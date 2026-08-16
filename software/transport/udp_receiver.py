"""UDP packet receiver for the Whack-a-Mole telemetry stream."""

from __future__ import annotations

import socket
from typing import Optional, Tuple

from .packet import TelemetryPacket, parse_telemetry_packet

DEFAULT_PORT = 5005
BUFFER_SIZE = 4096


def receive_packet(sock: socket.socket) -> Tuple[Optional[TelemetryPacket], Optional[tuple[str, int]]]:
    """Receive one UDP datagram and decode it into a telemetry packet if valid."""

    try:
        data, addr = sock.recvfrom(BUFFER_SIZE)
    except (BlockingIOError, OSError):
        return None, None

    packet = parse_telemetry_packet(data)
    if packet is None:
        return None, addr
    return packet, addr


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DEFAULT_PORT))

    print(f"Listening for UDP packets on port {DEFAULT_PORT}...")
    print("Waiting for telemetry packets. Press Ctrl+C to stop.\n")

    try:
        while True:
            packet, addr = receive_packet(sock)
            if packet is None:
                print(f"Ignoring invalid packet from {addr}")
                continue

            readings = ", ".join(
                f"{reading.sensor_id}={reading.distance_mm}mm valid={reading.valid}"
                for reading in packet.readings
            )
            print(f"From {addr[0]} | node={packet.node_id} seq={packet.sequence} status={packet.status} readings=[{readings}]")
    except KeyboardInterrupt:
        print("\nStopping listener.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()