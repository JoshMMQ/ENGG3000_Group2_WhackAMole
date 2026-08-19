import socket
import unittest

from software.game.sensor_scan import SensorId
from software.transport.mock_sensor_scan_sender import (
    build_sensor_scan_payload,
    encode_payload,
    send_mock_scans,
)
from software.transport.sensor_scan_packet import parse_sensor_scan_packet


class MockSensorScanSenderTests(unittest.TestCase):
    def test_payload_has_three_ordered_samples_and_no_s4(self) -> None:
        payload = build_sensor_scan_payload(2, cycle_started_ms=100)

        self.assertEqual(payload["version"], 3)
        self.assertEqual(
            [reading["sensor_id"] for reading in payload["readings"]],
            ["s1", "s2", "s3"],
        )
        self.assertEqual(
            [reading["sample_time_ms"] for reading in payload["readings"]],
            [100, 135, 170],
        )
        self.assertNotIn("s4", str(payload).lower())

    def test_encoded_payload_round_trips(self) -> None:
        scan = parse_sensor_scan_packet(
            encode_payload(build_sensor_scan_payload(7, (700.0, 800.0, 900.0)))
        )

        self.assertIsNotNone(scan)
        self.assertEqual(scan.reading_for(SensorId.S1).distance_mm, 700.0)

    def test_sender_reaches_local_udp_socket(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1.0)
            _, port = receiver.getsockname()

            send_mock_scans(target_port=port, count=1, interval_s=0.0)
            packet, _ = receiver.recvfrom(4096)

        self.assertIsNotNone(parse_sensor_scan_packet(packet))


if __name__ == "__main__":
    unittest.main()
