import unittest
from dataclasses import FrozenInstanceError

from software.game.sensor_overlay import (
    ID_MISMATCH,
    LIVE,
    NO_ECHO,
    PORT_ERROR,
    STALE,
    WAITING,
    SensorOverlaySnapshot,
    SensorOverlayValue,
    SerialSensorOverlay,
)
from software.transport.serial_sensor import BenchSensorReading


class FakeSource:
    def __init__(self, batches=()) -> None:
        self.batches = list(batches)
        self.poll_count = 0
        self.closed = False
        self.close_error = None

    def poll_readings(self):
        self.poll_count += 1
        if not self.batches:
            return ()
        batch = self.batches.pop(0)
        if isinstance(batch, BaseException):
            raise batch
        return tuple(batch)

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def valid(node_id: str, sensor_id: str, distance_mm: float) -> BenchSensorReading:
    return BenchSensorReading(node_id, sensor_id, distance_mm, True, 1)


class SerialSensorOverlayTests(unittest.TestCase):
    def make_overlay(self, left=None, right=None, **kwargs):
        return SerialSensorOverlay(
            "/dev/left",
            "/dev/right",
            left_source=left or FakeSource(),
            right_source=right or FakeSource(),
            **kwargs,
        )

    def test_snapshot_values_are_immutable_and_initially_waiting(self) -> None:
        overlay = self.make_overlay()

        snapshot = overlay.snapshot(now_s=10.0)

        self.assertEqual(
            snapshot,
            SensorOverlaySnapshot(
                left=SensorOverlayValue("LEFT SENSOR", "/dev/left", WAITING, None),
                right=SensorOverlayValue("RIGHT SENSOR", "/dev/right", WAITING, None),
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.left.status = LIVE

    def test_poll_returns_latest_live_reading_from_each_port(self) -> None:
        left = FakeSource([[
            valid("box1", "left", 300.0),
            valid("box1", "left", 325.5),
        ]])
        right = FakeSource([[valid("box2", "right", 710.25)]])
        overlay = self.make_overlay(left, right)

        snapshot = overlay.poll(now_s=2.0)

        self.assertEqual(snapshot.left.status, LIVE)
        self.assertEqual(snapshot.left.distance_mm, 325.5)
        self.assertEqual(snapshot.right.status, LIVE)
        self.assertEqual(snapshot.right.distance_mm, 710.25)
        self.assertEqual((left.poll_count, right.poll_count), (1, 1))

    def test_no_echo_and_stale_are_display_states_not_positions(self) -> None:
        left = FakeSource([[
            BenchSensorReading("box1", "left", None, False, 1),
        ]])
        right = FakeSource([[valid("box2", "right", 800.0)]])
        overlay = self.make_overlay(left, right, stale_after_s=1.0)

        first = overlay.poll(now_s=5.0)
        stale = overlay.snapshot(now_s=6.01)

        self.assertEqual(first.left, SensorOverlayValue("LEFT SENSOR", "/dev/left", NO_ECHO, None))
        self.assertEqual(stale.left.status, STALE)
        self.assertIsNone(stale.left.distance_mm)
        self.assertEqual(stale.right.status, STALE)
        self.assertEqual(stale.right.distance_mm, 800.0)

    def test_exact_node_and_sensor_identities_are_enforced(self) -> None:
        for node_id, sensor_id in (("box9", "left"), ("box1", "right")):
            with self.subTest(node_id=node_id, sensor_id=sensor_id):
                overlay = self.make_overlay(
                    FakeSource([[valid(node_id, sensor_id, 444.0)]]),
                    FakeSource([[valid("box2", "right", 555.0)]]),
                )
                snapshot = overlay.poll(now_s=1.0)
                self.assertEqual(snapshot.left.status, ID_MISMATCH)
                self.assertIsNone(snapshot.left.distance_mm)
                self.assertEqual(snapshot.right.status, LIVE)

    def test_poll_errors_are_isolated_per_port_and_recovery_clears_error(self) -> None:
        left = FakeSource([
            OSError("left disconnected"),
            [valid("box1", "left", 123.0)],
        ])
        right = FakeSource([[valid("box2", "right", 456.0)], []])
        overlay = self.make_overlay(left, right)

        failed = overlay.poll(now_s=1.0)
        recovered = overlay.poll(now_s=1.1)

        self.assertEqual(failed.left.status, PORT_ERROR)
        self.assertIsNone(failed.left.distance_mm)
        self.assertEqual(failed.right.status, LIVE)
        self.assertEqual(recovered.left.status, LIVE)
        self.assertEqual(recovered.left.distance_mm, 123.0)
        self.assertEqual(recovered.right.status, LIVE)

    def test_positive_finite_stale_timeout_is_required(self) -> None:
        for value in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.make_overlay(stale_after_s=value)

    def test_constructor_closes_left_when_opening_right_fails(self) -> None:
        left = FakeSource()

        def factory(port, baud_rate):
            self.assertEqual(baud_rate, 115200)
            if port == "/dev/left":
                return left
            raise OSError("right is busy")

        with self.assertRaisesRegex(OSError, "right is busy"):
            SerialSensorOverlay("/dev/left", "/dev/right", source_factory=factory)

        self.assertTrue(left.closed)

    def test_close_attempts_both_sources_and_is_idempotent(self) -> None:
        left = FakeSource()
        right = FakeSource()
        left.close_error = OSError("left close failed")
        overlay = self.make_overlay(left, right)

        with self.assertRaisesRegex(OSError, "left close failed"):
            overlay.close()

        self.assertTrue(left.closed)
        self.assertTrue(right.closed)
        overlay.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            overlay.poll(now_s=1.0)


if __name__ == "__main__":
    unittest.main()
