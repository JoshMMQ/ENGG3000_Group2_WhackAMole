from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_ROOT = REPOSITORY_ROOT / "firmware"
HOST_PATH = (
    FIRMWARE_ROOT / "three_sensor_host_left" / "three_sensor_host_left.ino"
)
STATION_PATHS = {
    2: (
        "s2",
        FIRMWARE_ROOT
        / "three_sensor_station_centre"
        / "three_sensor_station_centre.ino",
    ),
    3: (
        "s3",
        FIRMWARE_ROOT
        / "three_sensor_station_right"
        / "three_sensor_station_right.ino",
    ),
}


class ThreeSensorFirmwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.host = HOST_PATH.read_text(encoding="utf-8")
        cls.stations = {
            index: path.read_text(encoding="utf-8")
            for index, (_, path) in STATION_PATHS.items()
        }

    def test_s1_is_the_wifi_and_esp_now_host(self) -> None:
        for expected in (
            "WiFi.mode(WIFI_AP_STA);",
            'AP_SSID = "WhackAMole"',
            "WiFi.softAP(",
            "esp_now_init()",
            "S1_INDEX = 1",
            "UDP_BROADCAST_IP(192, 168, 4, 255)",
            "LAPTOP_UDP_PORT = 5005",
        ):
            self.assertIn(expected, self.host)

    def test_s1_owns_the_non_overlapping_scan_schedule(self) -> None:
        for expected in (
            "SENSOR_SLOT_US = 35000UL",
            "S2_TRIGGER_OFFSET_US = 35000UL",
            "S3_TRIGGER_OFFSET_US = 70000UL",
            "SCAN_INTERVAL_US = 105000UL",
            "const RangeSample s1 = readLocalSensor();",
            "const RangeSample s2 = requestStation(S2_INDEX, cycleId);",
            "const RangeSample s3 = requestStation(S3_INDEX, cycleId);",
        ):
            self.assertIn(expected, self.host)

    def test_s2_and_s3_are_command_driven_esp_now_stations(self) -> None:
        for index, (sensor_id, _) in STATION_PATHS.items():
            source = self.stations[index]
            with self.subTest(sensor_id=sensor_id):
                self.assertIn(f"SENSOR_INDEX = {index}", source)
                self.assertIn(f'SENSOR_ID = "{sensor_id}"', source)
                self.assertIn("WiFi.mode(WIFI_STA);", source)
                self.assertIn("esp_now_init()", source)
                self.assertIn(
                    "command.targetSensorIndex != SENSOR_INDEX", source
                )
                self.assertIn("const RangeSample sample = readSensor();", source)
                loop_body = source[
                    source.index("void loop() {") : source.index(
                        "void configureEspNow() {"
                    )
                ]
                self.assertNotIn("readSensor()", loop_body)

    def test_host_and_stations_share_exact_binary_layouts(self) -> None:
        all_sources = (self.host, *self.stations.values())
        for source in all_sources:
            self.assertIn("sizeof(MeasureCommand) == 9", source)
            self.assertIn("sizeof(MeasureResult) == 18", source)
            self.assertIn("COMMAND_MAGIC = 0x57414D33UL", source)
            self.assertIn("RESULT_MAGIC = 0x57414D53UL", source)

    def test_host_emits_exact_version_three_sensor_set(self) -> None:
        for expected in (
            '\\"version\\":3',
            '\\"type\\":\\"sensor_scan\\"',
            'appendReading(payload, "s1", s1)',
            'appendReading(payload, "s2", s2)',
            'appendReading(payload, "s3", s3)',
            "udp.beginPacket(UDP_BROADCAST_IP, LAPTOP_UDP_PORT)",
        ):
            self.assertIn(expected, self.host)
        self.assertNotIn('"s4"', self.host.lower())


if __name__ == "__main__":
    unittest.main()
