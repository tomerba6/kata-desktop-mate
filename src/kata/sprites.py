"""Read Kata's sprite sheet.

The sheet is one PNG (assets/kata.png) holding every frame on a grid, plus a
JSON file (assets/kata.json) that says which row is which animation.

This module is split in two on purpose:

* read_sheet_info() is plain Python. It needs no window system, so tests can
  call it anywhere.
* load_frames() cuts the PNG into QPixmaps. A QPixmap lives on the graphics
  side of Qt, so a QApplication must exist before you call it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import as_file, files

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


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


def load_frames(info: SheetInfo, scale: int = 1) -> dict[str, list[QPixmap]]:
    """Cut the sheet into frames, enlarged by a whole-number scale.

    FastTransformation is nearest-neighbour scaling: every source pixel becomes
    a crisp scale x scale block. The default smooth scaling would blur pixel art.
    """
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        sheet = QPixmap(str(path))
    if sheet.isNull():
        raise FileNotFoundError(f"could not load sprite sheet {info.image}")

    frames: dict[str, list[QPixmap]] = {}
    for anim in info.animations.values():
        cut = []
        for col in range(anim.frames):
            frame = sheet.copy(col * info.frame_w, anim.row * info.frame_h, info.frame_w, info.frame_h)
            if scale != 1:
                frame = frame.scaled(
                    info.frame_w * scale,
                    info.frame_h * scale,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            cut.append(frame)
        frames[anim.name] = cut
    return frames
