import json
from math import hypot
import unittest

from software.game.udp_position import (
    RangePairPacket,
    TrackingStatus,
    UdpPositionSource,
    parse_range_pair_packet,
    triangulate_ranges,
)


class FakeSocket:
    def __init__(self, packets: list[bytes]) -> None:
        self._packets = packets
        self.closed = False

    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        if not self._packets:
            raise BlockingIOError
        return self._packets.pop(0), ("127.0.0.1", 12345)

    def close(self) -> None:
        self.closed = True


def ranges_for(x_m: float, y_m: float) -> tuple[float, float]:
    return hypot(x_m, y_m - 0.10) * 1000.0, hypot(x_m - 1.50, y_m - 0.10) * 1000.0


def valid_payload(cycle_id: int = 1, x_m: float = 0.75, y_m: float = 1.30) -> dict:
    left_mm, right_mm = ranges_for(x_m, y_m)
    return {
        "version": 2,
        "type": "range_pair",
        "cycle_id": cycle_id,
        "left_mm": left_mm,
        "right_mm": right_mm,
        "left_valid": True,
        "right_valid": True,
        "pair_skew_ms": 35.0,
    }


def encoded(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


class RangePairParserTests(unittest.TestCase):
    def test_parses_the_v2_contract(self) -> None:
        packet = parse_range_pair_packet(valid_payload(cycle_id=1042))

        self.assertIsInstance(packet, RangePairPacket)
        self.assertEqual(packet.cycle_id, 1042)
        self.assertEqual(packet.packet_type, "range_pair")
        self.assertEqual(packet.pair_skew_ms, 35.0)

    def test_accepts_null_ranges_only_when_marked_invalid(self) -> None:
        payload = valid_payload()
        payload.update(left_mm=None, left_valid=False)

        packet = parse_range_pair_packet(payload)

        self.assertIsNotNone(packet)
        self.assertFalse(packet.left_valid)

    def test_rejects_bad_schema_values(self) -> None:
        mutations = (
            ("version", 1),
            ("type", "position"),
            ("cycle_id", -1),
            ("cycle_id", 1.5),
            ("left_valid", 1),
            ("right_mm", None),
            ("pair_skew_ms", -0.1),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                payload = valid_payload()
                payload[field] = value
                self.assertIsNone(parse_range_pair_packet(payload))

        self.assertIsNone(parse_range_pair_packet(b"{bad json"))


class TriangulationTests(unittest.TestCase):
    def assertPositionAlmostEqual(self, actual, expected) -> None:
        self.assertIsNotNone(actual)
        self.assertAlmostEqual(actual[0], expected[0], places=6)
        self.assertAlmostEqual(actual[1], expected[1], places=6)

    def test_triangulates_centre_and_off_centre_positions(self) -> None:
        for expected in ((0.75, 1.30), (0.30, 1.00), (1.20, 1.00), (0.75, 0.50)):
            with self.subTest(expected=expected):
                self.assertPositionAlmostEqual(triangulate_ranges(*ranges_for(*expected)), expected)

    def test_rejects_impossible_and_out_of_footprint_geometry(self) -> None:
        self.assertIsNone(triangulate_ranges(500.0, 500.0))
        self.assertIsNone(triangulate_ranges(*ranges_for(2.0, 1.0)))
        self.assertIsNone(triangulate_ranges(10.0, 10.0))


class UdpPositionSourceTests(unittest.TestCase):
    def test_starts_waiting_at_safe_centre(self) -> None:
        source = UdpPositionSource(sock=FakeSocket([]))

        snapshot = source.poll(now_s=0.0)

        self.assertEqual(snapshot.status, TrackingStatus.WAITING)
        self.assertIsNone(snapshot.world_position)
        self.assertEqual(snapshot.cursor_position, (0.75, 1.30))

    def test_valid_pair_updates_two_dimensional_position(self) -> None:
        source = UdpPositionSource(
            sock=FakeSocket([encoded(valid_payload(x_m=0.30, y_m=1.00))]),
            filter_alpha=1.0,
        )

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.status, TrackingStatus.PLAYABLE)
        self.assertAlmostEqual(snapshot.world_position[0], 0.30, places=6)
        self.assertAlmostEqual(snapshot.world_position[1], 1.00, places=6)
        self.assertEqual(snapshot.cursor_position, snapshot.world_position)

    def test_dead_zone_freezes_the_last_playable_cursor(self) -> None:
        packets = [
            encoded(valid_payload(cycle_id=1, x_m=0.30, y_m=1.00)),
            encoded(valid_payload(cycle_id=2, x_m=0.75, y_m=0.50)),
        ]
        source = UdpPositionSource(sock=FakeSocket(packets), filter_alpha=1.0)

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.status, TrackingStatus.DEAD_ZONE)
        self.assertAlmostEqual(snapshot.world_position[1], 0.50, places=6)
        self.assertAlmostEqual(snapshot.cursor_position[0], 0.30, places=6)
        self.assertAlmostEqual(snapshot.cursor_position[1], 1.00, places=6)

    def test_invalid_pair_and_excessive_skew_mark_tracking_lost(self) -> None:
        for mutation in (
            {"left_valid": False, "left_mm": None},
            {"pair_skew_ms": 40.1},
            {"left_mm": 500.0, "right_mm": 500.0},
        ):
            with self.subTest(mutation=mutation):
                payload = valid_payload()
                payload.update(mutation)
                source = UdpPositionSource(sock=FakeSocket([encoded(payload)]), filter_alpha=1.0)
                self.assertEqual(source.poll(now_s=1.0).status, TrackingStatus.TRACKING_LOST)

    def test_stale_stream_marks_tracking_lost_and_retains_cursor(self) -> None:
        source = UdpPositionSource(
            sock=FakeSocket([encoded(valid_payload(x_m=1.20, y_m=1.00))]),
            stale_after_s=0.5,
            filter_alpha=1.0,
        )
        live = source.poll(now_s=1.0)

        stale = source.poll(now_s=1.51)

        self.assertEqual(stale.status, TrackingStatus.TRACKING_LOST)
        self.assertEqual(stale.cursor_position, live.cursor_position)

    def test_older_cycle_and_malformed_datagram_do_not_replace_new_state(self) -> None:
        packets = [
            encoded(valid_payload(cycle_id=3, x_m=1.20, y_m=1.00)),
            b"{bad json",
            encoded(valid_payload(cycle_id=2, x_m=0.30, y_m=1.00)),
        ]
        source = UdpPositionSource(sock=FakeSocket(packets), filter_alpha=1.0)

        snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.cycle_id, 3)
        self.assertAlmostEqual(snapshot.cursor_position[0], 1.20, places=6)

    def test_filter_smooths_accepted_world_positions(self) -> None:
        packets = [
            encoded(valid_payload(cycle_id=1, x_m=0.30, y_m=1.00)),
            encoded(valid_payload(cycle_id=2, x_m=1.20, y_m=1.00)),
        ]
        source = UdpPositionSource(sock=FakeSocket(packets), filter_alpha=0.5)

        snapshot = source.poll(now_s=1.0)

        self.assertAlmostEqual(snapshot.world_position[0], 0.75, places=6)

    def test_rejects_invalid_configuration(self) -> None:
        with self.assertRaises(ValueError):
            UdpPositionSource(sock=FakeSocket([]), filter_alpha=0.0)
        with self.assertRaises(ValueError):
            UdpPositionSource(sock=FakeSocket([]), stale_after_s=0.0)
        with self.assertRaises(ValueError):
            UdpPositionSource(sock=FakeSocket([]), max_pair_skew_ms=-1.0)


if __name__ == "__main__":
    unittest.main()
