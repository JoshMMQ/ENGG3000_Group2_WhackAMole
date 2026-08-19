"""Coordinate conversion for the Whack-a-Mole play area."""

from dataclasses import dataclass
from math import isfinite
from typing import Optional, Tuple


ScreenPosition = Tuple[int, int]


@dataclass(frozen=True)
class CoordinateMapper:
    """Map physical metre coordinates into screen pixel coordinates."""

    play_area_left_m: float = 0.0
    play_area_top_m: float = 0.60
    play_area_width_m: float = 1.50
    play_area_height_m: float = 1.40
    screen_width_px: int = 900
    screen_height_px: int = 900

    def __post_init__(self) -> None:
        if self.play_area_width_m <= 0:
            raise ValueError("play_area_width_m must be positive")
        if self.play_area_height_m <= 0:
            raise ValueError("play_area_height_m must be positive")
        if self.screen_width_px <= 0:
            raise ValueError("screen_width_px must be positive")
        if self.screen_height_px <= 0:
            raise ValueError("screen_height_px must be positive")

    def physical_to_screen(self, x_m: object, y_m: object) -> Optional[ScreenPosition]:
        """Convert physical metres to clamped screen pixels.

        Only the playable V2 area is mapped: world ``y=0.60`` is the top of
        the window and ``y=2.00`` is the bottom. Invalid values return None.
        """

        x = self._valid_number(x_m)
        y = self._valid_number(y_m)
        if x is None or y is None:
            return None

        right_m = self.play_area_left_m + self.play_area_width_m
        bottom_m = self.play_area_top_m + self.play_area_height_m
        clamped_x = self._clamp(x, self.play_area_left_m, right_m)
        clamped_y = self._clamp(y, self.play_area_top_m, bottom_m)

        screen_x = round(
            ((clamped_x - self.play_area_left_m) / self.play_area_width_m)
            * (self.screen_width_px - 1)
            + 1e-9
        )
        screen_y = round(
            ((clamped_y - self.play_area_top_m) / self.play_area_height_m)
            * (self.screen_height_px - 1)
            + 1e-9
        )

        return screen_x, screen_y

    @staticmethod
    def _valid_number(value: object) -> Optional[float]:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not isfinite(number):
            return None
        return number

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))
