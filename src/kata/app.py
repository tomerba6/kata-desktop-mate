"""Start Kata: the QApplication, the sprites, the body, the window, and where it stands.

main() reads the sprite facts, loads the frames at SCALE, and stands Kata's body in the middle of
the primary screen's floor. The floor is the first row below the area Qt says windows may use: the
top of the taskbar, or the screen's bottom edge when the taskbar auto-hides, since Qt then counts
the whole screen as usable. The window is handed the body, a brain (the default behaviour, the
sheet's walking speed at SCALE, and a random.Random seeded by the OS), the clock, Qt's desktop and
a log function. With KATA_LOG=1 in the environment, the log prints where Kata was placed and, from
then on, each grab, release, landing, click and change of state.
"""

from __future__ import annotations

import os
import random
import sys
import time

from PySide6.QtWidgets import QApplication

from kata.body import Body, PhysicsConfig
from kata.brain import BehaviourConfig, Brain
from kata.geometry import start_feet
from kata.sheet import read_sheet_info, walk_speed
from kata.sprites import load_frames
from kata.switches import is_on, log_line
from kata.window import Log, PetWindow, qt_desktop, to_rect

SCALE = 3  # each sprite pixel becomes a SCALE x SCALE block; milestone 5 makes it a setting


def main() -> None:
    started = time.perf_counter()
    app = QApplication(sys.argv)
    log = printing_log(started) if is_on("KATA_LOG", os.environ) else silent_log
    sheet = read_sheet_info()

    screen = app.primaryScreen()
    area = to_rect(screen.availableGeometry())
    feet = start_feet(area)
    body = Body(*feet, PhysicsConfig())
    brain = Brain(BehaviourConfig(), walk_speed(sheet, SCALE), random.Random())
    window = PetWindow(
        load_frames(sheet, SCALE),
        sheet,
        SCALE,
        body,
        brain,
        clock=time.perf_counter,
        desktop=qt_desktop,
        log=log,
    )
    window.show()

    placed = window.geometry()
    log(
        "placed",
        screen=screen.name(),
        dpr=screen.devicePixelRatio(),
        area=(area.x, area.y, area.w, area.h),
        feet=feet,
        window=(placed.x(), placed.y(), placed.width(), placed.height()),
    )

    sys.exit(app.exec())


def printing_log(started: float) -> Log:
    """A log that prints each event as a KATA_LOG line, timed from `started` (perf_counter)."""

    def log(event: str, **fields: object) -> None:
        print(log_line(time.perf_counter() - started, event, **fields), flush=True)

    return log


def silent_log(event: str, **fields: object) -> None:
    """KATA_LOG is off: log nothing."""
