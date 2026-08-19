"""Display-only access to the two independent USB bench sensors.

The readings exposed here are autonomous and are not a time-matched V2 pair.
They are suitable for an on-screen diagnostic overlay only: this module never
calculates a player position and must not feed scoring or safety decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import time
from typing import Callable, Optional, Protocol

from software.transport.serial_sensor import (
    DEFAULT_BAUD_RATE,
    BenchSensorReading,
    SerialSensorSource,
)


DEFAULT_STALE_AFTER_S = 1.0

WAITING = "WAITING"
LIVE = "LIVE"
NO_ECHO = "NO ECHO"
STALE = "STALE"
ID_MISMATCH = "ID MISMATCH"
PORT_ERROR = "PORT ERROR"


class _PollingSensorSource(Protocol):
    def poll_readings(self) -> tuple[BenchSensorReading, ...]:
        ...

    def close(self) -> None:
        ...


SourceFactory = Callable[[str, int], _PollingSensorSource]
Clock = Callable[[], float]


@dataclass(frozen=True)
class SensorOverlayValue:
    """One sensor's immutable, presentation-ready overlay value."""

    label: str
    port: str
    status: str
    distance_mm: Optional[float]


@dataclass(frozen=True)
class SensorOverlaySnapshot:
    """One non-blocking frame of left and right diagnostic values."""

    left: SensorOverlayValue
    right: SensorOverlayValue


@dataclass
class _SensorState:
    label: str
    port: str
    expected_node_id: str
    expected_sensor_id: str
    reading: Optional[BenchSensorReading] = None
    received_at_s: Optional[float] = None
    poll_failed: bool = False


class SerialSensorOverlay:
    """Poll two USB bench sources without blocking the Pygame frame loop."""

    def __init__(
        self,
        left_port: str,
        right_port: str,
        baud_rate: int = DEFAULT_BAUD_RATE,
        stale_after_s: float = DEFAULT_STALE_AFTER_S,
        *,
        left_source: Optional[_PollingSensorSource] = None,
        right_source: Optional[_PollingSensorSource] = None,
        source_factory: SourceFactory = SerialSensorSource,
        clock: Clock = time.monotonic,
    ) -> None:
        if not isinstance(left_port, str) or not left_port.strip():
            raise ValueError("left_port must not be empty")
        if not isinstance(right_port, str) or not right_port.strip():
            raise ValueError("right_port must not be empty")
        if left_port == right_port:
            raise ValueError("left_port and right_port must be different devices")
        if isinstance(baud_rate, bool) or not isinstance(baud_rate, int) or baud_rate <= 0:
            raise ValueError("baud_rate must be a positive integer")
        if isinstance(stale_after_s, bool):
            raise ValueError("stale_after_s must be positive")
        try:
            stale_timeout = float(stale_after_s)
        except (TypeError, ValueError) as exc:
            raise ValueError("stale_after_s must be positive") from exc
        if not isfinite(stale_timeout) or stale_timeout <= 0:
            raise ValueError("stale_after_s must be positive")

        self._stale_after_s = stale_timeout
        self._clock = clock
        self._left_state = _SensorState("LEFT SENSOR", left_port, "box1", "left")
        self._right_state = _SensorState("RIGHT SENSOR", right_port, "box2", "right")
        self._closed = False

        self._left_source = (
            left_source
            if left_source is not None
            else source_factory(left_port, baud_rate)
        )
        try:
            self._right_source = (
                right_source
                if right_source is not None
                else source_factory(right_port, baud_rate)
            )
        except BaseException:
            try:
                self._left_source.close()
            except Exception:
                pass
            raise

    def poll(self, now_s: Optional[float] = None) -> SensorOverlaySnapshot:
        """Drain both ports once and return values for the current game frame."""

        if self._closed:
            raise RuntimeError("serial sensor overlay is closed")
        observed_at_s = self._resolve_time(now_s)
        self._poll_one(self._left_source, self._left_state, observed_at_s)
        self._poll_one(self._right_source, self._right_state, observed_at_s)
        return self.snapshot(observed_at_s)

    def snapshot(self, now_s: Optional[float] = None) -> SensorOverlaySnapshot:
        """Return current display state without reading either serial port."""

        observed_at_s = self._resolve_time(now_s)
        return SensorOverlaySnapshot(
            left=self._value(self._left_state, observed_at_s),
            right=self._value(self._right_state, observed_at_s),
        )

    def close(self) -> None:
        """Close both owned sources, attempting the right even if left fails."""

        if self._closed:
            return
        self._closed = True
        first_error: Optional[BaseException] = None
        for source in (self._left_source, self._right_source):
            try:
                source.close()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "SerialSensorOverlay":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @staticmethod
    def _poll_one(
        source: _PollingSensorSource,
        state: _SensorState,
        observed_at_s: float,
    ) -> None:
        try:
            readings = source.poll_readings()
            latest = readings[-1] if readings else None
        except Exception:
            state.poll_failed = True
            return

        state.poll_failed = False
        if latest is not None:
            state.reading = latest
            state.received_at_s = observed_at_s

    def _value(self, state: _SensorState, now_s: float) -> SensorOverlayValue:
        status = WAITING
        reading = state.reading
        if state.poll_failed:
            status = PORT_ERROR
        elif reading is None or state.received_at_s is None:
            status = WAITING
        elif (
            reading.node_id != state.expected_node_id
            or reading.sensor_id != state.expected_sensor_id
        ):
            status = ID_MISMATCH
        elif now_s - state.received_at_s > self._stale_after_s:
            status = STALE
        elif not reading.valid:
            status = NO_ECHO
        else:
            status = LIVE

        distance_mm = None
        if status in (LIVE, STALE) and reading is not None and reading.valid:
            distance_mm = reading.distance_mm
        return SensorOverlayValue(state.label, state.port, status, distance_mm)

    def _resolve_time(self, now_s: Optional[float]) -> float:
        value = self._clock() if now_s is None else now_s
        try:
            resolved = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("now_s must be finite") from exc
        if not isfinite(resolved):
            raise ValueError("now_s must be finite")
        return resolved
