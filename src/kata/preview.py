"""A plain window that plays Kata's animations, to check the sprites and your setup.

Keys: Left / Right switch animation, Space pauses, Esc quits.

This is ordinary-window Qt on purpose. Milestone 1 turns the same ideas (a
widget, a timer, a paintEvent) into a frameless, see-through desktop window.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QWidget

from kata.sheet import read_sheet_info
from kata.sprites import load_frames

SCALE = 6
BACKGROUND = QColor(58, 92, 110)


class Preview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.info = read_sheet_info()
        self.frames = load_frames(self.info, SCALE)
        self.names = list(self.info.animations)
        self.current = 0  # index into self.names
        self.frame = 0  # index into the current animation's frames

        self.setFixedSize(self.info.frame_w * SCALE, self.info.frame_h * SCALE)

        # A QTimer calls next_frame() from Qt's event loop. Nothing here blocks or sleeps.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.play(0)

    def play(self, index: int) -> None:
        self.current = index % len(self.names)
        self.frame = 0
        anim = self.info.animations[self.names[self.current]]
        self.setWindowTitle(f"Kata preview: {anim.name} ({anim.frames} frames at {anim.fps} fps)")
        self.timer.start(anim.frame_ms)
        self.update()  # ask Qt to repaint soon; never call paintEvent yourself

    def next_frame(self) -> None:
        anim = self.info.animations[self.names[self.current]]
        self.frame = (self.frame + 1) % anim.frames
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        painter.drawPixmap(0, 0, self.frames[self.names[self.current]][self.frame])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.play(self.current + 1)
        elif key == Qt.Key.Key_Left:
            self.play(self.current - 1)
        elif key == Qt.Key.Key_Space:
            if self.timer.isActive():
                self.timer.stop()
            else:
                self.timer.start()
        elif key == Qt.Key.Key_Escape:
            self.close()


def main() -> None:
    app = QApplication(sys.argv)
    window = Preview()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
