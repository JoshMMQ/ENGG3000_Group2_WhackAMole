"""Capture raw Version 3 scans as calibration evidence and summarize them."""

from __future__ import annotations

import argparse
import csv
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from statistics import median
from typing import Optional, Protocol, Sequence

from software.game.sensor_scan import SensorId, SensorScan
from .sensor_scan_packet import parse_sensor_scan_packet
from .udp_receiver import DEFAULT_PORT


DEFAULT_CAPTURE_COUNT = 100
DEFAULT_TIMEOUT_S = 5.0

CSV_FIELDS = (
    "captured_at_utc",
    "run_label",
    "sensor_under_test",
    "known_distance_mm",
    "cycle_id",
    "s1_distance_mm",
    "s1_valid",
    "s1_sample_time_ms",
    "s2_distance_mm",
    "s2_valid",
    "s2_sample_time_ms",
    "s3_distance_mm",
    "s3_valid",
    "s3_sample_time_ms",
    "scan_span_ms",
)


class DatagramSocket(Protocol):
    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        ...


@dataclass(frozen=True)
class CaptureMetadata:
    """Ground truth and context repeated on every evidence row."""

    sensor_under_test: SensorId
    known_distance_mm: float
    captured_at_utc: str
    run_label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.sensor_under_test, SensorId):
            raise TypeError("sensor_under_test must be an active SensorId")
        if (
            isinstance(self.known_distance_mm, bool)
            or not isinstance(self.known_distance_mm, (int, float))
            or not isfinite(float(self.known_distance_mm))
            or float(self.known_distance_mm) <= 0.0
        ):
            raise ValueError("known_distance_mm must be finite and positive")
        if not isinstance(self.captured_at_utc, str) or not self.captured_at_utc:
            raise ValueError("captured_at_utc must be non-empty")
        if not isinstance(self.run_label, str):
            raise TypeError("run_label must be a string")
        object.__setattr__(self, "known_distance_mm", float(self.known_distance_mm))


@dataclass(frozen=True)
class SensorCaptureStats:
    """Validity and range distribution for one sensor in one capture."""

    valid_count: int
    total_count: int
    median_mm: Optional[float]
    minimum_mm: Optional[float]
    maximum_mm: Optional[float]

    @property
    def valid_rate(self) -> float:
        return self.valid_count / self.total_count if self.total_count else 0.0


@dataclass(frozen=True)
class ScanCaptureSummary:
    """Cycle continuity and per-sensor statistics for captured scans."""

    scan_count: int
    first_cycle_id: Optional[int]
    last_cycle_id: Optional[int]
    missing_cycle_count: int
    duplicate_cycle_count: int
    sensor_stats: dict[SensorId, SensorCaptureStats]


def receive_complete_scans(
    sock: DatagramSocket,
    count: int,
) -> tuple[list[SensorScan], int]:
    """Receive ``count`` valid-schema scans and count rejected datagrams."""

    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")

    scans: list[SensorScan] = []
    rejected_count = 0
    while len(scans) < count:
        packet, _ = sock.recvfrom(4096)
        scan = parse_sensor_scan_packet(packet)
        if scan is None:
            rejected_count += 1
            continue
        scans.append(scan)
    return scans, rejected_count


def summarize_scans(scans: Sequence[SensorScan]) -> ScanCaptureSummary:
    """Compute deterministic validity, range, duplicate, and cycle-gap facts."""

    cycle_ids = [scan.cycle_id for scan in scans]
    unique_cycle_ids = sorted(set(cycle_ids))
    duplicate_count = len(cycle_ids) - len(unique_cycle_ids)
    if unique_cycle_ids:
        first_cycle_id = unique_cycle_ids[0]
        last_cycle_id = unique_cycle_ids[-1]
        expected_count = last_cycle_id - first_cycle_id + 1
        missing_count = expected_count - len(unique_cycle_ids)
    else:
        first_cycle_id = None
        last_cycle_id = None
        missing_count = 0

    sensor_stats: dict[SensorId, SensorCaptureStats] = {}
    for sensor_id in SensorId:
        valid_distances = [
            reading.distance_mm
            for scan in scans
            for reading in (scan.reading_for(sensor_id),)
            if reading.valid and reading.distance_mm is not None
        ]
        sensor_stats[sensor_id] = SensorCaptureStats(
            valid_count=len(valid_distances),
            total_count=len(scans),
            median_mm=median(valid_distances) if valid_distances else None,
            minimum_mm=min(valid_distances) if valid_distances else None,
            maximum_mm=max(valid_distances) if valid_distances else None,
        )

    return ScanCaptureSummary(
        scan_count=len(scans),
        first_cycle_id=first_cycle_id,
        last_cycle_id=last_cycle_id,
        missing_cycle_count=missing_count,
        duplicate_cycle_count=duplicate_count,
        sensor_stats=sensor_stats,
    )


def format_capture_summary(
    summary: ScanCaptureSummary,
    metadata: CaptureMetadata,
) -> str:
    """Return a compact human-readable evidence summary."""

    lines = [
        f"captured={summary.scan_count} cycles={summary.first_cycle_id}-"
        f"{summary.last_cycle_id} missing={summary.missing_cycle_count} "
        f"duplicates={summary.duplicate_cycle_count}"
    ]
    for sensor_id in SensorId:
        stats = summary.sensor_stats[sensor_id]
        if stats.median_mm is None:
            distribution = "median=none min=none max=none"
        else:
            error = ""
            if sensor_id is metadata.sensor_under_test:
                error_mm = stats.median_mm - metadata.known_distance_mm
                error = f" error={error_mm:+.1f}mm"
            distribution = (
                f"median={stats.median_mm:.1f}mm{error} "
                f"min={stats.minimum_mm:.1f}mm max={stats.maximum_mm:.1f}mm"
            )
        lines.append(
            f"{sensor_id.value} valid={stats.valid_count}/{stats.total_count} "
            f"({stats.valid_rate:.1%}) {distribution}"
        )
    return "\n".join(lines)


def write_capture_csv(
    output_path: Path,
    scans: Sequence[SensorScan],
    metadata: CaptureMetadata,
) -> None:
    """Create a new evidence CSV without overwriting an existing capture."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for scan in scans:
            row: dict[str, object] = {
                "captured_at_utc": metadata.captured_at_utc,
                "run_label": metadata.run_label,
                "sensor_under_test": metadata.sensor_under_test.value,
                "known_distance_mm": metadata.known_distance_mm,
                "cycle_id": scan.cycle_id,
                "scan_span_ms": scan.sample_span_ms,
            }
            for sensor_id in SensorId:
                reading = scan.reading_for(sensor_id)
                row[f"{sensor_id.value}_distance_mm"] = (
                    reading.distance_mm if reading.distance_mm is not None else ""
                )
                row[f"{sensor_id.value}_valid"] = reading.valid
                row[f"{sensor_id.value}_sample_time_ms"] = reading.sample_time_ms
            writer.writerow(row)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture raw Version 3 scans for known-distance calibration."
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument("--count", default=DEFAULT_CAPTURE_COUNT, type=int)
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT_S, type=float)
    parser.add_argument(
        "--sensor",
        required=True,
        choices=[item.value for item in SensorId],
    )
    parser.add_argument("--known-distance-mm", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-label", default="")
    args = parser.parse_args(argv)

    if args.count < 1:
        parser.error("--count must be positive")
    if not isfinite(args.timeout) or args.timeout <= 0.0:
        parser.error("--timeout must be finite and positive")
    if args.output.exists():
        print(f"Refusing to overwrite existing capture: {args.output}", file=sys.stderr)
        return 2

    try:
        metadata = CaptureMetadata(
            sensor_under_test=SensorId(args.sensor),
            known_distance_mm=args.known_distance_mm,
            captured_at_utc=datetime.now(timezone.utc).isoformat(),
            run_label=args.run_label,
        )
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, args.port))
        sock.settimeout(args.timeout)
        try:
            scans, rejected_count = receive_complete_scans(sock, args.count)
        except TimeoutError:
            print(
                "Capture timed out before the requested complete-scan count; "
                "no CSV was written.",
                file=sys.stderr,
            )
            return 2

    try:
        write_capture_csv(args.output, scans, metadata)
    except FileExistsError:
        print(f"Refusing to overwrite existing capture: {args.output}", file=sys.stderr)
        return 2

    print(f"wrote={args.output} rejected_datagrams={rejected_count}")
    print(format_capture_summary(summarize_scans(scans), metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
