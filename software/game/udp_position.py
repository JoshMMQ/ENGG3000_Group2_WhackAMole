"""Non-blocking V2 paired-range input and two-dimensional triangulation."""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any, Callable, Optional, Protocol

from .simulated_position import PhysicalPosition
from software.transport.udp_receiver import DEFAULT_PORT


SUPPORTED_RANGE_PAIR_VERSION = 2
RANGE_PAIR_TYPE = "range_pair"
LEFT_SENSOR_POSITION_M = (0.0, 0.10)
RIGHT_SENSOR_POSITION_M = (1.50, 0.10)
TRACKED_WIDTH_M = 1.50
TRACKED_DEPTH_M = 2.00
PLAYABLE_MIN_Y_M = 0.60
DEFAULT_MAX_PAIR_SKEW_MS = 40.0
DEFAULT_STALE_AFTER_S = 0.50
DEFAULT_FILTER_ALPHA = 0.65
MIN_RANGE_MM = 20.0
MAX_RANGE_MM = 3000.0


class DatagramSocket(Protocol):
    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        ...

    def close(self) -> None:
        ...


class TrackingStatus(str, Enum):
    """State produced by the V2 paired-range tracking pipeline."""

    WAITING = "waiting"
    PLAYABLE = "playable"
    DEAD_ZONE = "dead_zone"
    TRACKING_LOST = "tracking_lost"


@dataclass(frozen=True)
class RangePairPacket:
    """One time-matched left/right range pair from the wireless host."""

    version: int
    packet_type: str
    cycle_id: int
    left_mm: Optional[float]
    right_mm: Optional[float]
    left_valid: bool
    right_valid: bool
    pair_skew_ms: float


@dataclass(frozen=True)
class TrackingSnapshot:
    """Latest tracking state plus the safe cursor position to render."""

    status: TrackingStatus
    world_position: Optional[PhysicalPosition]
    cursor_position: PhysicalPosition
    cycle_id: Optional[int]


def parse_range_pair_packet(raw_packet: object) -> Optional[RangePairPacket]:
    """Parse one V2 JSON datagram, returning ``None`` for invalid input."""

    payload = _decode_json(raw_packet)
    if not isinstance(payload, dict):
        return None

    version = _integer(payload.get("version"))
    packet_type = payload.get("type")
    cycle_id = _integer(payload.get("cycle_id"))
    left_valid = payload.get("left_valid")
    right_valid = payload.get("right_valid")
    left_mm = _number(payload.get("left_mm"))
    right_mm = _number(payload.get("right_mm"))
    pair_skew_ms = _number(payload.get("pair_skew_ms"))

    if version != SUPPORTED_RANGE_PAIR_VERSION or packet_type != RANGE_PAIR_TYPE:
        return None
    if cycle_id is None or cycle_id < 0:
        return None
    if not isinstance(left_valid, bool) or not isinstance(right_valid, bool):
        return None
    if pair_skew_ms is None or pair_skew_ms < 0:
        return None
    if left_valid and (left_mm is None or left_mm <= 0):
        return None
    if right_valid and (right_mm is None or right_mm <= 0):
        return None
    if left_mm is not None and left_mm <= 0:
        return None
    if right_mm is not None and right_mm <= 0:
        return None

    return RangePairPacket(
        version=version,
        packet_type=packet_type,
        cycle_id=cycle_id,
        left_mm=left_mm,
        right_mm=right_mm,
        left_valid=left_valid,
        right_valid=right_valid,
        pair_skew_ms=pair_skew_ms,
    )


def triangulate_ranges(
    left_mm: float,
    right_mm: float,
    *,
    footprint_tolerance_m: float = 0.02,
) -> Optional[PhysicalPosition]:
    """Convert a valid paired range into the positive-root world position."""

    left = _number(left_mm)
    right = _number(right_mm)
    if left is None or right is None:
        return None
    if not MIN_RANGE_MM <= left <= MAX_RANGE_MM:
        return None
    if not MIN_RANGE_MM <= right <= MAX_RANGE_MM:
        return None
    if footprint_tolerance_m < 0:
        raise ValueError("footprint_tolerance_m must be non-negative")

    left_m = left / 1000.0
    right_m = right / 1000.0
    baseline_m = RIGHT_SENSOR_POSITION_M[0] - LEFT_SENSOR_POSITION_M[0]
    q_m = (left_m * left_m - right_m * right_m + baseline_m * baseline_m) / (
        2.0 * baseline_m
    )
    radicand = left_m * left_m - q_m * q_m
    if radicand < -1e-9:
        return None

    x_m = LEFT_SENSOR_POSITION_M[0] + q_m
    y_m = LEFT_SENSOR_POSITION_M[1] + sqrt(max(0.0, radicand))
    if not -footprint_tolerance_m <= x_m <= TRACKED_WIDTH_M + footprint_tolerance_m:
        return None
    if not -footprint_tolerance_m <= y_m <= TRACKED_DEPTH_M + footprint_tolerance_m:
        return None

    return (
        max(0.0, min(x_m, TRACKED_WIDTH_M)),
        max(0.0, min(y_m, TRACKED_DEPTH_M)),
    )


class UdpPositionSource:
    """Receive V2 range pairs and expose a safe, non-blocking cursor state."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        *,
        max_pair_skew_ms: float = DEFAULT_MAX_PAIR_SKEW_MS,
        stale_after_s: float = DEFAULT_STALE_AFTER_S,
        filter_alpha: float = DEFAULT_FILTER_ALPHA,
        sock: Optional[DatagramSocket] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isfinite(max_pair_skew_ms) or max_pair_skew_ms < 0:
            raise ValueError("max_pair_skew_ms must be non-negative")
        if not isfinite(stale_after_s) or stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        if not isfinite(filter_alpha) or not 0 < filter_alpha <= 1:
            raise ValueError("filter_alpha must be in (0, 1]")

        self._max_pair_skew_ms = max_pair_skew_ms
        self._stale_after_s = stale_after_s
        self._filter_alpha = filter_alpha
        self._clock = clock
        self._last_packet_at_s: Optional[float] = None
        self._last_cycle_id: Optional[int] = None
        self._filtered_position: Optional[PhysicalPosition] = None
        self._last_playable_position: PhysicalPosition = (0.75, 1.30)
        self._snapshot = TrackingSnapshot(
            status=TrackingStatus.WAITING,
            world_position=None,
            cursor_position=self._last_playable_position,
            cycle_id=None,
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
        """Return the last playable position retained for cursor rendering."""

        return self._last_playable_position

    @property
    def tracking_snapshot(self) -> TrackingSnapshot:
        return self._snapshot

    def poll(self, now_s: Optional[float] = None) -> TrackingSnapshot:
        """Drain available packets without blocking and return the newest state."""

        now = self._clock() if now_s is None else float(now_s)
        while True:
            try:
                raw_packet, _ = self._socket.recvfrom(65535)
            except (BlockingIOError, TimeoutError):
                break
            except OSError:
                self._mark_tracking_lost()
                return self._snapshot

            packet = parse_range_pair_packet(raw_packet)
            if packet is None:
                continue
            if self._last_cycle_id is not None and packet.cycle_id <= self._last_cycle_id:
                continue

            self._last_cycle_id = packet.cycle_id
            self._last_packet_at_s = now
            self._accept_packet(packet)

        if (
            self._last_packet_at_s is not None
            and now - self._last_packet_at_s > self._stale_after_s
        ):
            self._mark_tracking_lost()
        return self._snapshot

    def poll_position(self) -> PhysicalPosition:
        """Compatibility helper returning the safe cursor position only."""

        return self.poll().cursor_position

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()

    def _accept_packet(self, packet: RangePairPacket) -> None:
        if (
            not packet.left_valid
            or not packet.right_valid
            or packet.left_mm is None
            or packet.right_mm is None
            or packet.pair_skew_ms > self._max_pair_skew_ms
        ):
            self._mark_tracking_lost()
            return

        position = triangulate_ranges(packet.left_mm, packet.right_mm)
        if position is None:
            self._mark_tracking_lost()
            return

        filtered = self._filter(position)
        if filtered[1] < PLAYABLE_MIN_Y_M:
            status = TrackingStatus.DEAD_ZONE
        else:
            status = TrackingStatus.PLAYABLE
            self._last_playable_position = filtered

        self._snapshot = TrackingSnapshot(
            status=status,
            world_position=filtered,
            cursor_position=self._last_playable_position,
            cycle_id=packet.cycle_id,
        )

    def _filter(self, position: PhysicalPosition) -> PhysicalPosition:
        if self._filtered_position is None:
            self._filtered_position = position
        else:
            alpha = self._filter_alpha
            self._filtered_position = (
                alpha * position[0] + (1.0 - alpha) * self._filtered_position[0],
                alpha * position[1] + (1.0 - alpha) * self._filtered_position[1],
            )
        return self._filtered_position

    def _mark_tracking_lost(self) -> None:
        self._snapshot = TrackingSnapshot(
            status=TrackingStatus.TRACKING_LOST,
            world_position=None,
            cursor_position=self._last_playable_position,
            cycle_id=self._last_cycle_id,
        )


def _decode_json(raw_packet: object) -> Any:
    if isinstance(raw_packet, bytes):
        try:
            return json.loads(raw_packet.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    if isinstance(raw_packet, str):
        try:
            return json.loads(raw_packet)
        except json.JSONDecodeError:
            return None
    if isinstance(raw_packet, dict):
        return raw_packet
    return None


def _number(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _integer(value: object) -> Optional[int]:
    number = _number(value)
    if number is None or number != int(number):
        return None
    return int(number)
