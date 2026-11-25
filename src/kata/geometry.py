"""Where Kata's window goes, worked out from plain numbers.

Kata's position is the feet point: the bottom centre of the sprite on its ground line, in Qt
screen coordinates. The window's top-left corner is derived from it.

Rect is this module's own, not Qt's QRect. QRect.bottom() is y + height - 1, one row short of the
floor, and keeping QRect out of here means that trap can't reach the maths. Build a Rect from a
QRect's x(), y(), width() and height() only.

This module is plain Python with no Qt, so it is tested without a screen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from kata.sheet import SheetInfo


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Bounds:
    """Where the feet may go: from left to right, both included, and no higher than top.

    y grows downwards, so "no higher" means y >= top. The floor, the lowest the feet may go, is
    passed separately, since it depends on which screen Kata is over.
    """

    left: float
    right: float
    top: float


def floor_y(area: Rect) -> int:
    """The row Kata's feet stand on: the first row below the area, not its last row."""
    return area.y + area.h


def start_feet(area: Rect) -> tuple[int, int]:
    """Kata's first feet point: the middle of the area's floor."""
    return area.x + area.w // 2, floor_y(area)


def window_origin(feet: tuple[int, int], sheet: SheetInfo, scale: int) -> tuple[int, int]:
    """The window's top-left corner that centres the sprite on the feet, ground line on feet y."""
    feet_x, feet_y = feet
    return feet_x - sheet.frame_w * scale // 2, feet_y - sheet.ground_y * scale


def grip_feet(
    pointer: tuple[float, float], anchor: tuple[int, int], sheet: SheetInfo, scale: int
) -> tuple[float, float]:
    """The feet point that puts the middle of the anchor pixel's scaled block under the pointer.

    The anchor is a pixel of the frame (for `held`, the scruff), so on screen it is a scale x
    scale block; the pointer sits at that block's middle, to the right of it when scale is even.
    """
    block_x = anchor[0] * scale + scale // 2  # from the window's top-left corner
    block_y = anchor[1] * scale + scale // 2
    left, top = pointer[0] - block_x, pointer[1] - block_y
    return left + sheet.frame_w * scale // 2, top + sheet.ground_y * scale


def feet_bounds(desktop: Rect, sheet: SheetInfo, scale: int) -> Bounds:
    """How far the feet may go while the window's left, right and top edges stay on the desktop."""
    width = sheet.frame_w * scale
    half = width // 2  # columns of the window left of the feet
    return Bounds(
        left=desktop.x + half,
        right=desktop.x + desktop.w - (width - half),
        top=desktop.y + sheet.ground_y * scale,
    )


def floor_under(feet: tuple[float, float], areas: Sequence[Rect]) -> int:
    """The floor of the screen Kata is over: the first floor at or below the feet.

    `areas` are the screens' usable areas. Only screens whose columns hold the feet count; if
    none does, the nearest screens sideways stand in. If no floor is at or below the feet (carried
    below a shorter screen's floor), the lowest of them is used.
    """
    column, y = math.floor(feet[0]), feet[1]

    def columns_away(area: Rect) -> int:
        """0 over the area; otherwise the columns to its nearest edge column."""
        return max(area.x - column, column - (area.x + area.w - 1), 0)

    nearest = min(columns_away(area) for area in areas)
    floors = [floor_y(area) for area in areas if columns_away(area) == nearest]
    at_or_below = [floor for floor in floors if floor >= y]
    return min(at_or_below) if at_or_below else max(floors)
