"""Cut Kata's sprite sheet into frames, and flip them for facing left.

The sheet is one PNG (assets/kata.png) holding every frame on a grid; kata.sheet reads the JSON
that says which row is which animation. load_frames() cuts the PNG into QPixmaps, and mirrored()
flips them left to right, since the sheet draws Kata facing right. A QPixmap lives on the graphics
side of Qt, so a QApplication must exist before you call either.
"""

from __future__ import annotations

from importlib.resources import as_file, files

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QTransform

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


def mirrored(frames: dict[str, list[QPixmap]]) -> dict[str, list[QPixmap]]:
    """The same frames flipped left to right, for Kata facing left. Build them once, at load.

    The flip is about the frame's middle column line, which is where the feet point sits, so a
    turn never shifts Kata sideways. FastTransformation keeps every pixel exactly as it was.
    """
    flip = QTransform().scale(-1, 1)
    return {
        name: [frame.transformed(flip, Qt.TransformationMode.FastTransformation) for frame in cut]
        for name, cut in frames.items()
    }
