"""The sprite metadata must describe the PNG that actually ships, and the frames cut from it.

The first two tests read the PNG as a QImage, which needs no QApplication. The rest cut frames
with load_frames(), and a QPixmap does need one: the `app` fixture (conftest.py), on Qt's
offscreen platform. Frames are compared row by row as bytes, all in one pixel format (ARGB32,
premultiplied), which is what QPixmap.toImage() gives here (checked).
"""

from __future__ import annotations

from importlib.resources import as_file, files

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from kata.sheet import SheetInfo, read_sheet_info
from kata.sprites import load_frames, mirrored

FORMAT = QImage.Format.Format_ARGB32_Premultiplied


def sheet_image(info: SheetInfo) -> QImage:
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        return QImage(str(path))  # QImage, unlike QPixmap, works without a QApplication


def rows(image: QImage) -> list[bytes]:
    """The image's rows of pixels as bytes, four per pixel."""
    image = image.convertToFormat(FORMAT)
    data, line, width = bytes(image.constBits()), image.bytesPerLine(), image.width() * 4
    return [data[y * line : y * line + width] for y in range(image.height())]


def pixels(row: bytes) -> list[bytes]:
    return [row[i : i + 4] for i in range(0, len(row), 4)]


def test_animations_fit_inside_the_sheet() -> None:
    info = read_sheet_info()
    sheet = sheet_image(info)
    assert not sheet.isNull()
    for anim in info.animations.values():
        assert anim.frames >= 1
        assert anim.fps > 0
        assert anim.frames * info.frame_w <= sheet.width(), anim.name
        assert (anim.row + 1) * info.frame_h <= sheet.height(), anim.name


def test_feet_stand_on_the_ground_line() -> None:
    info = read_sheet_info()
    sheet = sheet_image(info)
    # In the first idle frame the paws (with their outline) reach the row just above
    # ground_y, and nothing is drawn from ground_y down.
    assert any(sheet.pixelColor(x, info.ground_y - 1).alpha() > 0 for x in range(info.frame_w))
    for y in range(info.ground_y, info.frame_h):
        assert all(sheet.pixelColor(x, y).alpha() == 0 for x in range(info.frame_w))


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_every_animation_gets_its_frames_at_frame_size_times_scale(app: QApplication, scale: int) -> None:
    info = read_sheet_info()
    frames = load_frames(info, scale)
    assert set(frames) == set(info.animations)
    for name, anim in info.animations.items():
        assert len(frames[name]) == anim.frames, name
        for frame in frames[name]:
            assert (frame.width(), frame.height()) == (info.frame_w * scale, info.frame_h * scale), name


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_every_sheet_pixel_becomes_a_scale_by_scale_block(app: QApplication, scale: int) -> None:
    # Nearest-neighbour scaling: each output row repeats a sheet row's pixels `scale` times each,
    # and each sheet row is used for `scale` output rows. Smooth scaling would blend neighbours.
    info = read_sheet_info()
    sheet = rows(sheet_image(info))
    frames = load_frames(info, scale)
    for name, anim in info.animations.items():
        for col, frame in enumerate(frames[name]):
            for y, row in enumerate(rows(frame.toImage())):
                source = pixels(sheet[anim.row * info.frame_h + y // scale])
                cell = source[col * info.frame_w : (col + 1) * info.frame_w]
                assert row == b"".join(px * scale for px in cell), (name, col, y)


def test_mirrored_frames_are_the_frames_flipped_left_to_right(app: QApplication) -> None:
    frames = load_frames(read_sheet_info(), 3)
    flipped = mirrored(frames)
    assert set(flipped) == set(frames)
    for name, cut in frames.items():
        assert len(flipped[name]) == len(cut), name
        for original, mirror in zip(cut, flipped[name], strict=True):
            assert mirror.size() == original.size(), name
            expected = [b"".join(reversed(pixels(row))) for row in rows(original.toImage())]
            assert rows(mirror.toImage()) == expected, name
