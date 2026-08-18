"""Two-sensor (box1/box2) UDP position source using same-wall triangulation.

box1 and box2 sit on the same wall, baseline_m apart, both facing into the
play area and each reporting a straight-line (radial) distance to the
player. The player's position is the intersection of the two range circles.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Optional, Protocol

try:
    from .simulated_position import PhysicalPosition
except ImportError:
    from simulated_position import PhysicalPosition


DEFAULT_PORT = 4210


class DatagramSocket(Protocol):
    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        ...

    def close(self) -> None:
        ...


def parse_box_reading(data: bytes) -> Optional[tuple[str, float]]:
    """Parse a 'box_id,distance_cm' UDP payload from an ESP32 sensor box."""

    try:
        message = data.decode("utf-8", errors="ignore").strip()
        box_id, distance_str = message.split(",")
        distance_cm = float(distance_str)
    except ValueError:
        return None
    if not isfinite(distance_cm) or distance_cm < 0:
        return None
    return box_id, distance_cm


@dataclass(frozen=True)
class WallTriangulationMapper:
    """Locate a player from two same-wall ultrasonic ranges.

    box1 is treated as the origin (0, 0) and box2 as (baseline_m, 0) along
    the wall. x is position along the wall, y is depth into the play area.
    """

    baseline_m: float = 1.5
    depth_m: float = 1.4

    def __post_init__(self) -> None:
        if self.baseline_m <= 0:
            raise ValueError("baseline_m must be positive")
        if self.depth_m <= 0:
            raise ValueError("depth_m must be positive")

    def position_for_ranges(
        self, box1_distance_m: float, box2_distance_m: float
    ) -> Optional[PhysicalPosition]:
        """Return the (x, y) intersection of the two range circles, if any."""

        r1, r2, d = box1_distance_m, box2_distance_m, self.baseline_m
        if r1 <= 0 or r2 <= 0:
            return None
        if r1 + r2 < d or abs(r1 - r2) > d:
            return None

        x = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
        y_squared = r1 * r1 - x * x
        if y_squared < 0:
            return None
        y = sqrt(y_squared)

        clamped_x = max(0.0, min(x, d))
        clamped_y = max(0.0, min(y, self.depth_m))
        return clamped_x, clamped_y


class BoxPositionSource:
    """Track the player's physical position from box1/box2 UDP telemetry."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        mapper: Optional[WallTriangulationMapper] = None,
        sock: Optional[DatagramSocket] = None,
    ) -> None:
        self._mapper = mapper or WallTriangulationMapper()
        self._latest_position: PhysicalPosition = (
            self._mapper.baseline_m / 2.0,
            self._mapper.depth_m / 2.0,
        )
        self._box1_distance_m: Optional[float] = None
        self._box2_distance_m: Optional[float] = None
        self._owns_socket = sock is None
        if sock is None:
            active_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            active_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            active_socket.bind((host, port))
            active_socket.setblocking(False)
            self._socket: DatagramSocket = active_socket
        else:
            self._socket = sock

    @property
    def latest_position(self) -> PhysicalPosition:
        return self._latest_position

    def poll_position(self) -> PhysicalPosition:
        """Drain all pending datagrams and refresh the position from box1/box2."""

        while True:
            try:
                data, _ = self._socket.recvfrom(1024)
            except OSError:
                break
            reading = parse_box_reading(data)
            if reading is None:
                continue
            box_id, distance_cm = reading
            distance_m = distance_cm / 100.0
            if box_id == "box1":
                self._box1_distance_m = distance_m
            elif box_id == "box2":
                self._box2_distance_m = distance_m

        if self._box1_distance_m is not None and self._box2_distance_m is not None:
            position = self._mapper.position_for_ranges(self._box1_distance_m, self._box2_distance_m)
            if position is not None:
                self._latest_position = position

        return self._latest_position

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()


class SingleBoxPositionSource:
    """Track player depth from one ultrasonic sensor box (no lateral fix).

    A single sensor can only report a straight-line distance from the wall,
    so x is held fixed at centre_x_m and only y (depth from the wall) moves.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        box_id: str = "box1",
        centre_x_m: float = 0.75,
        max_depth_m: float = 2.0,
        sock: Optional[DatagramSocket] = None,
    ) -> None:
        if max_depth_m <= 0:
            raise ValueError("max_depth_m must be positive")
        self._box_id = box_id
        self._centre_x_m = centre_x_m
        self._max_depth_m = max_depth_m
        self._latest_position: PhysicalPosition = (centre_x_m, max_depth_m / 2.0)
        self._owns_socket = sock is None
        if sock is None:
            active_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            active_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            active_socket.bind((host, port))
            active_socket.setblocking(False)
            self._socket: DatagramSocket = active_socket
        else:
            self._socket = sock

    @property
    def latest_position(self) -> PhysicalPosition:
        return self._latest_position

    def poll_position(self) -> PhysicalPosition:
        """Drain all pending datagrams and refresh depth from the sensor box."""

        while True:
            try:
                data, _ = self._socket.recvfrom(1024)
            except OSError:
                break
            reading = parse_box_reading(data)
            if reading is None:
                continue
            box_id, distance_cm = reading
            if box_id != self._box_id:
                continue
            distance_m = max(0.0, min(distance_cm / 100.0, self._max_depth_m))
            self._latest_position = (self._centre_x_m, distance_m)

        return self._latest_position

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()
