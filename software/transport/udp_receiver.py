"""
Python UDP Receiver - Whack-a-Mole Sensor Test
-------------------------------------------------
Listens for UDP broadcast packets from both ESP32 boxes and
prints the distance readings. This is a standalone test to
confirm the wireless link works before wiring this into the
pygame game loop.

Message format expected from ESP32: "box1,123.4"
"""

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
            data, addr = sock.recvfrom(BUFFER_SIZE)
            message = data.decode("utf-8", errors="ignore").strip()

            try:
                box_id, distance_str = message.split(",")
                distance = float(distance_str)
                latest_readings[box_id] = distance

                print(f"From {addr[0]} | {box_id}: {distance:.1f} cm")

            except ValueError:
                print(f"Malformed packet from {addr[0]}: {message}")

    except KeyboardInterrupt:
        print("\nStopping listener.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()