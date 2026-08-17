"""Non-blocking V2 paired-range input and two-dimensional triangulation."""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, sqrt
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
# tracker.py weights one new position against two parts of the previous
# position. Keep that behaviour at the laptop-owned, post-triangulation
# boundary rather than filtering either range independently in firmware.
DEFAULT_FILTER_ALPHA = 1.0 / 3.0
DEFAULT_MIN_MOVEMENT_M = 0.005
DEFAULT_STABLE_SAMPLE_COUNT = 3
MIN_RANGE_MM = 20.0
# The firmware deliberately accepts echoes beyond the approximately 2.42 m
# maximum planar range needed by the tracked footprint. Geometry, not this
# tolerance ceiling, decides whether a paired position belongs to the game.
MAX_RANGE_MM = 3000.0
# Allow only floating-point round-off at an exact footprint boundary. This is
# not a physical margin: a position even 0.1 mm beyond the footprint is rejected.
FOOTPRINT_NUMERICAL_EPSILON_M = 1e-9

logger = logging.getLogger(__name__)


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
) -> Optional[PhysicalPosition]:
    """Triangulate a pair and reject positions outside the tracked footprint."""

    left = _number(left_mm)
    right = _number(right_mm)
    if left is None or right is None:
        return None
    if not MIN_RANGE_MM <= left <= MAX_RANGE_MM:
        return None
    if not MIN_RANGE_MM <= right <= MAX_RANGE_MM:
        return None
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
    if not (
        -FOOTPRINT_NUMERICAL_EPSILON_M
        <= x_m
        <= TRACKED_WIDTH_M + FOOTPRINT_NUMERICAL_EPSILON_M
    ):
        return None
    if not (
        -FOOTPRINT_NUMERICAL_EPSILON_M
        <= y_m
        <= TRACKED_DEPTH_M + FOOTPRINT_NUMERICAL_EPSILON_M
    ):
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
        min_movement_m: float = DEFAULT_MIN_MOVEMENT_M,
        stable_sample_count: int = DEFAULT_STABLE_SAMPLE_COUNT,
        sock: Optional[DatagramSocket] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isfinite(max_pair_skew_ms) or max_pair_skew_ms < 0:
            raise ValueError("max_pair_skew_ms must be non-negative")
        if not isfinite(stale_after_s) or stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        if not isfinite(filter_alpha) or not 0 < filter_alpha <= 1:
            raise ValueError("filter_alpha must be in (0, 1]")
        if not isfinite(min_movement_m) or min_movement_m < 0:
            raise ValueError("min_movement_m must be non-negative")
        if (
            isinstance(stable_sample_count, bool)
            or not isinstance(stable_sample_count, int)
            or stable_sample_count < 1
        ):
            raise ValueError("stable_sample_count must be a positive integer")

        self._max_pair_skew_ms = max_pair_skew_ms
        self._stale_after_s = stale_after_s
        self._filter_alpha = filter_alpha
        self._min_movement_m = min_movement_m
        self._stable_sample_count = stable_sample_count
        self._stable_samples = 0
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
                logger.exception("UDP receive failed")
                self._mark_tracking_lost("udp_receive_error")
                return self._snapshot

            packet = parse_range_pair_packet(raw_packet)
            if packet is None:
                logger.warning("Dropped malformed or unsupported UDP packet raw=%r", raw_packet[:240])
                continue
            if self._last_cycle_id is not None and packet.cycle_id <= self._last_cycle_id:
                logger.debug(
                    "Ignored old/duplicate pair cycle_id=%s latest_cycle_id=%s",
                    packet.cycle_id,
                    self._last_cycle_id,
                )
                continue

            self._last_cycle_id = packet.cycle_id
            self._last_packet_at_s = now
            self._accept_packet(packet)

        if (
            self._last_packet_at_s is not None
            and now - self._last_packet_at_s > self._stale_after_s
        ):
            self._mark_tracking_lost("stale_stream")
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
        ):
            logger.warning(
                "Rejected invalid pair cycle_id=%s left_mm=%s right_mm=%s "
                "left_valid=%s right_valid=%s",
                packet.cycle_id,
                packet.left_mm,
                packet.right_mm,
                packet.left_valid,
                packet.right_valid,
            )
            self._mark_tracking_lost("invalid_range")
            return
        if packet.pair_skew_ms > self._max_pair_skew_ms:
            logger.warning(
                "Rejected high-skew pair cycle_id=%s pair_skew_ms=%.3f maximum_ms=%.3f",
                packet.cycle_id,
                packet.pair_skew_ms,
                self._max_pair_skew_ms,
            )
            self._mark_tracking_lost("pair_skew")
            return

        position = triangulate_ranges(packet.left_mm, packet.right_mm)
        if position is None:
            logger.warning(
                "Rejected impossible/out-of-footprint geometry cycle_id=%s "
                "left_mm=%.3f right_mm=%.3f",
                packet.cycle_id,
                packet.left_mm,
                packet.right_mm,
            )
            self._mark_tracking_lost("invalid_geometry")
            return

        filtered = self._filter(position)
        if filtered[1] < PLAYABLE_MIN_Y_M:
            status = TrackingStatus.DEAD_ZONE
        else:
            status = TrackingStatus.PLAYABLE
            self._last_playable_position = filtered

        self._set_snapshot(TrackingSnapshot(
            status=status,
            world_position=filtered,
            cursor_position=self._last_playable_position,
            cycle_id=packet.cycle_id,
        ))
        logger.debug(
            "Accepted pair cycle_id=%s left_mm=%.3f right_mm=%.3f skew_ms=%.3f "
            "raw_x_m=%.4f raw_y_m=%.4f filtered_x_m=%.4f filtered_y_m=%.4f status=%s",
            packet.cycle_id,
            packet.left_mm,
            packet.right_mm,
            packet.pair_skew_ms,
            position[0],
            position[1],
            filtered[0],
            filtered[1],
            status.value,
        )

    def _filter(self, position: PhysicalPosition) -> PhysicalPosition:
        if self._filtered_position is None:
            self._filtered_position = position
            return self._filtered_position

        movement_m = hypot(
            position[0] - self._filtered_position[0],
            position[1] - self._filtered_position[1],
        )
        if movement_m < self._min_movement_m:
            self._stable_samples += 1
            if self._stable_samples < self._stable_sample_count:
                return self._filtered_position
        else:
            self._stable_samples = 0

        # Once a small change has remained stable for the configured number of
        # samples, accept it and begin a fresh stability window. Larger moves
        # are accepted immediately, matching tracker.py's responsiveness.
        self._stable_samples = 0
        alpha = self._filter_alpha
        self._filtered_position = (
            alpha * position[0] + (1.0 - alpha) * self._filtered_position[0],
            alpha * position[1] + (1.0 - alpha) * self._filtered_position[1],
        )
        return self._filtered_position

    def _mark_tracking_lost(self, reason: str) -> None:
        # tracker.py starts a new stability window when an object disappears;
        # an invalid or stale V2 pair is the equivalent event in this pipeline.
        self._stable_samples = 0
        if self._snapshot.status != TrackingStatus.TRACKING_LOST:
            logger.warning(
                "Tracking lost reason=%s cycle_id=%s cursor_x_m=%.4f cursor_y_m=%.4f",
                reason,
                self._last_cycle_id,
                self._last_playable_position[0],
                self._last_playable_position[1],
            )
        self._set_snapshot(TrackingSnapshot(
            status=TrackingStatus.TRACKING_LOST,
            world_position=None,
            cursor_position=self._last_playable_position,
            cycle_id=self._last_cycle_id,
        ))

    def _set_snapshot(self, snapshot: TrackingSnapshot) -> None:
        previous_status = self._snapshot.status
        self._snapshot = snapshot
        if snapshot.status != previous_status:
            logger.info(
                "Tracking state changed from=%s to=%s cycle_id=%s",
                previous_status.value,
                snapshot.status.value,
                snapshot.cycle_id,
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
