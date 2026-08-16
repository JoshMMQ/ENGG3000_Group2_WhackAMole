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
    play_area_height_m: float = 3.0
    fixed_x_m: float = 1.5
    fixed_y_m: float = 1.5

    def __post_init__(self) -> None:
        if self.min_distance_mm >= self.max_distance_mm:
            raise ValueError("min_distance_mm must be less than max_distance_mm")
        if self.play_area_width_m <= 0:
            raise ValueError("play_area_width_m must be positive")
        if self.play_area_height_m <= 0:
            raise ValueError("play_area_height_m must be positive")

    def position_for_distance(self, distance_mm: int, axis: str = "x") -> PhysicalPosition:
        normalized_axis = str(axis).strip().lower()
        if normalized_axis not in {"x", "y"}:
            raise ValueError("axis must be 'x' or 'y'")

        clamped = max(self.min_distance_mm, min(distance_mm, self.max_distance_mm))
        ratio = (clamped - self.min_distance_mm) / (self.max_distance_mm - self.min_distance_mm)

        if normalized_axis == "x":
            return ratio * self.play_area_width_m, self.fixed_y_m
        return self.fixed_x_m, ratio * self.play_area_height_m


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
            self._axis_mapper.fixed_x_m,
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

    def _axis_value_from_reading(self, reading) -> tuple[str, int] | None:
        if not reading.valid or reading.distance_mm is None:
            return None

        sensor_name = str(reading.sensor_id).strip().lower().replace("-", "_").replace(" ", "_")
        if sensor_name in {"x", "x_axis", "x_axis_sensor", "x_sensor", "horizontal", "left", "box1"}:
            return "x", reading.distance_mm
        if sensor_name in {"y", "y_axis", "y_axis_sensor", "y_sensor", "vertical", "top", "box2"}:
            return "y", reading.distance_mm
        if sensor_name.endswith("_x") or sensor_name.startswith("x_"):
            return "x", reading.distance_mm
        if sensor_name.endswith("_y") or sensor_name.startswith("y_"):
            return "y", reading.distance_mm
        return None

    def poll_position(self) -> PhysicalPosition:
        packet, _ = receive_packet(self._socket)
        if packet is None:
            return self._latest_position

        x_distance: Optional[int] = None
        y_distance: Optional[int] = None
        for reading in packet.readings:
            axis_value = self._axis_value_from_reading(reading)
            if axis_value is None:
                continue
            axis_name, distance_mm = axis_value
            if axis_name == "x":
                x_distance = distance_mm
            else:
                y_distance = distance_mm

        if x_distance is not None:
            x_position, _ = self._axis_mapper.position_for_distance(x_distance, axis="x")
        else:
            x_position = self._latest_position[0]

        if y_distance is not None:
            _, y_position = self._axis_mapper.position_for_distance(y_distance, axis="y")
        else:
            y_position = self._latest_position[1]

        if x_distance is None and y_distance is None:
            for reading in packet.readings:
                if reading.valid and reading.distance_mm is not None:
                    self._latest_position = self._axis_mapper.position_for_distance(reading.distance_mm)
                    return self._latest_position
            return self._latest_position

        self._latest_position = (x_position, y_position)
        return self._latest_position

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()
