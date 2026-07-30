"""Mock UDP sender for laptop-side receiver testing."""

from __future__ import annotations

import argparse
import json
import socket
import time
from math import pi, sin
from typing import Optional

from .packet import SUPPORTED_PACKET_VERSION
from .udp_receiver import DEFAULT_PORT


DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_NODE_ID = "mock_esp32_01"
DEFAULT_SENSOR_ID = "simulated"
DEFAULT_INTERVAL_S = 0.25
DEFAULT_COUNT = 20


def build_mock_payload(
    sequence: int,
    sent_ms: int,
    distance_mm: int,
    valid: bool = True,
    node_id: str = DEFAULT_NODE_ID,
    sensor_id: str = DEFAULT_SENSOR_ID,
    battery_mv: int = 3700,
    status: str = "ok",
) -> dict:
    """Build one schema-valid fake ESP32 telemetry payload."""

    return {
        "v": SUPPORTED_PACKET_VERSION,
        "node_id": node_id,
        "seq": sequence,
        "sent_ms": sent_ms,
        "readings": [
            {
                "sensor_id": sensor_id,
                "distance_mm": distance_mm if valid else None,
                "valid": valid,
            }
        ],
        "battery_mv": battery_mv,
        "status": status,
    }


def simulated_distance_mm(sequence: int) -> int:
    """Return a repeatable fake distance between 500 mm and 2500 mm."""

    ratio = (sin((2.0 * pi * sequence) / 20.0) + 1.0) / 2.0
    return round(500 + ratio * 2000)


def encode_payload(payload: dict) -> bytes:
    """Encode a telemetry payload as compact JSON bytes."""

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def send_mock_packets(
    target_host: str = DEFAULT_TARGET_HOST,
    target_port: int = DEFAULT_PORT,
    count: int = DEFAULT_COUNT,
    interval_s: float = DEFAULT_INTERVAL_S,
    include_invalid: bool = False,
) -> None:
    """Send a short stream of fake ESP32 telemetry packets."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        start_ms = int(time.monotonic() * 1000)
        for sequence in range(count):
            sent_ms = int(time.monotonic() * 1000) - start_ms
            payload = build_mock_payload(
                sequence=sequence,
                sent_ms=sent_ms,
                distance_mm=simulated_distance_mm(sequence),
            )
            sock.sendto(encode_payload(payload), (target_host, target_port))

            if include_invalid and sequence == count // 2:
                sock.sendto(b"{bad json", (target_host, target_port))

            if sequence < count - 1:
                time.sleep(interval_s)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send mock ESP32 UDP telemetry packets.")
    parser.add_argument("--host", default=DEFAULT_TARGET_HOST, help="Receiver host.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Receiver UDP port.")
    parser.add_argument("--count", default=DEFAULT_COUNT, type=int, help="Number of packets to send.")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL_S, type=float, help="Seconds between packets.")
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Also send one malformed packet so the receiver drop path can be observed.",
    )
    args = parser.parse_args(argv)

    send_mock_packets(
        target_host=args.host,
        target_port=args.port,
        count=max(0, args.count),
        interval_s=max(0.0, args.interval),
        include_invalid=args.include_invalid,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
