"""UDP-backed position source for ESP32 fake telemetry."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Optional, Protocol

from .simulated_position import PhysicalPosition
from software.transport.udp_receiver import DEFAULT_PORT, receive_packet


class DatagramSocket(Protocol):
    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class DistanceAxisMapper:
    """Map a single distance reading onto one play-area axis."""

    min_distance_mm: int = 500
    max_distance_mm: int = 2500
    play_area_width_m: float = 3.0
    fixed_y_m: float = 1.5

    def __post_init__(self) -> None:
        if self.min_distance_mm >= self.max_distance_mm:
            raise ValueError("min_distance_mm must be less than max_distance_mm")
        if self.play_area_width_m <= 0:
            raise ValueError("play_area_width_m must be positive")

    def position_for_distance(self, distance_mm: int) -> PhysicalPosition:
        clamped = max(self.min_distance_mm, min(distance_mm, self.max_distance_mm))
        ratio = (clamped - self.min_distance_mm) / (self.max_distance_mm - self.min_distance_mm)
        return ratio * self.play_area_width_m, self.fixed_y_m


class UdpPositionSource:
    """Read ESP32 telemetry packets and expose the latest physical position."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        axis_mapper: Optional[DistanceAxisMapper] = None,
        sock: Optional[DatagramSocket] = None,
    ) -> None:
        self._axis_mapper = axis_mapper or DistanceAxisMapper()
        self._latest_position: PhysicalPosition = (
            self._axis_mapper.play_area_width_m / 2.0,
            self._axis_mapper.fixed_y_m,
        )
        self._owns_socket = sock is None
        if sock is None:
            active_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            active_socket.bind((host, port))
            active_socket.setblocking(False)
            self._socket: DatagramSocket = active_socket
        else:
            self._socket = sock

    @property
    def latest_position(self) -> PhysicalPosition:
        return self._latest_position

    def poll_position(self) -> PhysicalPosition:
        packet, _ = receive_packet(self._socket)
        if packet is None:
            return self._latest_position

        for reading in packet.readings:
            if reading.valid and reading.distance_mm is not None:
                self._latest_position = self._axis_mapper.position_for_distance(reading.distance_mm)
                break

        return self._latest_position

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()
