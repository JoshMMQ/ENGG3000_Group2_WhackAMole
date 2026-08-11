"""Simulated physical position input for hardware-free development."""

from dataclasses import dataclass
from math import pi, sin
from typing import Tuple


PhysicalPosition = Tuple[float, float]


@dataclass(frozen=True)
class SimulatedPositionSource:
    """Generate repeatable in-bounds movement across the play area."""

    play_area_width_m: float = 1.50
    play_area_top_m: float = 0.60
    play_area_height_m: float = 1.40
    x_period_s: float = 4.0
    y_period_s: float = 6.0

    def __post_init__(self) -> None:
        if self.play_area_width_m <= 0:
            raise ValueError("play_area_width_m must be positive")
        if self.play_area_height_m <= 0:
            raise ValueError("play_area_height_m must be positive")
        if self.x_period_s <= 0:
            raise ValueError("x_period_s must be positive")
        if self.y_period_s <= 0:
            raise ValueError("y_period_s must be positive")

    def position_at(self, elapsed_s: float) -> PhysicalPosition:
        """Return a simulated physical position for the elapsed time."""

        elapsed = max(0.0, float(elapsed_s))
        x_ratio = self._wave(elapsed, self.x_period_s)
        y_ratio = self._wave(elapsed, self.y_period_s)
        return (
            x_ratio * self.play_area_width_m,
            self.play_area_top_m + y_ratio * self.play_area_height_m,
        )

    @staticmethod
    def _wave(elapsed_s: float, period_s: float) -> float:
        return (sin((2.0 * pi * elapsed_s) / period_s) + 1.0) / 2.0
