import json
import unittest

from software.transport.packet import (
    SUPPORTED_PACKET_VERSION,
    SensorReading,
    TelemetryPacket,
    parse_telemetry_packet,
)


def valid_payload() -> dict:
    return {
        "v": 1,
        "node_id": "esp32_01",
        "seq": 7,
        "sent_ms": 12345,
        "readings": [
            {
                "sensor_id": "simulated",
                "distance_mm": 1500,
                "valid": True,
            }
        ],
        "battery_mv": 3700,
        "status": "ok",
    }


class TelemetryPacketParserTests(unittest.TestCase):
    def test_parses_valid_json_bytes(self) -> None:
        packet = parse_telemetry_packet(json.dumps(valid_payload()).encode("utf-8"))

        self.assertEqual(
            packet,
            TelemetryPacket(
                version=SUPPORTED_PACKET_VERSION,
                node_id="esp32_01",
                sequence=7,
                sent_ms=12345,
                readings=(SensorReading(sensor_id="simulated", distance_mm=1500, valid=True),),
                battery_mv=3700,
                status="ok",
            ),
        )

    def test_parses_valid_dict_payload(self) -> None:
        packet = parse_telemetry_packet(valid_payload())

        self.assertIsNotNone(packet)
        self.assertEqual(packet.node_id, "esp32_01")
        self.assertEqual(packet.readings[0].distance_mm, 1500)

    def test_rejects_unknown_packet_version(self) -> None:
        payload = valid_payload()
        payload["v"] = 2

        self.assertIsNone(parse_telemetry_packet(payload))

    def test_rejects_missing_required_fields(self) -> None:
        for field in ("v", "node_id", "seq", "sent_ms", "readings", "status"):
            payload = valid_payload()
            del payload[field]

            self.assertIsNone(parse_telemetry_packet(payload), field)

    def test_rejects_malformed_json(self) -> None:
        self.assertIsNone(parse_telemetry_packet(b"{bad json"))

    def test_rejects_negative_sequence_or_time(self) -> None:
        payload = valid_payload()
        payload["seq"] = -1
        self.assertIsNone(parse_telemetry_packet(payload))

        payload = valid_payload()
        payload["sent_ms"] = -1
        self.assertIsNone(parse_telemetry_packet(payload))

    def test_rejects_invalid_reading_shape(self) -> None:
        payload = valid_payload()
        payload["readings"] = []
        self.assertIsNone(parse_telemetry_packet(payload))

        payload = valid_payload()
        payload["readings"][0]["valid"] = "true"
        self.assertIsNone(parse_telemetry_packet(payload))

        payload = valid_payload()
        payload["readings"][0]["distance_mm"] = -1
        self.assertIsNone(parse_telemetry_packet(payload))

    def test_allows_invalid_reading_without_distance(self) -> None:
        payload = valid_payload()
        payload["readings"][0]["valid"] = False
        payload["readings"][0]["distance_mm"] = None

        packet = parse_telemetry_packet(payload)

        self.assertIsNotNone(packet)
        self.assertIsNone(packet.readings[0].distance_mm)
        self.assertFalse(packet.readings[0].valid)


if __name__ == "__main__":
    unittest.main()
