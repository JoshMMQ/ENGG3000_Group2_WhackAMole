import json
import socket
import unittest

from software.transport.mock_udp_sender import (
    build_mock_payload,
    encode_payload,
    send_mock_packets,
    simulated_distance_mm,
)
from software.transport.packet import parse_telemetry_packet


class MockUdpSenderTests(unittest.TestCase):
    def test_build_mock_payload_matches_telemetry_schema(self) -> None:
        payload = build_mock_payload(sequence=3, sent_ms=120, distance_mm=1500)

        packet = parse_telemetry_packet(payload)

        self.assertIsNotNone(packet)
        self.assertEqual(packet.node_id, "mock_esp32_01")
        self.assertEqual(packet.sequence, 3)
        self.assertEqual(packet.readings[0].sensor_id, "simulated")
        self.assertEqual(packet.readings[0].distance_mm, 1500)

    def test_invalid_payload_marks_reading_invalid_without_distance(self) -> None:
        payload = build_mock_payload(sequence=4, sent_ms=200, distance_mm=1500, valid=False)

        packet = parse_telemetry_packet(payload)

        self.assertIsNotNone(packet)
        self.assertFalse(packet.readings[0].valid)
        self.assertIsNone(packet.readings[0].distance_mm)

    def test_encoded_payload_is_compact_json_bytes(self) -> None:
        payload = build_mock_payload(sequence=1, sent_ms=50, distance_mm=1000)
        encoded = encode_payload(payload)

        decoded = json.loads(encoded.decode("utf-8"))

        self.assertIsInstance(encoded, bytes)
        self.assertEqual(decoded["seq"], 1)

    def test_simulated_distance_stays_in_expected_range(self) -> None:
        for sequence in range(100):
            distance_mm = simulated_distance_mm(sequence)
            self.assertGreaterEqual(distance_mm, 500)
            self.assertLessEqual(distance_mm, 2500)

    def test_send_mock_packets_reaches_local_udp_socket(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1.0)
            _, port = receiver.getsockname()

            send_mock_packets(target_port=port, count=1, interval_s=0.0)
            data, _ = receiver.recvfrom(4096)

        packet = parse_telemetry_packet(data)

        self.assertIsNotNone(packet)
        self.assertEqual(packet.node_id, "mock_esp32_01")


if __name__ == "__main__":
    unittest.main()
