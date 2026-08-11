import unittest

from software.diagnostics.sensor_monitor import (
    ERROR,
    LIVE,
    WAITING,
    SensorPanelState,
    distance_text,
    panel_rectangles,
    panel_status,
)
from software.transport.serial_sensor import BenchSensorReading


class SensorMonitorTests(unittest.TestCase):
    def test_formats_waiting_valid_and_no_echo_values(self) -> None:
        self.assertEqual(distance_text(None), ("--- mm", "waiting for JSON"))
        self.assertEqual(
            distance_text(BenchSensorReading("box1", "left", 173.7, True, 1)),
            ("173.7 mm", "17.4 cm"),
        )
        self.assertEqual(
            distance_text(BenchSensorReading("box1", "left", None, False, 2)),
            ("--- mm", "valid: false"),
        )

    def test_reports_live_stale_invalid_and_identity_mismatch(self) -> None:
        panel = SensorPanelState("LEFT SENSOR", "left", "fake")
        self.assertEqual(panel_status(panel, 10.0), ("WAITING", WAITING))

        panel.apply(BenchSensorReading("box1", "left", 500.0, True, 1), 10.0)
        self.assertEqual(panel_status(panel, 10.5), ("LIVE", LIVE))
        self.assertEqual(panel_status(panel, 11.1), ("STALE", WAITING))

        panel.apply(BenchSensorReading("box1", "left", None, False, 2), 12.0)
        self.assertEqual(panel_status(panel, 12.1), ("NO ECHO", ERROR))

        panel.apply(BenchSensorReading("box2", "right", 500.0, True, 3), 13.0)
        self.assertEqual(panel_status(panel, 13.1), ("ID MISMATCH", ERROR))

    def test_two_cards_fit_and_do_not_overlap(self) -> None:
        left, right = panel_rectangles(1000, 560)
        left_x, left_y, left_w, left_h = left
        right_x, right_y, right_w, right_h = right

        self.assertGreaterEqual(left_x, 0)
        self.assertGreaterEqual(left_y, 0)
        self.assertLessEqual(left_x + left_w, right_x)
        self.assertLessEqual(right_x + right_w, 1000)
        self.assertLessEqual(right_y + right_h, 560)


if __name__ == "__main__":
    unittest.main()
