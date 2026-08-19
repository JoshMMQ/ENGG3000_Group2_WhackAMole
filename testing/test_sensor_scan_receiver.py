import unittest

from software.transport.mock_sensor_scan_sender import build_sensor_scan_payload
from software.transport.sensor_scan_packet import parse_sensor_scan_packet
from software.transport.sensor_scan_receiver import format_sensor_scan


class SensorScanReceiverTests(unittest.TestCase):
    def test_formats_complete_scan_with_identity_time_and_validity(self) -> None:
        payload = build_sensor_scan_payload(
            8,
            (900.0, None, 1100.0),
            cycle_started_ms=1000,
        )
        scan = parse_sensor_scan_packet(payload)

        self.assertIsNotNone(scan)
        self.assertEqual(
            format_sensor_scan(scan),
            "cycle_id=8 s1=900.0mm@1000ms s2=invalid@1035ms "
            "s3=1100.0mm@1070ms",
        )


if __name__ == "__main__":
    unittest.main()
