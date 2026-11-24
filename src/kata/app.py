"""Start Kata: the QApplication, the sprites, the window, and where it stands.

main() reads the sprite facts, loads the frames at SCALE, plays idle, and stands Kata in the
middle of the primary screen's floor. The floor is the first row below the area Qt says windows
may use: the top of the taskbar, or the screen's bottom edge when the taskbar auto-hides, since Qt
then counts the whole screen as usable. With KATA_LOG=1 in the environment it prints where Kata
was placed.
"""

from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from kata.animator import Animator
from kata.geometry import Rect, start_feet, window_origin
from kata.sheet import read_sheet_info
from kata.sprites import load_frames
from kata.switches import is_on, log_line
from kata.window import PetWindow

SCALE = 3  # each sprite pixel becomes a SCALE x SCALE block; milestone 5 makes it a setting


def main() -> None:
    started = time.perf_counter()
    app = QApplication(sys.argv)
    sheet = read_sheet_info()
    animator = Animator(sheet.animations, "idle")
    size = QSize(sheet.frame_w * SCALE, sheet.frame_h * SCALE)
    window = PetWindow(load_frames(sheet, SCALE), animator, size)

    screen = app.primaryScreen()
    usable = screen.availableGeometry()
    # x, y, width and height only: QRect.bottom() is one row short of the floor.
    area = Rect(usable.x(), usable.y(), usable.width(), usable.height())
    feet = start_feet(area)
    window.move(*window_origin(feet, sheet, SCALE))
    window.show()

    if is_on("KATA_LOG", os.environ):
        placed = window.geometry()
        line = log_line(
            time.perf_counter() - started,
            "placed",
            screen=screen.name(),
            dpr=screen.devicePixelRatio(),
            area=(area.x, area.y, area.w, area.h),
            feet=feet,
            window=(placed.x(), placed.y(), placed.width(), placed.height()),
        )
        print(line, flush=True)

    sys.exit(app.exec())
