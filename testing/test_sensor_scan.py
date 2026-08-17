import unittest
from dataclasses import FrozenInstanceError

from software.game.sensor_scan import SensorId, SensorReading, SensorScan


def valid_reading(
    sensor_id: SensorId, distance_mm: float = 1000.0, sample_time_ms: int = 0
) -> SensorReading:
    return SensorReading(
        sensor_id=sensor_id,
        distance_mm=distance_mm,
        valid=True,
        sample_time_ms=sample_time_ms,
    )


class SensorReadingTests(unittest.TestCase):
    def test_valid_reading_is_normalized_and_immutable(self) -> None:
        reading = valid_reading(SensorId.S1, distance_mm=900, sample_time_ms=10)

        self.assertEqual(reading.distance_mm, 900.0)
        with self.assertRaises(FrozenInstanceError):
            reading.distance_mm = 800.0  # type: ignore[misc]

    def test_invalid_reading_uses_none_distance(self) -> None:
        reading = SensorReading(SensorId.S2, None, False, 35)

        self.assertFalse(reading.valid)
        self.assertIsNone(reading.distance_mm)

    def test_invalid_reading_rejects_a_plausible_distance(self) -> None:
        with self.assertRaises(ValueError):
            SensorReading(SensorId.S2, 1200.0, False, 35)

    def test_valid_reading_rejects_missing_nonfinite_or_nonpositive_distance(
        self,
    ) -> None:
        for distance_mm in (None, float("nan"), float("inf"), 0.0, -1.0):
            with self.subTest(distance_mm=distance_mm):
                with self.assertRaises(ValueError):
                    SensorReading(SensorId.S3, distance_mm, True, 70)

    def test_reading_rejects_unknown_sensor_identity(self) -> None:
        with self.assertRaises(TypeError):
            SensorReading("s4", 1000.0, True, 0)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            SensorId("s4")

    def test_reading_rejects_bad_validity_or_sample_time(self) -> None:
        with self.assertRaises(TypeError):
            SensorReading(SensorId.S1, 1000.0, 1, 0)  # type: ignore[arg-type]
        for sample_time_ms in (-1, 1.5, True):
            with self.subTest(sample_time_ms=sample_time_ms):
                with self.assertRaises(ValueError):
                    SensorReading(
                        SensorId.S1,
                        1000.0,
                        True,
                        sample_time_ms,  # type: ignore[arg-type]
                    )


class SensorScanTests(unittest.TestCase):
    def make_scan(self) -> SensorScan:
        return SensorScan(
            cycle_id=42,
            readings=(
                valid_reading(SensorId.S1, 900.0, 0),
                valid_reading(SensorId.S2, 1000.0, 35),
                valid_reading(SensorId.S3, 1100.0, 70),
            ),
        )

    def test_complete_scan_exposes_all_three_readings_and_timing(self) -> None:
        scan = self.make_scan()

        self.assertEqual(scan.reading_for(SensorId.S2).distance_mm, 1000.0)
        self.assertTrue(scan.all_valid)
        self.assertEqual(scan.sample_span_ms, 70)

    def test_scan_order_does_not_change_identity_lookup(self) -> None:
        scan = SensorScan(
            cycle_id=1,
            readings=(
                valid_reading(SensorId.S3),
                valid_reading(SensorId.S1),
                valid_reading(SensorId.S2),
            ),
        )

        self.assertEqual(scan.reading_for(SensorId.S1).sensor_id, SensorId.S1)

    def test_complete_scan_can_represent_one_invalid_acquisition(self) -> None:
        scan = SensorScan(
            cycle_id=3,
            readings=(
                valid_reading(SensorId.S1),
                SensorReading(SensorId.S2, None, False, 35),
                valid_reading(SensorId.S3, sample_time_ms=70),
            ),
        )

        self.assertFalse(scan.all_valid)

    def test_scan_rejects_missing_or_duplicate_sensor(self) -> None:
        with self.assertRaises(ValueError):
            SensorScan(
                1,
                (
                    valid_reading(SensorId.S1),
                    valid_reading(SensorId.S2),
                ),
            )
        with self.assertRaises(ValueError):
            SensorScan(
                1,
                (
                    valid_reading(SensorId.S1),
                    valid_reading(SensorId.S1),
                    valid_reading(SensorId.S3),
                ),
            )

    def test_scan_rejects_mutable_or_non_reading_collection(self) -> None:
        readings = [
            valid_reading(SensorId.S1),
            valid_reading(SensorId.S2),
            valid_reading(SensorId.S3),
        ]
        with self.assertRaises(TypeError):
            SensorScan(1, readings)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            SensorScan(  # type: ignore[arg-type]
                1, (readings[0], readings[1], object())
            )

    def test_scan_rejects_bad_cycle_or_lookup_identity(self) -> None:
        for cycle_id in (-1, 1.5, True):
            with self.subTest(cycle_id=cycle_id):
                with self.assertRaises(ValueError):
                    SensorScan(  # type: ignore[arg-type]
                        cycle_id, self.make_scan().readings
                    )
        with self.assertRaises(TypeError):
            self.make_scan().reading_for("s1")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
