"""Kata's desktop window: frameless, see-through, always on top, with no taskbar button.

PetWindow draws the animator's current frame, moves with Kata's body, and handles the mouse. Qt
clears a translucent window to fully transparent before each paint, so there is no background to
fill. Kata's brain (kata.brain) decides what Kata does; the window carries it out.

The main tick. A QTimer fires at about 60 Hz, and each tick moves Kata on by the time since the
last one, read from the clock the window was given. Unless Kata is being carried, it updates the
brain, steps the body at the brain's walking velocity and under gravity, and tells the brain when
the body lands or its floor drops away. Then it moves the window when the feet's rounded position
changes, plays the brain's animation facing the brain's way, and advances the animator,
repainting only when the frame changes. A timer at the frame rate itself would fire right on the
frame boundaries, and Windows firing it a few milliseconds early or late showed a frame twice and
then skipped one. The desktop is read on every tick, so a taskbar that appears or moves is picked
up. Kata walks on the screen it stands on, and no further.

Facing left, the window draws the frames flipped left to right (kata.sprites.mirrored), built
once. The flip is about the feet point, so a turn never moves Kata sideways.

The mouse. A left press starts a Grip (kata.drag). Once it is a drag, the scruff (the `held`
anchor) follows the pointer, and the window moves on each mouse event so it doesn't lag a tick.
Facing left, the grip is the flipped frame's scruff. The brain hears grabbed() then, released(vx)
when Kata is thrown at the pointer's speed, and clicked() for a press that never became a drag,
which also emits `clicked`. Mouse tracking is on while the button is down: Qt delivers a move with
no button down only to a window that tracks the mouse, and such a move means the release went to
another window, so it counts as the release. Right-click opens a menu with Quit, the way out until
the tray menu arrives in milestone 5.

Events for KATA_LOG go to the `log` function: grab, release, landed and click, and a `state` line
whenever the brain's state or facing changes (a turn at the end of a walk is from=walk to=walk).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QContextMenuEvent, QGuiApplication, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from kata.animator import Animator
from kata.body import Body
from kata.brain import Brain, Facing, State
from kata.drag import Grip
from kata.geometry import (
    Bounds,
    Rect,
    area_under,
    feet_bounds,
    floor_under,
    grip_feet,
    mirrored_anchor,
    window_origin,
)
from kata.sheet import SheetInfo
from kata.sprites import mirrored

TICK_MS = 16  # about 60 Hz

type Point = tuple[float, float]


@dataclass(frozen=True)
class Desktop:
    """Where Kata may go: all screens' usable area as one rectangle, and each screen's."""

    area: Rect  # Qt's availableVirtualGeometry()
    screens: tuple[Rect, ...]  # each screen's availableGeometry()


def to_rect(rect: QRect) -> Rect:
    """A geometry Rect from a QRect, by x, y, width and height: QRect.bottom() is a row short."""
    return Rect(rect.x(), rect.y(), rect.width(), rect.height())


def qt_desktop() -> Desktop:
    """The desktop as Qt sees it now."""
    return Desktop(
        area=to_rect(QGuiApplication.primaryScreen().availableVirtualGeometry()),
        screens=tuple(to_rect(screen.availableGeometry()) for screen in QGuiApplication.screens()),
    )


class Log(Protocol):
    """Where KATA_LOG events go: an event name and its fields, as kata.switches.log_line takes them."""

    def __call__(self, event: str, **fields: object) -> None: ...


class PetWindow(QWidget):
    clicked = Signal()  # a left press and release that never became a drag

    def __init__(
        self,
        frames: dict[str, list[QPixmap]],
        sheet: SheetInfo,
        scale: int,
        body: Body,
        brain: Brain,
        *,
        clock: Callable[[], float],
        desktop: Callable[[], Desktop],
        log: Log,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        # See-through around the sprite, and shown without taking keyboard focus.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Kata")  # never shown, but it lets tools find the window
        self.setFixedSize(QSize(sheet.frame_w * scale, sheet.frame_h * scale))
        anchor = sheet.animations["held"].anchor
        if anchor is None:
            raise ValueError("the sprite sheet gives `held` no anchor, so there is nowhere to grip")
        self.frames = {Facing.RIGHT: frames, Facing.LEFT: mirrored(frames)}
        self.sheet = sheet
        self.scale = scale
        self.anchor = anchor
        self.body = body
        self.brain = brain
        self.read_desktop = desktop
        self.log = log
        self.animator = Animator(sheet.animations, brain.animation)
        self.facing_shown = brain.facing
        self.grip: Grip | None = None  # while the left button is down on Kata
        self.place()

        self.clock = clock
        self.last_tick = clock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

    @property
    def carried(self) -> bool:
        """True from the move that starts a drag until the release."""
        return self.grip is not None and self.grip.dragging

    def tick(self) -> None:
        now = self.clock()
        dt = now - self.last_tick
        self.last_tick = now
        if not self.carried:
            self.live(dt)
        self.follow_brain()
        shown = self.animator.frame
        self.animator.advance(dt)
        if self.animator.frame != shown:
            self.update()  # ask Qt to repaint soon; never call paintEvent yourself

    def live(self, dt: float) -> None:
        """Kata's own dt seconds: the brain decides, the body moves, and the floor reports back."""
        desktop = self.read_desktop()
        feet = (self.body.x, self.body.y)
        floor = floor_under(feet, desktop.screens)
        ground = feet_bounds(area_under(feet, desktop.screens), self.sheet, self.scale)
        self.think(lambda: self.brain.update(dt, self.body.x, (ground.left, ground.right)))
        # Standing, Kata stays on its own screen; in the air, the whole desktop is open to it.
        bounds = feet_bounds(desktop.area, self.sheet, self.scale) if self.body.airborne else ground
        if self.body.step(dt, floor, bounds, walk=self.brain.walk_velocity):
            self.think(self.brain.landed)
            self.log("landed", feet=self.feet(), floor=floor)
        elif self.body.airborne and self.brain.state not in (State.HELD, State.FALL):
            self.think(lambda: self.brain.released(0.0))  # the floor dropped away
        self.place()

    def think(self, event: Callable[[], None]) -> None:
        """Tell the brain something, and log a `state` line if its state or facing changed."""
        before = (self.brain.state, self.brain.facing)
        event()
        state, facing = self.brain.state, self.brain.facing
        if (state, facing) != before:
            moved = {"from": before[0].value, "to": state.value}  # "from" is a Python keyword
            self.log("state", **moved, facing=facing.name.lower(), feet=self.feet())

    def follow_brain(self) -> None:
        """Play the brain's animation, facing its way."""
        self.play(self.brain.animation)
        if self.brain.facing is not self.facing_shown:
            self.facing_shown = self.brain.facing
            self.update()

    def play(self, name: str) -> None:
        """Switch to the named animation, unless it is playing already."""
        if self.animator.animation.name != name:
            self.animator.play(name)
            self.update()

    def frame(self) -> QPixmap:
        """What to draw now: the animation's current frame, facing the brain's way."""
        return self.frames[self.brain.facing][self.animator.animation.name][self.animator.frame]

    def place(self) -> None:
        """Move the window to the body's feet, rounded, unless it is there already."""
        feet = (round(self.body.x), round(self.body.y))
        origin = QPoint(*window_origin(feet, self.sheet, self.scale))
        if origin != self.pos():
            self.move(origin)

    def hold(self, pointer: Point) -> tuple[Bounds, int]:
        """Put the scruff under the pointer, as far as the desktop allows.

        Returns the bounds and the floor it used, for the log.
        """
        desktop = self.read_desktop()
        anchor = self.anchor
        if self.brain.facing is Facing.LEFT:
            anchor = mirrored_anchor(anchor, self.sheet)  # the flipped frame's scruff
        feet = grip_feet(pointer, anchor, self.sheet, self.scale)
        bounds = feet_bounds(desktop.area, self.sheet, self.scale)
        floor = floor_under(feet, desktop.screens)
        self.body.hold(*feet, floor, bounds)
        self.place()
        return bounds, floor

    def feet(self) -> Point:
        """The feet point, rounded for the log."""
        return round(self.body.x, 2), round(self.body.y, 2)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        threshold = QApplication.startDragDistance()
        self.grip = Grip(pointer(event), self.clock(), threshold, self.body.config.release_window)
        self.setMouseTracking(True)  # so a lost release still arrives, as a move with no button

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.grip is None:
            super().mouseMoveEvent(event)
            return
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self.let_go(pointer(event))  # the release went to another window
            return
        started = self.grip.move(pointer(event), self.clock())
        if self.grip.dragging:
            bounds, floor = self.hold(pointer(event))
            if started:
                self.think(self.brain.grabbed)
                self.follow_brain()
                self.log("grab", feet=self.feet(), floor=floor, bounds=edges(bounds))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.grip is None:
            super().mouseReleaseEvent(event)
            return
        self.let_go(pointer(event))

    def let_go(self, at: Point) -> None:
        """The left button came up at `at`: a click, or a throw at the pointer's speed."""
        assert self.grip is not None
        grip, self.grip = self.grip, None
        self.setMouseTracking(False)
        if grip.release(at, self.clock()):
            self.log("click", feet=self.feet())
            self.think(self.brain.clicked)
            self.follow_brain()
            self.clicked.emit()
            return
        bounds, floor = self.hold(at)
        self.body.throw(*grip.velocity())
        self.think(lambda: self.brain.released(self.body.vx))
        self.follow_brain()
        speed = (round(self.body.vx, 2), round(self.body.vy, 2))
        self.log("release", feet=self.feet(), speed=speed, floor=floor, bounds=edges(bounds))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.frame())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())


def pointer(event: QMouseEvent) -> Point:
    """Where the pointer is on the screen: fractional at scaling such as 150%."""
    at = event.globalPosition()
    return at.x(), at.y()


def edges(bounds: Bounds) -> tuple[float, float, float]:
    """The bounds as one log field: left, right, top."""
    return bounds.left, bounds.right, bounds.top
