"""Kata's desktop window: frameless, see-through, always on top, with no taskbar button.

PetWindow draws the animator's current frame and nothing else. Qt clears a translucent window to
fully transparent before each paint, so there is no background to fill.

A QTimer ticks at about 60 Hz and moves the animator on by the real time since the last tick,
measured with QElapsedTimer; the window repaints only when the frame changes. A timer at the
frame rate itself would fire right on the frame boundaries, and Windows firing it a few
milliseconds early or late showed a frame twice and then skipped one. Milestone 2's main tick
grows out of this timer.

Right-click opens a menu with Quit, the way out until the tray menu arrives in milestone 5.
"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QSize, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from kata.animator import Animator

TICK_MS = 16  # about 60 Hz


class PetWindow(QWidget):
    def __init__(self, frames: dict[str, list[QPixmap]], animator: Animator, size: QSize) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        # See-through around the sprite, and shown without taking keyboard focus.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Kata")  # never shown, but it lets tools find the window
        self.setFixedSize(size)
        self.frames = frames
        self.animator = animator

        self.clock = QElapsedTimer()
        self.clock.start()
        self.last_tick_ns = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

    def tick(self) -> None:
        now_ns = self.clock.nsecsElapsed()
        shown = self.animator.frame
        self.animator.advance((now_ns - self.last_tick_ns) / 1e9)
        self.last_tick_ns = now_ns
        if self.animator.frame != shown:
            self.update()  # ask Qt to repaint soon; never call paintEvent yourself

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.frames[self.animator.animation.name][self.animator.frame])

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())
