from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_ROOT = REPOSITORY_ROOT / "firmware"
STATIONS = {
    1: (
        "s1",
        FIRMWARE_ROOT
        / "three_sensor_wifi_station_left"
        / "three_sensor_wifi_station_left.ino",
    ),
    2: (
        "s2",
        FIRMWARE_ROOT
        / "three_sensor_wifi_station_centre"
        / "three_sensor_wifi_station_centre.ino",
    ),
    3: (
        "s3",
        FIRMWARE_ROOT
        / "three_sensor_wifi_station_right"
        / "three_sensor_wifi_station_right.ino",
    ),
}
PRESERVED_ESPNOW_SKETCHES = (
    FIRMWARE_ROOT / "three_sensor_host_left" / "three_sensor_host_left.ino",
    FIRMWARE_ROOT
    / "three_sensor_station_centre"
    / "three_sensor_station_centre.ino",
    FIRMWARE_ROOT
    / "three_sensor_station_right"
    / "three_sensor_station_right.ino",
)


class ThreeSensorFirmwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sketches = {
            index: path.read_text(encoding="utf-8")
            for index, (_, path) in STATIONS.items()
        }
        cls.active_source = "\n".join(cls.sketches.values())

    def test_each_station_is_one_self_contained_arduino_sketch(self) -> None:
        for sensor_index, (sensor_id, _) in STATIONS.items():
            source = self.sketches[sensor_index]
            with self.subTest(sensor_id=sensor_id):
                self.assertIn(
                    f"constexpr uint8_t SENSOR_INDEX = {sensor_index};",
                    source,
                )
                self.assertIn(
                    f'const char* const SENSOR_ID = "{sensor_id}";',
                    source,
                )
                self.assertIn("void setup() {", source)
                self.assertIn("void loop() {", source)
                self.assertNotIn('#include "wifi_udp_station.h"', source)
                self.assertNotIn('#include "station_config.h"', source)
                self.assertNotIn("SENSOR_INDEX_TO_UPLOAD", source)

    def test_all_stations_use_wifi_udp_not_esp_now(self) -> None:
        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                self.assertIn("WiFi.mode(WIFI_STA);", source)
                self.assertIn("WiFi.setSleep(false);", source)
                self.assertIn(
                    "WiFi.begin(WIFI_SSID, WIFI_PASSWORD);", source
                )
                self.assertIn("udp.begin(LOCAL_UDP_PORT)", source)
                self.assertIn(
                    "constexpr uint16_t LOCAL_UDP_PORT = 5006;", source
                )

        for forbidden in (
            "WiFi.softAP",
            "WIFI_AP_STA",
            "esp_now",
            "WIFI_CHANNEL",
            "UDP_BROADCAST_IP",
            "LAPTOP_UDP_PORT",
            "sensor_scan",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.active_source)

    def test_cpp_packets_match_phase_one_field_order_and_sizes(self) -> None:
        hello_fields = """struct __attribute__((packed)) HelloPacket {
  uint32_t magic;
  uint8_t version;
  uint8_t sensorIndex;
};"""
        command_fields = """struct __attribute__((packed)) MeasureCommand {
  uint32_t magic;
  uint32_t cycleId;
  uint8_t targetSensorIndex;
};"""
        result_fields = """struct __attribute__((packed)) MeasureResult {
  uint32_t magic;
  uint32_t cycleId;
  float distanceMm;
  uint32_t commandToSampleUs;
  uint8_t valid;
  uint8_t sensorIndex;
};"""

        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                for fields in (hello_fields, command_fields, result_fields):
                    self.assertIn(fields, source)
                self.assertIn("sizeof(HelloPacket) == 6", source)
                self.assertIn("sizeof(MeasureCommand) == 9", source)
                self.assertIn("sizeof(MeasureResult) == 18", source)
                self.assertIn("HELLO_MAGIC = 0x57414D48UL", source)
                self.assertIn("COMMAND_MAGIC = 0x57414D33UL", source)
                self.assertIn("RESULT_MAGIC = 0x57414D53UL", source)
                self.assertIn("PROTOCOL_VERSION = 1", source)

    def test_hello_is_unicast_immediate_and_periodic(self) -> None:
        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                self.assertIn("HELLO_INTERVAL_MS = 1000UL", source)
                self.assertIn(
                    "HelloPacket hello = {HELLO_MAGIC, PROTOCOL_VERSION, "
                    "SENSOR_INDEX}",
                    source,
                )
                self.assertIn(
                    "udp.beginPacket(COORDINATOR_IP, COORDINATOR_PORT)",
                    source,
                )
                self.assertIn("helloSentSinceConnect = false;", source)
                self.assertNotIn("WiFi.gatewayIP", source)

    def test_commands_are_strict_and_only_trigger_matching_station(self) -> None:
        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                self.assertIn("senderIp != COORDINATOR_IP", source)
                self.assertIn(
                    "packetSize != static_cast<int>(sizeof(MeasureCommand))",
                    source,
                )
                self.assertIn("command.magic != COMMAND_MAGIC", source)
                self.assertIn("command.targetSensorIndex < 1", source)
                self.assertIn("command.targetSensorIndex > 3", source)
                self.assertIn(
                    "command.targetSensorIndex != SENSOR_INDEX", source
                )

                loop_body = source[
                    source.index("void loop() {") : source.index(
                        "void maintainNetwork() {"
                    )
                ]
                self.assertNotIn("readSensor()", loop_body)
                command_handler = source[source.rindex("void handleCommand(") :]
                self.assertIn(
                    "const RangeSample sample = readSensor();",
                    command_handler,
                )
                self.assertIn("command.cycleId", command_handler)
                self.assertIn(
                    "udp.beginPacket(senderIp, senderPort)", command_handler
                )

    def test_sensor_and_recovery_boundaries_are_preserved(self) -> None:
        expected_values = (
            "TRIG_PIN = 32",
            "ECHO_PIN = 35",
            "ECHO_TIMEOUT_US = 18000UL",
            "SPEED_OF_SOUND_MM_PER_US = 0.343f",
            "MIN_DISTANCE_MM = 20.0f",
            "MAX_DISTANCE_MM = 3000.0f",
            "CALIBRATION_OFFSET_MM = 0.0f",
            "WIFI_RETRY_INTERVAL_MS = 5000UL",
            "udp.stop();",
        )
        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                for expected in expected_values:
                    self.assertIn(expected, source)
                self.assertNotIn("ESP.restart", source)
                self.assertNotIn("WiFi.disconnect", source)

    def test_credentials_remain_placeholders_and_are_never_logged(self) -> None:
        for sensor_index, source in self.sketches.items():
            with self.subTest(sensor_index=sensor_index):
                self.assertIn(
                    'WIFI_PASSWORD = "REPLACE_WITH_NEW_HOTSPOT_PASSWORD"',
                    source,
                )
                self.assertIn("IPAddress COORDINATOR_IP(0, 0, 0, 0);", source)
                self.assertNotIn("Serial.print(WIFI_PASSWORD", source)
                self.assertNotIn("Serial.printf(WIFI_PASSWORD", source)

    def test_previous_esp_now_three_board_baseline_is_preserved(self) -> None:
        for sketch_path in PRESERVED_ESPNOW_SKETCHES:
            with self.subTest(sketch=sketch_path):
                source = sketch_path.read_text(encoding="utf-8")
                self.assertIn("esp_now", source)


if __name__ == "__main__":
    unittest.main()
