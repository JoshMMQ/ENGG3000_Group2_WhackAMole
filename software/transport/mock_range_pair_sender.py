"""Hardware-free sender for the V2 paired-range gameplay path."""

from __future__ import annotations

import argparse
import json
import socket
import time
from math import cos, hypot, pi, sin
from typing import Optional

from .udp_receiver import DEFAULT_PORT


DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_INTERVAL_S = 0.07
DEFAULT_COUNT = 1000
DEFAULT_PAIR_SKEW_MS = 35.0
LEFT_SENSOR_POSITION_M = (0.0, 0.10)
RIGHT_SENSOR_POSITION_M = (1.50, 0.10)


def ranges_for_position(x_m: float, y_m: float) -> tuple[float, float]:
    """Return ideal left/right millimetre ranges for a world position."""

    left_mm = (
        hypot(x_m - LEFT_SENSOR_POSITION_M[0], y_m - LEFT_SENSOR_POSITION_M[1])
        * 1000.0
    )
    right_mm = (
        hypot(x_m - RIGHT_SENSOR_POSITION_M[0], y_m - RIGHT_SENSOR_POSITION_M[1])
        * 1000.0
    )
    return left_mm, right_mm


def simulated_position(cycle_id: int) -> tuple[float, float]:
    """Move around the playable field while staying clear of the dead zone."""

    angle = (2.0 * pi * cycle_id) / 120.0
    return 0.75 + 0.55 * sin(angle), 1.30 + 0.45 * cos(angle)


def build_range_pair_payload(
    cycle_id: int,
    x_m: float,
    y_m: float,
    *,
    pair_skew_ms: float = DEFAULT_PAIR_SKEW_MS,
    valid: bool = True,
) -> dict:
    """Build one V2 packet from an ideal target coordinate."""

    left_mm, right_mm = ranges_for_position(x_m, y_m)
    return {
        "version": 2,
        "type": "range_pair",
        "cycle_id": cycle_id,
        "left_mm": round(left_mm, 3) if valid else None,
        "right_mm": round(right_mm, 3) if valid else None,
        "left_valid": valid,
        "right_valid": valid,
        "pair_skew_ms": pair_skew_ms,
    }


def encode_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def send_mock_packets(
    target_host: str = DEFAULT_TARGET_HOST,
    target_port: int = DEFAULT_PORT,
    count: int = DEFAULT_COUNT,
    interval_s: float = DEFAULT_INTERVAL_S,
    *,
    fixed_position: Optional[tuple[float, float]] = None,
    include_invalid: bool = False,
) -> None:
    """Send V2 pairs suitable for driving the game cursor."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for cycle_id in range(count):
            x_m, y_m = fixed_position or simulated_position(cycle_id)
            payload = build_range_pair_payload(cycle_id, x_m, y_m)
            sock.sendto(encode_payload(payload), (target_host, target_port))

            if include_invalid and cycle_id == count // 2:
                invalid = build_range_pair_payload(cycle_id + count, x_m, y_m, valid=False)
                sock.sendto(encode_payload(invalid), (target_host, target_port))

            if cycle_id < count - 1:
                time.sleep(interval_s)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send mock V2 paired ranges to the game.")
    parser.add_argument("--host", default=DEFAULT_TARGET_HOST, help="Game host.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Game UDP port.")
    parser.add_argument("--count", default=DEFAULT_COUNT, type=int, help="Number of pairs to send.")
    parser.add_argument(
        "--interval",
        default=DEFAULT_INTERVAL_S,
        type=float,
        help="Seconds between pairs.",
    )
    parser.add_argument("--x", type=float, help="Fixed world x in metres; requires --y.")
    parser.add_argument("--y", type=float, help="Fixed world y in metres; requires --x.")
    parser.add_argument("--include-invalid", action="store_true")
    args = parser.parse_args(argv)

    if (args.x is None) != (args.y is None):
        parser.error("--x and --y must be supplied together")
    fixed_position = None if args.x is None else (args.x, args.y)
    send_mock_packets(
        target_host=args.host,
        target_port=args.port,
        count=max(0, args.count),
        interval_s=max(0.0, args.interval),
        fixed_position=fixed_position,
        include_invalid=args.include_invalid,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
