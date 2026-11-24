"""The sprite metadata must describe the PNG that actually ships."""

import json
from importlib.resources import as_file, files

from hypothesis import given
from hypothesis import strategies as st
from PySide6.QtGui import QImage

from kata.sprites import AnimationInfo, read_sheet_info

EXPECTED = {"idle", "walk", "sit", "sleep", "happy", "held", "fall"}


@given(st.integers(min_value=1, max_value=1000))
def test_frame_ms_is_one_frame_rounded_to_the_millisecond(fps: int) -> None:
    anim = AnimationInfo(name="any", row=0, frames=1, fps=fps, loop=True)
    assert abs(anim.frame_ms - 1000 / fps) <= 0.5


def test_sheet_info_says_what_the_json_file_says() -> None:
    raw = json.loads(files("kata").joinpath("assets", "kata.json").read_text(encoding="utf-8"))
    info = read_sheet_info()
    assert info.image == raw["image"]
    assert (info.frame_w, info.frame_h) == (raw["frame"]["w"], raw["frame"]["h"])
    assert info.ground_y == raw["ground_y"]
    assert set(info.animations) == set(raw["animations"])
    for name, a in raw["animations"].items():
        anim = info.animations[name]
        assert anim.name == name
        assert (anim.row, anim.frames, anim.fps, anim.loop) == (a["row"], a["frames"], a["fps"], a["loop"])
        assert anim.anchor == (tuple(a["anchor"]) if "anchor" in a else None), name


def test_every_behaviour_has_an_animation():
    info = read_sheet_info()
    assert set(info.animations) == EXPECTED


def test_animations_fit_inside_the_sheet():
    info = read_sheet_info()
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        sheet = QImage(str(path))  # QImage, unlike QPixmap, works without a QApplication
    assert not sheet.isNull()
    for anim in info.animations.values():
        assert anim.frames >= 1
        assert anim.fps > 0
        assert anim.frames * info.frame_w <= sheet.width(), anim.name
        assert (anim.row + 1) * info.frame_h <= sheet.height(), anim.name


def test_held_knows_where_the_cursor_grips():
    info = read_sheet_info()
    anchor = info.animations["held"].anchor
    assert anchor is not None
    assert 0 <= anchor[0] < info.frame_w
    assert 0 <= anchor[1] < info.frame_h


def test_feet_stand_on_the_ground_line():
    info = read_sheet_info()
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        sheet = QImage(str(path))
    # In the first idle frame the paws (with their outline) reach the row just above
    # ground_y, and nothing is drawn from ground_y down.
    assert any(sheet.pixelColor(x, info.ground_y - 1).alpha() > 0 for x in range(info.frame_w))
    for y in range(info.ground_y, info.frame_h):
        assert all(sheet.pixelColor(x, y).alpha() == 0 for x in range(info.frame_w))
