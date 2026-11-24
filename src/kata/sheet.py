"""Read Kata's sprite sheet description, assets/kata.json.

The sheet is one PNG (assets/kata.png) holding every frame on a grid, plus this JSON file saying
which row is which animation, how big a frame is and where the ground line sits.

This module is plain Python with no Qt, so any module can import the sprite facts and tests can
call it anywhere. Cutting the PNG into frames needs Qt and lives in kata.sprites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class AnimationInfo:
    name: str
    row: int  # which row of the sheet
    frames: int  # how many frames, counted from the left
    fps: int  # playback speed
    loop: bool  # False: play once, then the caller decides what comes next
    anchor: tuple[int, int] | None = None  # "held" only: where the cursor grips, in frame pixels

    @property
    def frame_ms(self) -> int:
        """How long one frame stays on screen, in milliseconds."""
        return round(1000 / self.fps)


@dataclass(frozen=True)
class SheetInfo:
    image: str  # file name of the PNG, next to the JSON
    frame_w: int
    frame_h: int
    ground_y: int  # the floor line: first empty row under the paws
    animations: dict[str, AnimationInfo]


def read_sheet_info(name: str = "kata") -> SheetInfo:
    """Parse assets/<name>.json into typed objects. No Qt involved."""
    raw = json.loads(files("kata").joinpath("assets", f"{name}.json").read_text(encoding="utf-8"))
    animations = {
        anim_name: AnimationInfo(
            name=anim_name,
            row=a["row"],
            frames=a["frames"],
            fps=a["fps"],
            loop=a["loop"],
            anchor=tuple(a["anchor"]) if "anchor" in a else None,
        )
        for anim_name, a in raw["animations"].items()
    }
    return SheetInfo(
        image=raw["image"],
        frame_w=raw["frame"]["w"],
        frame_h=raw["frame"]["h"],
        ground_y=raw["ground_y"],
        animations=animations,
    )
