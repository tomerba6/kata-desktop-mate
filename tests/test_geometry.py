"""kata.geometry places Kata's window from plain numbers, without Qt.

Qt's QRect.bottom() is y + height - 1, the last row inside the rect. The floor Kata stands on is
the first row below it, y + height, so these tests pin that number and never go through QRect.
"""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kata.geometry import Bounds, Rect, floor_y, start_feet, window_origin
from kata.sheet import SheetInfo, read_sheet_info

SCREEN = Rect(0, 0, 1280, 720)  # this machine's usable area, in Qt units, taskbar hidden


def test_a_rect_cannot_be_changed_after_it_is_made() -> None:
    # A Rect is a value handed between modules; a change made through one holder would reach all.
    # mypy rejects the assignment already; the ignore says the failure is the point.
    area = Rect(0, 0, 1280, 720)
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.y = 48  # type: ignore[misc]


def test_bounds_cannot_be_changed_after_they_are_made() -> None:
    bounds = Bounds(0.0, 1000.0, 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bounds.top = 50.0  # type: ignore[misc]


def test_the_floor_is_the_row_below_the_area_not_its_last_row() -> None:
    assert floor_y(SCREEN) == 720


def test_a_taskbar_along_the_top_moves_the_area_but_not_the_floor() -> None:
    assert floor_y(Rect(0, 48, 1280, 672)) == 720


def test_kata_starts_centred_on_the_floor() -> None:
    assert start_feet(SCREEN) == (640, 720)


def test_the_window_at_scale_3_puts_the_ground_line_on_the_feet() -> None:
    # 48x48 frames with the ground line at row 47: a 144x144 window, its row 141 on y = 720.
    assert window_origin((640, 720), read_sheet_info(), 3) == (568, 579)


def centred(left: int, width: int, x: int) -> bool:
    """Column x is the middle of `width` columns starting at `left`.

    With an even width there are two middle columns, and x is the right-hand one.
    """
    on_left = x - left
    on_right = left + width - 1 - x
    return on_left - on_right in (0, 1)


areas = st.builds(
    Rect,
    x=st.integers(min_value=-10_000, max_value=10_000),
    y=st.integers(min_value=-10_000, max_value=10_000),
    w=st.integers(min_value=1, max_value=10_000),
    h=st.integers(min_value=1, max_value=10_000),
)


@st.composite
def sheets(draw: st.DrawFn) -> SheetInfo:
    frame_h = draw(st.integers(min_value=1, max_value=256))
    return SheetInfo(
        image="any.png",
        frame_w=draw(st.integers(min_value=1, max_value=256)),
        frame_h=frame_h,
        ground_y=draw(st.integers(min_value=0, max_value=frame_h)),
        animations={},
    )


@given(areas, sheets(), st.integers(min_value=1, max_value=6))
def test_the_window_stands_kata_centred_on_the_floor(area: Rect, sheet: SheetInfo, scale: int) -> None:
    feet_x, feet_y = start_feet(area)
    assert feet_y == area.y + area.h
    assert centred(area.x, area.w, feet_x)

    left, top = window_origin((feet_x, feet_y), sheet, scale)
    assert top + sheet.ground_y * scale == feet_y
    assert centred(left, sheet.frame_w * scale, feet_x)
    # Whole pixels: Qt places windows on integer coordinates.
    assert all(type(n) is int for n in (feet_x, feet_y, left, top))
