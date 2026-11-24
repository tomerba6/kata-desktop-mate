"""kata.sheet reads kata.json faithfully, without Qt."""

import json
from importlib.resources import files

from hypothesis import given
from hypothesis import strategies as st

from kata.sheet import AnimationInfo, read_sheet_info

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
