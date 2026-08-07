"""UDP receiver utilities for ESP32 telemetry packets."""

from __future__ import annotations

import argparse
import socket
import time
from typing import Optional, TextIO

from .packet import TelemetryPacket, parse_telemetry_packet


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5005
DEFAULT_BUFFER_SIZE = 4096
POLL_INTERVAL_S = 0.01
TWO_BOX_PORT = 4210


def receive_packet(
    sock: socket.socket,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> tuple[Optional[TelemetryPacket], Optional[tuple[str, int]]]:
    """Receive one UDP datagram and parse it into versioned telemetry."""

    try:
        data, address = sock.recvfrom(buffer_size)
    except BlockingIOError:
        return None, None
    return parse_telemetry_packet(data), address


def format_packet(packet: TelemetryPacket, address: tuple[str, int]) -> str:
    """Format telemetry as one readable receiver log line."""

    readings = ", ".join(
        f"{reading.sensor_id}={reading.distance_mm}mm valid={reading.valid}"
        for reading in packet.readings
    )
    return (
        f"{address[0]}:{address[1]} "
        f"node={packet.node_id} seq={packet.sequence} sent_ms={packet.sent_ms} "
        f"status={packet.status} battery_mv={packet.battery_mv} readings=[{readings}]"
    )


def parse_two_box_message(message: object) -> Optional[tuple[str, float]]:
    """Parse the laptop-hotspot two-box test format: ``box1,123.4``."""

    if isinstance(message, bytes):
        text = message.decode("utf-8", errors="ignore").strip()
    elif isinstance(message, str):
        text = message.strip()
    else:
        return None

    try:
        box_id, distance_text = text.split(",", maxsplit=1)
        distance_cm = float(distance_text)
    except ValueError:
        return None

    box_id = box_id.strip()
    if not box_id:
        return None
    return box_id, distance_cm


def run_receiver(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    output: Optional[TextIO] = None,
) -> None:
    """Listen for versioned JSON UDP telemetry forever and print valid packets."""

    active_output = output if output is not None else None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        sock.setblocking(False)
        _print(f"Listening for UDP telemetry on {host}:{port}", active_output)
        while True:
            packet, address = receive_packet(sock)
            if address is None:
                time.sleep(POLL_INTERVAL_S)
                continue
            if packet is None:
                _print(f"{address[0]}:{address[1]} invalid packet dropped", active_output)
                continue
            _print(format_packet(packet, address), active_output)


def run_two_box_receiver(
    host: str = DEFAULT_HOST,
    port: int = TWO_BOX_PORT,
    output: Optional[TextIO] = None,
) -> None:
    """Listen for the simple two-box laptop-hotspot test packets."""

    active_output = output if output is not None else None
    latest_readings: dict[str, float] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        _print(f"Listening for two-box UDP packets on {host}:{port}", active_output)
        _print("Waiting for box1 / box2 readings. Press Ctrl+C to stop.", active_output)

        while True:
            data, address = sock.recvfrom(DEFAULT_BUFFER_SIZE)
            reading = parse_two_box_message(data)
            if reading is None:
                _print(f"Malformed packet from {address[0]}: {data!r}", active_output)
                continue

            box_id, distance_cm = reading
            latest_readings[box_id] = distance_cm
            _print(f"From {address[0]} | {box_id}: {distance_cm:.1f} cm", active_output)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Listen for ESP32 UDP telemetry packets.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host/interface to bind.")
    parser.add_argument("--port", default=None, type=int, help="UDP port to bind.")
    parser.add_argument(
        "--mode",
        choices=("telemetry", "two-box"),
        default="telemetry",
        help="Packet format to listen for.",
    )
    args = parser.parse_args(argv)

    try:
        if args.mode == "two-box":
            run_two_box_receiver(host=args.host, port=args.port or TWO_BOX_PORT)
        else:
            run_receiver(host=args.host, port=args.port or DEFAULT_PORT)
    except KeyboardInterrupt:
        return 0
    return 0


def _print(message: str, output: Optional[TextIO]) -> None:
    if output is None:
        print(message, flush=True)
    else:
        print(message, file=output, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
