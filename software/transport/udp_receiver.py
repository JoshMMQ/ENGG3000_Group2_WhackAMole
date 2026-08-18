"""UDP packet receiver for the Whack-a-Mole telemetry stream."""

from __future__ import annotations

import socket
from typing import Optional

from .packet import TelemetryPacket, parse_telemetry_packet

DEFAULT_PORT = 4210          # must match ESP32 sketch's UDP_PORT
BUFFER_SIZE = 1024


def receive_packet(
    sock: socket.socket, buffer_size: int = BUFFER_SIZE
) -> tuple[Optional[TelemetryPacket], Optional[tuple[str, int]]]:
    """Read one datagram and parse it, returning (packet, addr).

    Returns (None, None) if no packet is available (non-blocking socket)
    or the payload failed validation.
    """

    try:
        data, addr = sock.recvfrom(buffer_size)
    except OSError:
        return None, None
    return parse_telemetry_packet(data), addr


def format_packet(packet: TelemetryPacket, sender_address: tuple[str, int]) -> str:
    """Format a decoded telemetry packet as a one-line diagnostic string."""

    readings = " ".join(
        f"{reading.sensor_id}={reading.distance_mm}mm" if reading.valid else f"{reading.sensor_id}=invalid"
        for reading in packet.readings
    )
    return f"[{sender_address[0]}] node={packet.node_id} seq={packet.sequence} {readings}"


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to all interfaces on this port to catch broadcast packets
    sock.bind(("", DEFAULT_PORT))

    print(f"Listening for UDP packets on port {DEFAULT_PORT}...")
    print("Waiting for box1 / box2 readings. Press Ctrl+C to stop.\n")

    latest_readings = {}  # e.g. {"box1": 45.2, "box2": 120.7}

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