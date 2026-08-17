from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HOST_SKETCH = REPOSITORY_ROOT / "firmware" / "range_pair_host" / "range_pair_host.ino"
RIGHT_SKETCH = (
    REPOSITORY_ROOT / "firmware" / "range_station_right" / "range_station_right.ino"
)


class RangePairFirmwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.host = HOST_SKETCH.read_text(encoding="utf-8")
        cls.right = RIGHT_SKETCH.read_text(encoding="utf-8")

    def test_both_boards_share_the_radio_and_message_contract(self) -> None:
        for sketch in (self.host, self.right):
            self.assertIn("constexpr uint8_t WIFI_CHANNEL = 6;", sketch)
            self.assertIn("0x57414D43UL", sketch)
            self.assertIn("0x57414D52UL", sketch)
            self.assertIn("struct __attribute__((packed)) MeasureCommand", sketch)
            self.assertIn("struct __attribute__((packed)) MeasureResult", sketch)

    def test_host_uses_the_approved_non_overlapping_schedule(self) -> None:
        self.assertIn("RIGHT_TRIGGER_OFFSET_US = 35000UL", self.host)
        self.assertIn("CYCLE_INTERVAL_US = 70000UL", self.host)
        self.assertIn("RIGHT_RESULT_TIMEOUT_US = 30000UL", self.host)

    def test_host_emits_every_required_v2_packet_field(self) -> None:
        for field in (
            "version",
            "type",
            "range_pair",
            "cycle_id",
            "left_mm",
            "right_mm",
            "left_valid",
            "right_valid",
            "pair_skew_ms",
        ):
            self.assertIn(field, self.host)
        self.assertIn("LAPTOP_UDP_PORT = 5005", self.host)

    def test_right_sensor_is_command_driven_not_free_running(self) -> None:
        loop_match = re.search(
            r"void loop\(\) \{(?P<body>.*?)\n\}",
            self.right,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(loop_match)
        loop_body = loop_match.group("body")
        self.assertIn("processCommand(command)", loop_body)
        self.assertNotIn("readRightSensor()", loop_body)

    def test_host_and_station_keep_the_existing_sensor_pin_contract(self) -> None:
        for sketch in (self.host, self.right):
            self.assertIn("TRIG_PIN = 32", sketch)
            self.assertIn("ECHO_PIN = 35", sketch)
            self.assertIn("ECHO_TIMEOUT_US = 18000UL", sketch)

    def test_both_sensor_drivers_keep_the_three_metre_tolerance(self) -> None:
        for sketch in (self.host, self.right):
            self.assertIn("MIN_DISTANCE_MM = 20.0f", sketch)
            self.assertIn("MAX_DISTANCE_MM = 3000.0f", sketch)
            self.assertRegex(
                sketch,
                r"distanceMm\s*>=\s*MIN_DISTANCE_MM\s*&&\s*"
                r"distanceMm\s*<=\s*MAX_DISTANCE_MM",
            )


if __name__ == "__main__":
    unittest.main()
