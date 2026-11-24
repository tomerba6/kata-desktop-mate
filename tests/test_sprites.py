"""The sprite metadata must describe the PNG that actually ships."""

from importlib.resources import as_file, files

from PySide6.QtGui import QImage

from kata.sheet import read_sheet_info


def test_animations_fit_inside_the_sheet() -> None:
    info = read_sheet_info()
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        sheet = QImage(str(path))  # QImage, unlike QPixmap, works without a QApplication
    assert not sheet.isNull()
    for anim in info.animations.values():
        assert anim.frames >= 1
        assert anim.fps > 0
        assert anim.frames * info.frame_w <= sheet.width(), anim.name
        assert (anim.row + 1) * info.frame_h <= sheet.height(), anim.name


def test_feet_stand_on_the_ground_line() -> None:
    info = read_sheet_info()
    with as_file(files("kata").joinpath("assets", info.image)) as path:
        sheet = QImage(str(path))
    # In the first idle frame the paws (with their outline) reach the row just above
    # ground_y, and nothing is drawn from ground_y down.
    assert any(sheet.pixelColor(x, info.ground_y - 1).alpha() > 0 for x in range(info.frame_w))
    for y in range(info.ground_y, info.frame_h):
        assert all(sheet.pixelColor(x, y).alpha() == 0 for x in range(info.frame_w))
