"""kata.geometry places Kata's window from plain numbers, without Qt.

Qt's QRect.bottom() is y + height - 1, the last row inside the rect. The floor Kata stands on is
the first row below it, y + height, so these tests pin that number and never go through QRect.
"""

import dataclasses

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from kata.geometry import (
    Bounds,
    Rect,
    area_under,
    feet_bounds,
    floor_under,
    floor_y,
    grip_feet,
    mirrored_anchor,
    start_feet,
    window_origin,
)
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


# --- Held by the scruff --------------------------------------------------------------------------


def test_held_at_scale_3_the_feet_hang_below_and_right_of_the_pointer() -> None:
    # Today's sheet: 48x48 frames, ground line 47, held's anchor at (22, 21). The anchor's 3x3
    # block has its centre 67 px from the window's left and 64 from its top; the feet are 72 from
    # the left and 141 from the top. So the feet are 5 px right of the pointer and 77 below it.
    sheet = read_sheet_info()
    anchor = sheet.animations["held"].anchor
    assert anchor is not None
    assert grip_feet((640, 400), anchor, sheet, 3) == (645, 477)


@st.composite
def grips(draw: st.DrawFn) -> tuple[SheetInfo, tuple[int, int]]:
    """A made-up sheet and an anchor pixel inside its frame."""
    sheet = draw(sheets())
    anchor = (
        draw(st.integers(min_value=0, max_value=sheet.frame_w - 1)),
        draw(st.integers(min_value=0, max_value=sheet.frame_h - 1)),
    )
    return sheet, anchor


coordinates = st.integers(min_value=-10_000, max_value=10_000)


@given(grips(), coordinates, coordinates, st.integers(min_value=1, max_value=6))
def test_held_the_anchor_pixel_is_under_the_pointer(
    grip: tuple[SheetInfo, tuple[int, int]], px: int, py: int, scale: int
) -> None:
    sheet, (ax, ay) = grip
    feet = grip_feet((px, py), (ax, ay), sheet, scale)
    left, top = window_origin((int(feet[0]), int(feet[1])), sheet, scale)
    # The pointer is inside the anchor's scale x scale block, at its middle.
    assert px - left == ax * scale + scale // 2
    assert py - top == ay * scale + scale // 2


def test_facing_left_the_scruff_is_the_mirrored_pixel() -> None:
    # Today's sheet: 48 columns, so held's anchor column 22 becomes 47 - 22 = 25, the same row.
    sheet = read_sheet_info()
    assert mirrored_anchor((22, 21), sheet) == (25, 21)


@given(grips())
def test_mirroring_the_anchor_twice_gives_it_back(grip: tuple[SheetInfo, tuple[int, int]]) -> None:
    sheet, anchor = grip
    assert mirrored_anchor(mirrored_anchor(anchor, sheet), sheet) == anchor


@given(grips(), st.integers(min_value=1, max_value=6))
def test_the_mirrored_anchor_s_block_is_the_anchor_s_block_flipped_across_the_window(
    grip: tuple[SheetInfo, tuple[int, int]], scale: int
) -> None:
    # Flipping the frame sends window column c to width - 1 - c, so the scale x scale block of
    # the anchor pixel must land exactly on the block of the mirrored anchor, row unchanged.
    sheet, (ax, ay) = grip
    width = sheet.frame_w * scale
    mx, my = mirrored_anchor((ax, ay), sheet)
    flipped = sorted(width - 1 - c for c in range(ax * scale, (ax + 1) * scale))
    assert flipped == list(range(mx * scale, (mx + 1) * scale))
    assert my == ay


# --- How far the feet may go ---------------------------------------------------------------------


def test_the_feet_bounds_on_this_screen_at_scale_3() -> None:
    # Half the 144-wide window either side of the feet, and the 141 rows above the ground line.
    assert feet_bounds(SCREEN, read_sheet_info(), 3) == Bounds(72, 1208, 141)


@given(areas, sheets(), st.integers(min_value=1, max_value=6))
def test_at_the_feet_bounds_the_window_just_fits_on_the_desktop(
    desktop: Rect, sheet: SheetInfo, scale: int
) -> None:
    width = sheet.frame_w * scale
    assume(desktop.w >= width)  # a desktop narrower than Kata has no room for it
    bounds = feet_bounds(desktop, sheet, scale)
    left_x, right_x, top_y = int(bounds.left), int(bounds.right), int(bounds.top)
    right = desktop.x + desktop.w  # one past the desktop's last column

    window_left, window_top = window_origin((left_x, top_y), sheet, scale)
    assert window_left == desktop.x and window_top == desktop.y
    window_left, _ = window_origin((right_x, top_y), sheet, scale)
    assert window_left + width == right
    # One pixel further, and the window would cross the edge: the bounds are not too tight.
    assert window_origin((left_x - 1, top_y - 1), sheet, scale) == (desktop.x - 1, desktop.y - 1)
    assert window_origin((right_x + 1, top_y), sheet, scale)[0] + width == right + 1


# --- Which floor -------------------------------------------------------------------------------


def test_on_one_screen_the_floor_is_its_bottom_wherever_the_feet_are() -> None:
    assert floor_under((640, 100), [SCREEN]) == 720
    assert floor_under((640, 720), [SCREEN]) == 720
    assert floor_under((640, 900), [SCREEN]) == 720  # below it: the only floor there is


LEFT = Rect(0, 0, 1920, 1080)


def test_side_by_side_screens_each_have_their_own_floor() -> None:
    right = Rect(1920, 0, 2560, 1440)  # taller, to the right
    assert floor_under((1000, 500), [LEFT, right]) == 1080
    assert floor_under((1919.5, 500), [LEFT, right]) == 1080  # still over the left one
    assert floor_under((1920, 500), [LEFT, right]) == 1440
    # Carried from the tall screen onto the short one below its floor: the short one's floor.
    assert floor_under((1000, 1300), [LEFT, right]) == 1080


def test_stacked_screens_give_the_first_floor_at_or_below_the_feet() -> None:
    below = Rect(0, 1080, 1920, 1080)
    assert floor_under((500, 300), [below, LEFT]) == 1080
    assert floor_under((500, 1080), [below, LEFT]) == 1080
    assert floor_under((500, 1500), [below, LEFT]) == 2160


def test_stacked_screens_of_different_widths() -> None:
    wide_below = Rect(0, 1080, 2560, 1440)  # sticks out 640 columns right of LEFT
    assert floor_under((500.5, 300), [wide_below, LEFT]) == 1080  # over both: LEFT's floor first
    assert floor_under((2000.5, 300), [wide_below, LEFT]) == 2520  # only the wide one is there


def test_a_screen_s_first_and_last_columns_count_as_over_it() -> None:
    # Feet on the edge column of a short screen stacked over a wider one: over both.
    short = Rect(500, 0, 1000, 1080)  # columns 500 to 1499
    wide = Rect(0, 1080, 2000, 1440)
    assert floor_under((500.5, 300), [wide, short]) == 1080
    assert floor_under((1499.5, 300), [wide, short]) == 1080


# Screens that don't start at column 0, with a gap between them: narrow covers columns 150 to 999,
# offset covers 1200 to 2199.
NARROW = Rect(150, 0, 850, 800)
OFFSET = Rect(1200, 0, 1000, 600)


def test_feet_over_no_screen_use_the_nearest_one() -> None:
    assert floor_under((1099.5, 100), [NARROW, OFFSET]) == 800  # 100 columns from 999, 101 from 1200
    assert floor_under((1100.5, 100), [NARROW, OFFSET]) == 600  # 101 from 999, 100 from 1200
    assert floor_under((100.5, 100), [NARROW, OFFSET]) == 800  # left of everything


def test_equally_near_screens_both_count() -> None:
    # Column 1099 is 100 columns from both; the first floor at or below the feet wins.
    farther = Rect(1199, 0, 1000, 600)  # now 100 columns from 1099 as well
    assert floor_under((1099.5, 100), [NARROW, farther]) == 600
    assert floor_under((1099.5, 700), [NARROW, farther]) == 800


@given(st.floats(-20_000, 20_000), st.floats(-20_000, 20_000), st.lists(areas, min_size=1, max_size=4))
def test_the_floor_is_always_one_of_the_screens_floors(x: float, y: float, screens: list[Rect]) -> None:
    assert floor_under((x, y), screens) in {floor_y(s) for s in screens}


# --- Which screen Kata walks on ------------------------------------------------------------------


def test_side_by_side_the_screen_under_the_feet_is_the_one_whose_floor_they_get() -> None:
    right = Rect(1920, 0, 2560, 1440)
    assert area_under((1000, 500), [LEFT, right]) == LEFT
    assert area_under((1919.5, 500), [LEFT, right]) == LEFT
    assert area_under((1920, 500), [LEFT, right]) == right
    assert area_under((1000, 1300), [LEFT, right]) == LEFT  # below the short one's floor


def test_stacked_the_screen_under_the_feet_is_the_first_floor_at_or_below() -> None:
    below = Rect(0, 1080, 1920, 1080)
    assert area_under((500, 300), [below, LEFT]) == LEFT
    assert area_under((500, 1080), [below, LEFT]) == LEFT
    assert area_under((500, 1500), [below, LEFT]) == below


def test_over_no_screen_the_nearest_one_is_under_the_feet() -> None:
    assert area_under((1099.5, 100), [NARROW, OFFSET]) == NARROW
    assert area_under((1100.5, 100), [NARROW, OFFSET]) == OFFSET


def test_of_equally_near_screens_the_one_with_the_first_floor_at_or_below_is_under() -> None:
    farther = Rect(1199, 0, 1000, 600)
    assert area_under((1099.5, 100), [NARROW, farther]) == farther
    assert area_under((1099.5, 700), [NARROW, farther]) == NARROW


@given(st.floats(-20_000, 20_000), st.floats(-20_000, 20_000), st.lists(areas, min_size=1, max_size=4))
def test_the_screen_under_the_feet_is_one_of_the_screens(x: float, y: float, screens: list[Rect]) -> None:
    assert area_under((x, y), screens) in screens
