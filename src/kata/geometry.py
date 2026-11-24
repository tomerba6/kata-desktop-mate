"""Where Kata's window goes, worked out from plain numbers.

Kata's position is the feet point: the bottom centre of the sprite on its ground line, in Qt
screen coordinates. The window's top-left corner is derived from it.

Rect is this module's own, not Qt's QRect. QRect.bottom() is y + height - 1, one row short of the
floor, and keeping QRect out of here means that trap can't reach the maths. Build a Rect from a
QRect's x(), y(), width() and height() only.

This module is plain Python with no Qt, so it is tested without a screen.
"""

from __future__ import annotations

from dataclasses import dataclass

from kata.sheet import SheetInfo


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


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
