import socket
import unittest

from software.game.presentation_tracking import (
    PRESENTATION_COLUMN_X_M,
    PresentationTrackingSource,
    interpolate_position,
)
from software.game.sensor_scan import SensorId
from software.game.udp_position import TrackingStatus
from software.transport.mock_sensor_scan_sender import (
    build_sensor_scan_payload,
    encode_payload,
    send_mock_scans,
)


class FakeSocket:
    def __init__(self, packets: list[bytes]) -> None:
        self.packets = list(packets)
        self.close_count = 0

    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        del buffer_size
        if not self.packets:
            raise BlockingIOError
        return self.packets.pop(0), ("127.0.0.1", 5005)

    def close(self) -> None:
        self.close_count += 1


def packet(
    cycle_id: int,
    distances_mm: tuple[float | None, float | None, float | None],
) -> bytes:
    return encode_payload(build_sensor_scan_payload(cycle_id, distances_mm))


class PresentationTrackingSourceTests(unittest.TestCase):
    def test_starts_waiting_at_safe_centre_target(self) -> None:
        source = PresentationTrackingSource(sock=FakeSocket([]))

        snapshot = source.poll(now_s=0.0)

        self.assertEqual(snapshot.status, TrackingStatus.WAITING)
        self.assertIsNone(snapshot.world_position)
        self.assertEqual(snapshot.cursor_position, (0.7, 1.0))
        self.assertIsNone(snapshot.active_sensor)
        self.assertEqual(snapshot.filtered_distances_mm, (None, None, None))

    def test_first_valid_winner_becomes_active_and_controls_xy(self) -> None:
        source = PresentationTrackingSource(
            sock=FakeSocket([packet(1, (325.0, 600.0, 800.0))])
        )

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.status, TrackingStatus.PLAYABLE)
        self.assertEqual(snapshot.active_sensor, SensorId.S1)
        self.assertEqual(snapshot.candidate_sensor, SensorId.S1)
        self.assertEqual(
            snapshot.world_position,
            (PRESENTATION_COLUMN_X_M[SensorId.S1], 0.325),
        )

    def test_new_sensor_requires_two_consecutive_wins(self) -> None:
        fake_socket = FakeSocket([packet(1, (300.0, 500.0, 700.0))])
        source = PresentationTrackingSource(sock=fake_socket)
        source.poll(now_s=1.0)

        fake_socket.packets.append(packet(2, (600.0, 250.0, 700.0)))
        first_s2 = source.poll(now_s=1.1)
        self.assertEqual(first_s2.active_sensor, SensorId.S1)
        self.assertEqual(first_s2.candidate_sensor, SensorId.S2)
        self.assertEqual(first_s2.candidate_count, 1)
        self.assertEqual(first_s2.world_position, (0.233, 0.45))

        fake_socket.packets.append(packet(3, (200.0, 400.0, 700.0)))
        interrupted = source.poll(now_s=1.2)
        self.assertEqual(interrupted.active_sensor, SensorId.S1)
        self.assertEqual(interrupted.candidate_count, 0)

        fake_socket.packets.extend(
            [
                packet(4, (650.0, 225.0, 700.0)),
                packet(5, (650.0, 220.0, 700.0)),
            ]
        )
        confirmed = source.poll(now_s=1.3)
        self.assertEqual(confirmed.active_sensor, SensorId.S2)
        self.assertEqual(confirmed.world_position, (0.7, 0.225))

    def test_three_valid_measurement_median_rejects_one_scan_outlier(self) -> None:
        source = PresentationTrackingSource(
            sock=FakeSocket(
                [
                    packet(1, (300.0, 500.0, 700.0)),
                    packet(2, (305.0, 500.0, 700.0)),
                    packet(3, (900.0, 500.0, 700.0)),
                ]
            )
        )

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.active_sensor, SensorId.S1)
        self.assertEqual(snapshot.world_position, (0.233, 0.305))
        self.assertEqual(snapshot.filtered_distance_mm(SensorId.S1), 305.0)
        self.assertIn("S1: raw=900.0 mm  med3=305.0 mm", snapshot.diagnostic_lines)

    def test_invalid_measurement_does_not_enter_valid_median_history(self) -> None:
        source = PresentationTrackingSource(
            sock=FakeSocket(
                [
                    packet(1, (300.0, 500.0, 700.0)),
                    packet(2, (None, 500.0, 700.0)),
                    packet(3, (330.0, 500.0, 700.0)),
                ]
            )
        )

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.filtered_distance_mm(SensorId.S1), 315.0)
        self.assertEqual(snapshot.world_position, (0.233, 0.315))

    def test_invalid_readings_are_ignored_and_all_invalid_holds_target(self) -> None:
        fake_socket = FakeSocket([packet(1, (None, 450.0, 600.0))])
        source = PresentationTrackingSource(sock=fake_socket)

        tracking = source.poll(now_s=1.0)
        self.assertEqual(tracking.active_sensor, SensorId.S2)
        self.assertEqual(tracking.world_position, (0.7, 0.45))

        fake_socket.packets.append(packet(2, (None, None, None)))
        holding = source.poll(now_s=1.1)
        self.assertEqual(holding.status, TrackingStatus.TRACKING_LOST)
        self.assertIsNone(holding.world_position)
        self.assertEqual(holding.cursor_position, (0.7, 0.45))
        self.assertIn("Status: HOLDING LAST TARGET", holding.diagnostic_lines)

    def test_depth_is_clamped_and_old_or_malformed_packets_are_ignored(self) -> None:
        source = PresentationTrackingSource(
            sock=FakeSocket(
                [
                    b"not-json",
                    packet(8, (5000.0, None, None)),
                    packet(7, (100.0, None, None)),
                ]
            )
        )

        snapshot = source.poll(now_s=2.0)

        self.assertEqual(snapshot.cycle_id, 8)
        self.assertEqual(snapshot.world_position, (0.233, 2.0))

    def test_stale_stream_holds_last_target_without_new_movement(self) -> None:
        source = PresentationTrackingSource(
            sock=FakeSocket([packet(1, (300.0, 600.0, 800.0))]),
            stale_after_s=0.5,
        )
        live = source.poll(now_s=1.0)

        stale = source.poll(now_s=1.6)

        self.assertEqual(live.status, TrackingStatus.PLAYABLE)
        self.assertEqual(stale.status, TrackingStatus.TRACKING_LOST)
        self.assertIsNone(stale.world_position)
        self.assertEqual(stale.cursor_position, live.cursor_position)

    def test_real_local_udp_sender_reaches_presentation_source(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            port = receiver.getsockname()[1]
            source = PresentationTrackingSource(sock=receiver)

            send_mock_scans(
                target_port=port,
                count=1,
                interval_s=0.0,
                distances_mm=(900.0, 350.0, 700.0),
            )
            snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.status, TrackingStatus.PLAYABLE)
        self.assertEqual(snapshot.active_sensor, SensorId.S2)
        self.assertEqual(snapshot.world_position, (0.7, 0.35))

    def test_source_configuration_is_validated(self) -> None:
        for kwargs in (
            {"confirmation_scans": 0},
            {"confirmation_scans": True},
            {"tracked_depth_m": 0.0},
            {"stale_after_s": float("nan")},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    PresentationTrackingSource(sock=FakeSocket([]), **kwargs)

    def test_injected_socket_is_not_owned(self) -> None:
        fake_socket = FakeSocket([])
        source = PresentationTrackingSource(sock=fake_socket)

        source.close()

        self.assertEqual(fake_socket.close_count, 0)


class PresentationInterpolationTests(unittest.TestCase):
    def test_interpolation_is_frame_rate_independent(self) -> None:
        target = (1.167, 1.8)
        at_60_fps = (0.233, 0.2)
        for _ in range(12):
            at_60_fps = interpolate_position(at_60_fps, target, 1.0 / 60.0)

        at_30_fps = (0.233, 0.2)
        for _ in range(6):
            at_30_fps = interpolate_position(at_30_fps, target, 1.0 / 30.0)

        self.assertAlmostEqual(at_60_fps[0], at_30_fps[0], places=9)
        self.assertAlmostEqual(at_60_fps[1], at_30_fps[1], places=9)

    def test_interpolation_settles_and_caps_long_frame_steps(self) -> None:
        target = (0.7, 1.0)

        self.assertEqual(interpolate_position((0.701, 1.001), target, 0.016), target)
        after_stall = interpolate_position((0.0, 0.0), target, 10.0)
        self.assertGreater(after_stall[0], 0.0)
        self.assertLess(after_stall[0], target[0])

    def test_interpolation_rejects_invalid_configuration(self) -> None:
        invalid_calls = (
            ((float("nan"), 0.0), (1.0, 1.0), 0.1, 12.0),
            ((0.0, 0.0), (1.0, 1.0), -0.1, 12.0),
            ((0.0, 0.0), (1.0, 1.0), 0.1, 0.0),
        )
        for render, target, delta_s, response_rate in invalid_calls:
            with self.subTest(call=(render, target, delta_s, response_rate)):
                with self.assertRaises(ValueError):
                    interpolate_position(
                        render,
                        target,
                        delta_s,
                        response_rate=response_rate,
                    )


if __name__ == "__main__":
    unittest.main()
