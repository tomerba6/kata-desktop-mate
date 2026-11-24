"""Cut Kata's sprite sheet into frames.

The sheet is one PNG (assets/kata.png) holding every frame on a grid; kata.sheet reads the JSON
that says which row is which animation. load_frames() cuts the PNG into QPixmaps. A QPixmap lives
on the graphics side of Qt, so a QApplication must exist before you call it.
"""

from __future__ import annotations

from importlib.resources import as_file, files

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from kata.sheet import SheetInfo


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
