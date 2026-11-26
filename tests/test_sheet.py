"""kata.sheet reads kata.json faithfully, without Qt."""

import dataclasses
import json
from importlib.resources import files

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kata.sheet import AnimationInfo, SheetInfo, read_sheet_info, walk_speed

EXPECTED = {"idle", "walk", "sit", "sleep", "happy", "held", "fall"}


def test_every_behaviour_has_an_animation() -> None:
    info = read_sheet_info()
    assert set(info.animations) == EXPECTED


def test_held_knows_where_the_cursor_grips() -> None:
    info = read_sheet_info()
    anchor = info.animations["held"].anchor
    assert anchor is not None
    assert 0 <= anchor[0] < info.frame_w
    assert 0 <= anchor[1] < info.frame_h


def test_only_the_walk_has_a_stride() -> None:
    # 12 sprite pixels per loop: a planted paw slides back 6 in half a loop (make_sprites.py).
    info = read_sheet_info()
    assert info.animations["walk"].stride == 12
    assert [name for name, anim in info.animations.items() if anim.stride is not None] == ["walk"]


@pytest.mark.parametrize("scale", [1, 2, 3, 4, 5, 6])
def test_todays_walk_moves_15_sprite_pixels_a_second(scale: int) -> None:
    # 12 pixels per loop of 8 frames at 10 fps: 12 x 10 / 8 = 15 sprite pixels a second.
    assert walk_speed(read_sheet_info(), scale) == 15 * scale


def test_the_walk_speed_is_stride_times_fps_over_frames_times_scale() -> None:
    # Numbers that don't divide evenly, so a rounded or truncated division shows.
    walk = AnimationInfo(name="walk", row=1, frames=7, fps=12, loop=True, stride=10)
    sheet = SheetInfo(image="any.png", frame_w=48, frame_h=48, ground_y=47, animations={"walk": walk})
    assert walk_speed(sheet, 4) == pytest.approx(10 * 12 / 7 * 4)  # 68.57...


def test_a_walk_without_a_stride_has_no_speed_to_give() -> None:
    walk = AnimationInfo(name="walk", row=1, frames=8, fps=10, loop=True)
    sheet = SheetInfo(image="any.png", frame_w=48, frame_h=48, ground_y=47, animations={"walk": walk})
    with pytest.raises(ValueError, match="stride"):
        walk_speed(sheet, 3)


def test_sprite_facts_cannot_be_changed_after_loading() -> None:
    # Every part of the app shares one SheetInfo, so a change made through it would reach them all.
    # mypy rejects these assignments already; the ignores say the failure is the point.
    info = read_sheet_info()
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.ground_y = 0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.animations["walk"].fps = 20  # type: ignore[misc]


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
        assert anim.stride == a.get("stride"), name
