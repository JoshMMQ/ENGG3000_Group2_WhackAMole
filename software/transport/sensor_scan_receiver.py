"""Console diagnostic receiver for complete Version 3 sensor scans."""

from __future__ import annotations

import argparse
import socket
from typing import Optional

from software.game.sensor_scan import SensorId, SensorScan
from .sensor_scan_packet import parse_sensor_scan_packet
from .network_config import SENSOR_SCAN_BIND_HOST, SENSOR_SCAN_PORT


def format_sensor_scan(scan: SensorScan) -> str:
    """Format raw scan evidence without applying tracking decisions."""

    values = []
    for sensor_id in SensorId:
        reading = scan.reading_for(sensor_id)
        distance = (
            f"{reading.distance_mm:.1f}mm"
            if reading.distance_mm is not None
            else "invalid"
        )
        values.append(
            f"{sensor_id.value}={distance}@{reading.sample_time_ms}ms"
        )
    return f"cycle_id={scan.cycle_id} " + " ".join(values)


def receive_scans(
    host: str = SENSOR_SCAN_BIND_HOST,
    port: int = SENSOR_SCAN_PORT,
    *,
    count: int = 0,
) -> None:
    """Print valid complete scans; ``count=0`` continues until interrupted."""

    accepted = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        while count == 0 or accepted < count:
            packet, address = sock.recvfrom(4096)
            scan = parse_sensor_scan_packet(packet)
            if scan is None:
                print(f"rejected source={address[0]}:{address[1]}")
                continue
            print(format_sensor_scan(scan))
            accepted += 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print complete Version 3 S1/S2/S3 UDP scans."
    )
    parser.add_argument("--host", default=SENSOR_SCAN_BIND_HOST)
    parser.add_argument("--port", default=SENSOR_SCAN_PORT, type=int)
    parser.add_argument(
        "--count",
        default=0,
        type=int,
        help="Accepted scans to print; zero runs until interrupted.",
    )
    args = parser.parse_args(argv)
    receive_scans(args.host, args.port, count=max(0, args.count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
