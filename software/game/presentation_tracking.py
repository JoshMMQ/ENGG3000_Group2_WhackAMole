"""Temporary Version 3 three-sensor cursor source for presentation use only."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from math import exp, hypot, isfinite
import socket
from statistics import median
import time
from typing import Callable, Optional, Protocol

from software.transport.sensor_scan_packet import parse_sensor_scan_packet
from software.transport.udp_receiver import DEFAULT_PORT

from .sensor_scan import SensorId, SensorScan
from .simulated_position import PhysicalPosition
from .udp_position import TrackingStatus


PRESENTATION_COLUMN_X_M = {
    SensorId.S1: 0.233,
    SensorId.S2: 0.700,
    SensorId.S3: 1.167,
}
DEFAULT_TRACKED_DEPTH_M = 2.0
DEFAULT_CONFIRMATION_SCANS = 2
DEFAULT_STALE_AFTER_S = 0.50
DEFAULT_CURSOR_RESPONSE_RATE = 12.0
MAX_INTERPOLATION_STEP_S = 0.10
INITIAL_TARGET_POSITION_M = (PRESENTATION_COLUMN_X_M[SensorId.S2], 1.0)
PRESENTATION_MEDIAN_WINDOW = 3
SENSOR_ORDER = tuple(SensorId)

logger = logging.getLogger(__name__)


class DatagramSocket(Protocol):
    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class PresentationTrackingSnapshot:
    """Presentation target and diagnostics from the newest accepted scan."""

    status: TrackingStatus
    world_position: Optional[PhysicalPosition]
    cursor_position: PhysicalPosition
    cycle_id: Optional[int]
    scan: Optional[SensorScan]
    active_sensor: Optional[SensorId]
    candidate_sensor: Optional[SensorId]
    candidate_count: int
    filtered_distances_mm: tuple[Optional[float], ...]

    def filtered_distance_mm(self, sensor_id: SensorId) -> Optional[float]:
        return self.filtered_distances_mm[SENSOR_ORDER.index(sensor_id)]

    @property
    def diagnostic_lines(self) -> tuple[str, ...]:
        values = []
        for sensor_id in SENSOR_ORDER:
            reading = self.scan.reading_for(sensor_id) if self.scan else None
            if reading is None:
                raw_value = "waiting"
            elif not reading.valid or reading.distance_mm is None:
                raw_value = "invalid"
            else:
                raw_value = f"{reading.distance_mm:.1f}"
            filtered = self.filtered_distance_mm(sensor_id)
            filtered_value = "--" if filtered is None else f"{filtered:.1f}"
            values.append(
                f"{sensor_id.value.upper()}: raw={raw_value} mm  med3={filtered_value} mm"
            )

        active = self.active_sensor.value.upper() if self.active_sensor else "--"
        candidate = (
            self.candidate_sensor.value.upper() if self.candidate_sensor else "--"
        )
        if self.status is TrackingStatus.PLAYABLE:
            display_status = "TRACKING"
        elif self.status is TrackingStatus.WAITING:
            display_status = "WAITING"
        else:
            display_status = "HOLDING LAST TARGET"
        target_x, target_y = self.cursor_position
        return (
            *values,
            f"Active: {active}  Candidate: {candidate} ({self.candidate_count})",
            f"Target: x={target_x:.3f} m  y={target_y:.3f} m",
            f"Status: {display_status}",
        )


class PresentationTrackingSource:
    """Drain Version 3 scans and expose a temporary winner-based cursor target."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        *,
        confirmation_scans: int = DEFAULT_CONFIRMATION_SCANS,
        tracked_depth_m: float = DEFAULT_TRACKED_DEPTH_M,
        stale_after_s: float = DEFAULT_STALE_AFTER_S,
        sock: Optional[DatagramSocket] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            isinstance(confirmation_scans, bool)
            or not isinstance(confirmation_scans, int)
            or confirmation_scans < 1
        ):
            raise ValueError("confirmation_scans must be a positive integer")
        if not isfinite(tracked_depth_m) or tracked_depth_m <= 0.0:
            raise ValueError("tracked_depth_m must be finite and positive")
        if not isfinite(stale_after_s) or stale_after_s <= 0.0:
            raise ValueError("stale_after_s must be finite and positive")

        self._confirmation_scans = confirmation_scans
        self._tracked_depth_m = tracked_depth_m
        self._stale_after_s = stale_after_s
        self._clock = clock
        self._last_packet_at_s: Optional[float] = None
        self._last_cycle_id: Optional[int] = None
        self._active_sensor: Optional[SensorId] = None
        self._pending_sensor: Optional[SensorId] = None
        self._pending_count = 0
        self._last_target = INITIAL_TARGET_POSITION_M
        self._valid_distance_history = {
            sensor_id: deque(maxlen=PRESENTATION_MEDIAN_WINDOW)
            for sensor_id in SENSOR_ORDER
        }
        self._snapshot = PresentationTrackingSnapshot(
            status=TrackingStatus.WAITING,
            world_position=None,
            cursor_position=self._last_target,
            cycle_id=None,
            scan=None,
            active_sensor=None,
            candidate_sensor=None,
            candidate_count=0,
            filtered_distances_mm=(None, None, None),
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
    def tracking_snapshot(self) -> PresentationTrackingSnapshot:
        return self._snapshot

    def poll(self, now_s: Optional[float] = None) -> PresentationTrackingSnapshot:
        """Drain queued datagrams without blocking and return the newest state."""

        now = self._clock() if now_s is None else float(now_s)
        while True:
            try:
                raw_packet, _ = self._socket.recvfrom(65535)
            except (BlockingIOError, TimeoutError):
                break
            except OSError:
                logger.exception("Presentation UDP receive failed")
                self._hold_last_target(TrackingStatus.TRACKING_LOST)
                return self._snapshot

            scan = parse_sensor_scan_packet(raw_packet)
            if scan is None:
                logger.warning(
                    "Dropped malformed presentation scan raw=%r", raw_packet[:240]
                )
                continue
            if self._last_cycle_id is not None and scan.cycle_id <= self._last_cycle_id:
                logger.debug(
                    "Ignored old presentation scan cycle_id=%s latest_cycle_id=%s",
                    scan.cycle_id,
                    self._last_cycle_id,
                )
                continue

            self._last_cycle_id = scan.cycle_id
            self._last_packet_at_s = now
            self._accept_scan(scan)

        if (
            self._last_packet_at_s is not None
            and now - self._last_packet_at_s > self._stale_after_s
        ):
            self._hold_last_target(TrackingStatus.TRACKING_LOST)
        return self._snapshot

    def close(self) -> None:
        if self._owns_socket:
            self._socket.close()

    def _accept_scan(self, scan: SensorScan) -> None:
        self._record_valid_distances(scan)
        filtered_distances = self._filtered_distances()
        valid_readings = tuple(
            reading
            for reading in scan.readings
            if reading.valid and reading.distance_mm is not None
        )
        if not valid_readings:
            self._pending_sensor = None
            self._pending_count = 0
            self._snapshot = PresentationTrackingSnapshot(
                status=TrackingStatus.TRACKING_LOST,
                world_position=None,
                cursor_position=self._last_target,
                cycle_id=scan.cycle_id,
                scan=scan,
                active_sensor=self._active_sensor,
                candidate_sensor=None,
                candidate_count=0,
                filtered_distances_mm=filtered_distances,
            )
            return

        candidate_reading = min(
            valid_readings,
            key=lambda reading: (
                self._filtered_distance(reading.sensor_id),
                reading.sensor_id.value,
            ),
        )
        candidate_sensor = candidate_reading.sensor_id

        if self._active_sensor is None:
            self._active_sensor = candidate_sensor
            self._pending_sensor = None
            self._pending_count = 0
        elif candidate_sensor is self._active_sensor:
            self._pending_sensor = None
            self._pending_count = 0
        else:
            if candidate_sensor is self._pending_sensor:
                self._pending_count += 1
            else:
                self._pending_sensor = candidate_sensor
                self._pending_count = 1
            if self._pending_count >= self._confirmation_scans:
                self._active_sensor = candidate_sensor
                self._pending_sensor = None
                self._pending_count = 0

        active_reading = scan.reading_for(self._active_sensor)
        if active_reading.valid and active_reading.distance_mm is not None:
            active_distance_mm = self._filtered_distance(self._active_sensor)
            target_y_m = max(
                0.0,
                min(active_distance_mm / 1000.0, self._tracked_depth_m),
            )
            self._last_target = (
                PRESENTATION_COLUMN_X_M[self._active_sensor],
                target_y_m,
            )

        self._snapshot = PresentationTrackingSnapshot(
            status=TrackingStatus.PLAYABLE,
            world_position=self._last_target,
            cursor_position=self._last_target,
            cycle_id=scan.cycle_id,
            scan=scan,
            active_sensor=self._active_sensor,
            candidate_sensor=candidate_sensor,
            candidate_count=self._pending_count,
            filtered_distances_mm=filtered_distances,
        )

    def _record_valid_distances(self, scan: SensorScan) -> None:
        for reading in scan.readings:
            if reading.valid and reading.distance_mm is not None:
                self._valid_distance_history[reading.sensor_id].append(
                    reading.distance_mm
                )

    def _filtered_distance(self, sensor_id: SensorId) -> float:
        history = self._valid_distance_history[sensor_id]
        if not history:
            raise ValueError(f"no valid presentation history for {sensor_id.value}")
        return float(median(history))

    def _filtered_distances(self) -> tuple[Optional[float], ...]:
        return tuple(
            self._filtered_distance(sensor_id)
            if self._valid_distance_history[sensor_id]
            else None
            for sensor_id in SENSOR_ORDER
        )

    def _hold_last_target(self, status: TrackingStatus) -> None:
        self._snapshot = PresentationTrackingSnapshot(
            status=status,
            world_position=None,
            cursor_position=self._last_target,
            cycle_id=self._snapshot.cycle_id,
            scan=self._snapshot.scan,
            active_sensor=self._active_sensor,
            candidate_sensor=self._snapshot.candidate_sensor,
            candidate_count=self._pending_count,
            filtered_distances_mm=self._snapshot.filtered_distances_mm,
        )


def interpolate_position(
    render_position: PhysicalPosition,
    target_position: PhysicalPosition,
    delta_s: float,
    *,
    response_rate: float = DEFAULT_CURSOR_RESPONSE_RATE,
) -> PhysicalPosition:
    """Move the rendered cursor toward its target without frame-rate dependence."""

    render_x, render_y = _finite_position(render_position, "render_position")
    target_x, target_y = _finite_position(target_position, "target_position")
    if not isfinite(delta_s) or delta_s < 0.0:
        raise ValueError("delta_s must be finite and non-negative")
    if not isfinite(response_rate) or response_rate <= 0.0:
        raise ValueError("response_rate must be finite and positive")
    if hypot(target_x - render_x, target_y - render_y) <= 0.002:
        return target_x, target_y

    effective_delta_s = min(delta_s, MAX_INTERPOLATION_STEP_S)
    alpha = 1.0 - exp(-response_rate * effective_delta_s)
    return (
        render_x + (target_x - render_x) * alpha,
        render_y + (target_y - render_y) * alpha,
    )


def _finite_position(position: PhysicalPosition, name: str) -> PhysicalPosition:
    try:
        x_m = float(position[0])
        y_m = float(position[1])
    except (TypeError, ValueError, IndexError):
        raise ValueError(f"{name} must contain two finite coordinates") from None
    if not isfinite(x_m) or not isfinite(y_m):
        raise ValueError(f"{name} must contain two finite coordinates")
    return x_m, y_m
