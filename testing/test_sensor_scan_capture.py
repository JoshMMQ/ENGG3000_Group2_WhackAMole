import csv
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest

from software.game.sensor_scan import SensorId, SensorScan
from software.transport.mock_sensor_scan_sender import (
    build_sensor_scan_payload,
    encode_payload,
    send_mock_scans,
)
from software.transport.sensor_scan_capture import (
    CaptureMetadata,
    format_capture_summary,
    main,
    receive_complete_scans,
    summarize_scans,
    write_capture_csv,
)
from software.transport.sensor_scan_packet import parse_sensor_scan_packet


class FakeSocket:
    def __init__(self, packets: list[bytes]) -> None:
        self._packets = list(packets)

    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        del buffer_size
        if not self._packets:
            raise TimeoutError
        return self._packets.pop(0), ("127.0.0.1", 5006)


def scan_for(
    cycle_id: int,
    distances_mm: tuple[float | None, float | None, float | None],
) -> SensorScan:
    scan = parse_sensor_scan_packet(
        build_sensor_scan_payload(cycle_id, distances_mm)
    )
    if scan is None:
        raise AssertionError("test fixture did not produce a valid scan")
    return scan


class SensorScanCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = CaptureMetadata(
            sensor_under_test=SensorId.S2,
            known_distance_mm=500,
            captured_at_utc="2026-08-17T04:00:00+00:00",
            run_label="s2-flat-board-500mm",
        )

    def test_receive_collects_complete_scans_and_counts_rejections(self) -> None:
        socket = FakeSocket(
            [
                b"not-json",
                encode_payload(build_sensor_scan_payload(10)),
                encode_payload(build_sensor_scan_payload(11)),
            ]
        )

        scans, rejected_count = receive_complete_scans(socket, 2)

        self.assertEqual([scan.cycle_id for scan in scans], [10, 11])
        self.assertEqual(rejected_count, 1)

    def test_receive_requires_positive_count_and_propagates_timeout(self) -> None:
        with self.assertRaises(ValueError):
            receive_complete_scans(FakeSocket([]), 0)
        with self.assertRaises(TimeoutError):
            receive_complete_scans(FakeSocket([]), 1)

    def test_receive_collects_real_local_udp_mock_scan(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1.0)
            port = receiver.getsockname()[1]

            send_mock_scans(target_port=port, count=1, interval_s=0.0)
            scans, rejected_count = receive_complete_scans(receiver, 1)

        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0].cycle_id, 0)
        self.assertEqual(rejected_count, 0)

    def test_summary_reports_validity_distribution_gaps_and_duplicates(self) -> None:
        scans = [
            scan_for(10, (None, 490.0, 900.0)),
            scan_for(12, (700.0, 510.0, None)),
            scan_for(12, (None, 530.0, None)),
        ]

        summary = summarize_scans(scans)

        self.assertEqual(summary.scan_count, 3)
        self.assertEqual(summary.first_cycle_id, 10)
        self.assertEqual(summary.last_cycle_id, 12)
        self.assertEqual(summary.missing_cycle_count, 1)
        self.assertEqual(summary.duplicate_cycle_count, 1)
        self.assertEqual(summary.sensor_stats[SensorId.S1].valid_count, 1)
        self.assertEqual(summary.sensor_stats[SensorId.S2].median_mm, 510.0)
        self.assertEqual(summary.sensor_stats[SensorId.S2].minimum_mm, 490.0)
        self.assertEqual(summary.sensor_stats[SensorId.S2].maximum_mm, 530.0)
        self.assertEqual(summary.sensor_stats[SensorId.S3].valid_count, 1)

        formatted = format_capture_summary(summary, self.metadata)
        self.assertIn("captured=3 cycles=10-12 missing=1 duplicates=1", formatted)
        self.assertIn("s2 valid=3/3 (100.0%)", formatted)
        self.assertIn("median=510.0mm error=+10.0mm", formatted)
        self.assertNotIn("median=700.0mm error=", formatted)

    def test_empty_summary_has_explicit_no_measurement_values(self) -> None:
        formatted = format_capture_summary(summarize_scans([]), self.metadata)

        self.assertIn("captured=0 cycles=None-None", formatted)
        self.assertIn("s1 valid=0/0 (0.0%) median=none", formatted)

    def test_csv_preserves_raw_values_metadata_and_refuses_overwrite(self) -> None:
        scans = [scan_for(4, (900.0, None, 1100.0))]
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "capture.csv"

            write_capture_csv(output_path, scans, self.metadata)

            with output_path.open(newline="", encoding="utf-8") as capture_file:
                rows = list(csv.DictReader(capture_file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["run_label"], "s2-flat-board-500mm")
            self.assertEqual(rows[0]["sensor_under_test"], "s2")
            self.assertEqual(rows[0]["known_distance_mm"], "500.0")
            self.assertEqual(rows[0]["s1_distance_mm"], "900.0")
            self.assertEqual(rows[0]["s2_distance_mm"], "")
            self.assertEqual(rows[0]["s2_valid"], "False")
            self.assertEqual(rows[0]["scan_span_ms"], "70")

            with self.assertRaises(FileExistsError):
                write_capture_csv(output_path, scans, self.metadata)

    def test_metadata_rejects_invalid_ground_truth(self) -> None:
        for known_distance_mm in (0, -1, float("nan"), True):
            with self.subTest(known_distance_mm=known_distance_mm):
                with self.assertRaises(ValueError):
                    CaptureMetadata(
                        SensorId.S1,
                        known_distance_mm,
                        "2026-08-17T04:00:00+00:00",
                    )

    def test_cli_refuses_existing_output_before_opening_socket(self) -> None:
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "existing.csv"
            output_path.touch()

            result = main(
                [
                    "--sensor",
                    "s1",
                    "--known-distance-mm",
                    "500",
                    "--output",
                    str(output_path),
                ]
            )

        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
