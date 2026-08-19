"""Hardware-free sender for the target Version 3 scan transport boundary."""

from __future__ import annotations

import argparse
import json
import socket
import time
from typing import Optional

from software.game.sensor_scan import SensorId
from .sensor_scan_packet import SENSOR_SCAN_TYPE, SENSOR_SCAN_VERSION
from .network_config import SENSOR_SCAN_PORT


DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_INTERVAL_S = 0.105
DEFAULT_COUNT = 1000
DEFAULT_SAMPLE_SPACING_MS = 35
DEFAULT_DISTANCES_MM = (900.0, 1100.0, 1300.0)


def build_sensor_scan_payload(
    cycle_id: int,
    distances_mm: tuple[Optional[float], Optional[float], Optional[float]] = (
        DEFAULT_DISTANCES_MM
    ),
    *,
    cycle_started_ms: Optional[int] = None,
    sample_spacing_ms: int = DEFAULT_SAMPLE_SPACING_MS,
) -> dict:
    """Build one complete S1/S2/S3 packet; ``None`` marks invalid acquisition."""

    if cycle_started_ms is None:
        cycle_started_ms = cycle_id * sample_spacing_ms * len(SensorId)

    readings = []
    for offset, (sensor_id, distance_mm) in enumerate(
        zip(SensorId, distances_mm, strict=True)
    ):
        readings.append(
            {
                "sensor_id": sensor_id.value,
                "distance_mm": distance_mm,
                "valid": distance_mm is not None,
                "sample_time_ms": cycle_started_ms
                + offset * sample_spacing_ms,
            }
        )

    return {
        "version": SENSOR_SCAN_VERSION,
        "type": SENSOR_SCAN_TYPE,
        "cycle_id": cycle_id,
        "readings": readings,
    }


def encode_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def send_mock_scans(
    target_host: str = DEFAULT_TARGET_HOST,
    target_port: int = SENSOR_SCAN_PORT,
    count: int = DEFAULT_COUNT,
    interval_s: float = DEFAULT_INTERVAL_S,
    *,
    distances_mm: tuple[Optional[float], Optional[float], Optional[float]] = (
        DEFAULT_DISTANCES_MM
    ),
) -> None:
    """Send complete scans for packet/parser diagnostics, not gameplay input."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for cycle_id in range(count):
            payload = build_sensor_scan_payload(cycle_id, distances_mm)
            sock.sendto(encode_payload(payload), (target_host, target_port))
            if cycle_id < count - 1:
                time.sleep(interval_s)


def _optional_distance(raw_value: str) -> Optional[float]:
    if raw_value.lower() in {"none", "invalid"}:
        return None
    value = float(raw_value)
    if value <= 0.0:
        raise argparse.ArgumentTypeError("distance must be positive or 'invalid'")
    return value


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send complete Version 3 S1/S2/S3 scans for diagnostics."
    )
    parser.add_argument("--host", default=DEFAULT_TARGET_HOST)
    parser.add_argument("--port", default=SENSOR_SCAN_PORT, type=int)
    parser.add_argument("--count", default=DEFAULT_COUNT, type=int)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL_S, type=float)
    parser.add_argument(
        "--s1-mm", default=DEFAULT_DISTANCES_MM[0], type=_optional_distance
    )
    parser.add_argument(
        "--s2-mm", default=DEFAULT_DISTANCES_MM[1], type=_optional_distance
    )
    parser.add_argument(
        "--s3-mm", default=DEFAULT_DISTANCES_MM[2], type=_optional_distance
    )
    args = parser.parse_args(argv)

    send_mock_scans(
        target_host=args.host,
        target_port=args.port,
        count=max(0, args.count),
        interval_s=max(0.0, args.interval),
        distances_mm=(args.s1_mm, args.s2_mm, args.s3_mm),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
