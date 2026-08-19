"""Sensor-model-neutral domain types for one complete target tracking scan.

This module deliberately has no packet, firmware, Pygame, classification, or
gameplay behavior. It is the first structural step in the controlled migration
from the current two-sensor tracker to S1/S2/S3 cell tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Optional


class SensorId(str, Enum):
    """The three active sensors in the approved target architecture."""

    S1 = "s1"
    S2 = "s2"
    S3 = "s3"


@dataclass(frozen=True)
class SensorReading:
    """One calibrated-boundary measurement in millimetres.

    Invalid acquisition is represented by ``valid=False`` and
    ``distance_mm=None``. ``sample_time_ms`` is an explicitly unit-suffixed
    monotonic or host-domain time; its clock interpretation belongs to the
    later packet contract.
    """

    sensor_id: SensorId
    distance_mm: Optional[float]
    valid: bool
    sample_time_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.sensor_id, SensorId):
            raise TypeError("sensor_id must be an active SensorId")
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be a bool")
        if (
            isinstance(self.sample_time_ms, bool)
            or not isinstance(self.sample_time_ms, int)
            or self.sample_time_ms < 0
        ):
            raise ValueError("sample_time_ms must be a non-negative integer")

        if not self.valid:
            if self.distance_mm is not None:
                raise ValueError("an invalid reading must have distance_mm=None")
            return

        if isinstance(self.distance_mm, bool) or not isinstance(
            self.distance_mm, (int, float)
        ):
            raise ValueError("a valid reading must have a numeric distance_mm")
        distance_mm = float(self.distance_mm)
        if not isfinite(distance_mm) or distance_mm <= 0.0:
            raise ValueError("a valid distance_mm must be finite and positive")
        object.__setattr__(self, "distance_mm", distance_mm)


@dataclass(frozen=True)
class SensorScan:
    """Exactly one S1, S2, and S3 reading belonging to a shared cycle."""

    cycle_id: int
    readings: tuple[SensorReading, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle_id, bool)
            or not isinstance(self.cycle_id, int)
            or self.cycle_id < 0
        ):
            raise ValueError("cycle_id must be a non-negative integer")
        if not isinstance(self.readings, tuple):
            raise TypeError("readings must be an immutable tuple")
        if len(self.readings) != len(SensorId):
            raise ValueError("a complete scan must contain exactly three readings")
        if not all(isinstance(reading, SensorReading) for reading in self.readings):
            raise TypeError("readings must contain only SensorReading values")

        sensor_ids = tuple(reading.sensor_id for reading in self.readings)
        if len(set(sensor_ids)) != len(sensor_ids):
            raise ValueError("a complete scan cannot contain duplicate sensors")
        if set(sensor_ids) != set(SensorId):
            raise ValueError("a complete scan must contain S1, S2, and S3")

    def reading_for(self, sensor_id: SensorId) -> SensorReading:
        """Return one named active reading."""

        if not isinstance(sensor_id, SensorId):
            raise TypeError("sensor_id must be an active SensorId")
        return next(
            reading for reading in self.readings if reading.sensor_id is sensor_id
        )

    @property
    def all_valid(self) -> bool:
        """Whether all three acquisition results are valid."""

        return all(reading.valid for reading in self.readings)

    @property
    def sample_span_ms(self) -> int:
        """Elapsed sample-time span without imposing a timing policy."""

        sample_times_ms = [reading.sample_time_ms for reading in self.readings]
        return max(sample_times_ms) - min(sample_times_ms)
