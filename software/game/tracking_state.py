"""Sensor-model-neutral tracking state shared by game input sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .simulated_position import PhysicalPosition


class TrackingStatus(str, Enum):
    """High-level state exposed to the game loop."""

    WAITING = "waiting"
    PLAYABLE = "playable"
    DEAD_ZONE = "dead_zone"
    TRACKING_LOST = "tracking_lost"


@dataclass(frozen=True)
class TrackingSnapshot:
    """Minimal position state consumed by shared game helpers."""

    status: TrackingStatus
    world_position: Optional[PhysicalPosition]
    cursor_position: PhysicalPosition
    cycle_id: Optional[int]
