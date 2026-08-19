"""Logical cell domain plus a compatibility mapper for current V2 positions.

The approved three-sensor tracker will produce confirmed cells from calibrated
S1/S2/S3 scan evidence. ``world_position_to_cell`` exists only to bridge the
current two-sensor triangulation path during migration; it is not the target
sensor classifier and must not be used to bypass confidence or hysteresis.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional


PLAY_AREA_LEFT_M = 0.0
PLAY_AREA_TOP_M = 0.60
PLAY_AREA_WIDTH_M = 1.50
PLAY_AREA_HEIGHT_M = 1.40
GRID_COLUMNS = 3
GRID_ROWS = 3


@dataclass(frozen=True)
class PlayerCell:
    """One 1-indexed column/row in the physical 3 x 3 gameplay grid."""

    column: int
    row: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.column, bool)
            or not isinstance(self.column, int)
            or not 1 <= self.column <= GRID_COLUMNS
        ):
            raise ValueError("column must be an integer from 1 to 3")
        if (
            isinstance(self.row, bool)
            or not isinstance(self.row, int)
            or not 1 <= self.row <= GRID_ROWS
        ):
            raise ValueError("row must be an integer from 1 to 3")


def world_position_to_cell(position: object) -> Optional[PlayerCell]:
    """Map one current-tracker world position into a compatibility cell.

    Row 1 is nearest the screen and row 3 is farthest away. Cells are
    half-open at their internal boundaries, so a point exactly on a boundary
    enters the next column or row. The outer right and rear edges remain part
    of column 3 and row 3. Invalid or out-of-playable positions return ``None``
    rather than being clamped into a plausible cell. The target tracker instead
    confirms a column and row from a complete S1/S2/S3 scan.
    """

    if not isinstance(position, (tuple, list)) or len(position) != 2:
        return None

    x_m = _finite_number(position[0])
    y_m = _finite_number(position[1])
    if x_m is None or y_m is None:
        return None

    play_area_right_m = PLAY_AREA_LEFT_M + PLAY_AREA_WIDTH_M
    play_area_bottom_m = PLAY_AREA_TOP_M + PLAY_AREA_HEIGHT_M
    if not PLAY_AREA_LEFT_M <= x_m <= play_area_right_m:
        return None
    if not PLAY_AREA_TOP_M <= y_m <= play_area_bottom_m:
        return None

    x_ratio = (x_m - PLAY_AREA_LEFT_M) / PLAY_AREA_WIDTH_M
    y_ratio = (y_m - PLAY_AREA_TOP_M) / PLAY_AREA_HEIGHT_M
    column = min(int(x_ratio * GRID_COLUMNS), GRID_COLUMNS - 1) + 1
    row = min(int(y_ratio * GRID_ROWS), GRID_ROWS - 1) + 1
    return PlayerCell(column=column, row=row)


def _finite_number(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None
