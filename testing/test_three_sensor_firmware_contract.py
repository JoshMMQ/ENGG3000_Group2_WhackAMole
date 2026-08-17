from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HOST_SKETCH = (
    REPOSITORY_ROOT
    / "firmware"
    / "three_sensor_host_left"
    / "three_sensor_host_left.ino"
)
CENTRE_SKETCH = (
    REPOSITORY_ROOT
    / "firmware"
    / "three_sensor_station_centre"
    / "three_sensor_station_centre.ino"
)
RIGHT_SKETCH = (
    REPOSITORY_ROOT
    / "firmware"
    / "three_sensor_station_right"
    / "three_sensor_station_right.ino"
)


class ThreeSensorFirmwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.host = HOST_SKETCH.read_text(encoding="utf-8")
        cls.centre = CENTRE_SKETCH.read_text(encoding="utf-8")
        cls.right = RIGHT_SKETCH.read_text(encoding="utf-8")

    def test_three_sketches_share_the_radio_and_message_contract(self) -> None:
        for sketch in (self.host, self.centre, self.right):
            self.assertIn("constexpr uint8_t WIFI_CHANNEL = 6;", sketch)
            self.assertIn("0x57414D33UL", sketch)
            self.assertIn("0x57414D53UL", sketch)
            self.assertIn(
                "struct __attribute__((packed)) MeasureCommand", sketch
            )
            self.assertIn(
                "struct __attribute__((packed)) MeasureResult", sketch
            )
            self.assertIn("uint8_t targetSensorIndex;", sketch)
            self.assertIn("uint8_t sensorIndex;", sketch)

    def test_host_uses_three_sequential_provisional_slots(self) -> None:
        self.assertIn("S2_TRIGGER_OFFSET_US = 35000UL", self.host)
        self.assertIn("S3_TRIGGER_OFFSET_US = 70000UL", self.host)
        self.assertIn("SCAN_INTERVAL_US = 105000UL", self.host)
        self.assertIn("STATION_RESULT_TIMEOUT_US = 30000UL", self.host)

        s1_position = self.host.index("const RangeSample s1 = readLocalSensor()")
        s2_position = self.host.index("requestStation(S2_INDEX, cycleId)")
        s3_position = self.host.index("requestStation(S3_INDEX, cycleId)")
        self.assertLess(s1_position, s2_position)
        self.assertLess(s2_position, s3_position)

    def test_host_emits_exact_version_three_scan_fields(self) -> None:
        for field in (
            "version\\\":3",
            "sensor_scan",
            "cycle_id",
            "readings",
            "sensor_id",
            "distance_mm",
            "valid",
            "sample_time_ms",
        ):
            self.assertIn(field, self.host)
        self.assertIn('appendReading(payload, "s1", s1)', self.host)
        self.assertIn('appendReading(payload, "s2", s2)', self.host)
        self.assertIn('appendReading(payload, "s3", s3)', self.host)
        self.assertNotIn('appendReading(payload, "s4"', self.host)
        self.assertIn("LAPTOP_UDP_PORT = 5005", self.host)

    def test_stations_have_fixed_centre_and_right_identities(self) -> None:
        self.assertIn("constexpr uint8_t SENSOR_INDEX = 2;", self.centre)
        self.assertIn('const char* SENSOR_ID = "s2";', self.centre)
        self.assertIn("constexpr uint8_t SENSOR_INDEX = 3;", self.right)
        self.assertIn('const char* SENSOR_ID = "s3";', self.right)

        for sketch in (self.centre, self.right):
            self.assertIn(
                "command.targetSensorIndex != SENSOR_INDEX", sketch
            )
            loop_match = re.search(
                r"void loop\(\) \{(?P<body>.*?)\n\}",
                sketch,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(loop_match)
            self.assertIn("processCommand(command)", loop_match.group("body"))
            self.assertNotIn("readSensor()", loop_match.group("body"))

    def test_all_three_sensor_drivers_share_range_and_pin_boundaries(self) -> None:
        for sketch in (self.host, self.centre, self.right):
            self.assertIn("TRIG_PIN = 32", sketch)
            self.assertIn("ECHO_PIN = 35", sketch)
            self.assertIn("ECHO_TIMEOUT_US = 18000UL", sketch)
            self.assertIn("MIN_DISTANCE_MM = 20.0f", sketch)
            self.assertIn("MAX_DISTANCE_MM = 3000.0f", sketch)
            self.assertRegex(
                sketch,
                r"distanceMm\s*>=\s*MIN_DISTANCE_MM\s*&&\s*"
                r"distanceMm\s*<=\s*MAX_DISTANCE_MM",
            )


if __name__ == "__main__":
    unittest.main()
