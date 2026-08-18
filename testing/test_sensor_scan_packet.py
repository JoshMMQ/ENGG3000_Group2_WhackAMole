import copy
import json
import unittest

from software.game.sensor_scan import SensorId, SensorReading, SensorScan
from software.transport.mock_sensor_scan_sender import (
    build_sensor_scan_payload,
    encode_payload,
)
from software.transport.sensor_scan_packet import (
    encode_sensor_scan_packet,
    parse_sensor_scan_packet,
)


class SensorScanPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = build_sensor_scan_payload(
            42,
            (900.0, 1000.0, 1100.0),
            cycle_started_ms=500,
        )

    def test_complete_packet_round_trips_to_domain_model(self) -> None:
        scan = parse_sensor_scan_packet(encode_payload(self.payload))

        self.assertIsNotNone(scan)
        self.assertEqual(scan.cycle_id, 42)
        self.assertEqual(scan.reading_for(SensorId.S2).distance_mm, 1000.0)
        self.assertEqual(scan.reading_for(SensorId.S3).sample_time_ms, 570)
        self.assertTrue(scan.all_valid)

    def test_domain_scan_encoder_uses_exact_schema_and_canonical_order(self) -> None:
        scan = SensorScan(
            cycle_id=9,
            readings=(
                SensorReading(SensorId.S3, 1300.0, True, 70),
                SensorReading(SensorId.S1, 900.0, True, 0),
                SensorReading(SensorId.S2, None, False, 35),
            ),
        )

        encoded = encode_sensor_scan_packet(scan)
        payload = json.loads(encoded)

        self.assertEqual(
            list(payload), ["version", "type", "cycle_id", "readings"]
        )
        self.assertEqual(
            [reading["sensor_id"] for reading in payload["readings"]],
            ["s1", "s2", "s3"],
        )
        decoded = parse_sensor_scan_packet(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.cycle_id, scan.cycle_id)
        for sensor_id in SensorId:
            self.assertEqual(
                decoded.reading_for(sensor_id), scan.reading_for(sensor_id)
            )

    def test_invalid_acquisition_remains_part_of_complete_scan(self) -> None:
        payload = build_sensor_scan_payload(3, (900.0, None, 1100.0))

        scan = parse_sensor_scan_packet(payload)

        self.assertIsNotNone(scan)
        self.assertFalse(scan.all_valid)
        self.assertIsNone(scan.reading_for(SensorId.S2).distance_mm)

    def test_rejects_wrong_version_type_or_top_level_shape(self) -> None:
        changes = (
            ("version", 2),
            ("type", "range_pair"),
            ("cycle_id", -1),
        )
        for field, value in changes:
            with self.subTest(field=field):
                payload = copy.deepcopy(self.payload)
                payload[field] = value
                self.assertIsNone(parse_sensor_scan_packet(payload))

        payload = copy.deepcopy(self.payload)
        payload["s4"] = {}
        self.assertIsNone(parse_sensor_scan_packet(payload))

    def test_rejects_incomplete_duplicate_or_spare_sensor(self) -> None:
        incomplete = copy.deepcopy(self.payload)
        incomplete["readings"].pop()
        self.assertIsNone(parse_sensor_scan_packet(incomplete))

        duplicate = copy.deepcopy(self.payload)
        duplicate["readings"][2]["sensor_id"] = "s2"
        self.assertIsNone(parse_sensor_scan_packet(duplicate))

        spare = copy.deepcopy(self.payload)
        spare["readings"][2]["sensor_id"] = "s4"
        self.assertIsNone(parse_sensor_scan_packet(spare))

    def test_rejects_inconsistent_reading_values(self) -> None:
        cases = []
        invalid_with_distance = copy.deepcopy(self.payload)
        invalid_with_distance["readings"][0]["valid"] = False
        cases.append(invalid_with_distance)

        valid_without_distance = copy.deepcopy(self.payload)
        valid_without_distance["readings"][0]["distance_mm"] = None
        cases.append(valid_without_distance)

        bad_time = copy.deepcopy(self.payload)
        bad_time["readings"][0]["sample_time_ms"] = 1.5
        cases.append(bad_time)

        extra_field = copy.deepcopy(self.payload)
        extra_field["readings"][0]["model"] = "rcwl-1601"
        cases.append(extra_field)

        for payload in cases:
            with self.subTest(payload=payload):
                self.assertIsNone(parse_sensor_scan_packet(payload))

    def test_rejects_malformed_or_non_json_input(self) -> None:
        for raw_packet in (b"{", b"\xff", [], None, json.dumps([])):
            with self.subTest(raw_packet=raw_packet):
                self.assertIsNone(parse_sensor_scan_packet(raw_packet))


if __name__ == "__main__":
    unittest.main()
