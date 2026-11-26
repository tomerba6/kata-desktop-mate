"""PetWindow driven headless: Qt's offscreen platform, a fake clock and made-up mouse events.

conftest.py puts Qt on its offscreen platform, so no window appears. The tests call tick()
themselves, the way the window's timer would, and the fake clock moves on only when a test runs
ticks, so time is exactly what the test says. A tick is 1/64 s, which floats hold exactly, so a
300 px drop at gravity 2400 lands on exactly the 32nd tick (½ × 2400 × 0.5² = 300).

Mouse positions are screen positions, as Qt's globalPosition() gives them. The desktop is made up:
one screen whose usable area starts at (37, 23), not (0, 0), so a mix-up between x and y, or
between the area and the window, shows.

Kata's brain stays idle unless a test gives it other behaviour (STAY_IDLE), so wandering doesn't
move Kata under the tests about carrying it. A walk's direction is a coin, so the walking tests
start Kata at an end of its range, where it heads away whatever the coin says.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from kata.body import Body, PhysicsConfig
from kata.brain import BehaviourConfig, Brain, Facing, State
from kata.geometry import Rect, feet_bounds, mirrored_anchor, window_origin
from kata.sheet import read_sheet_info, walk_speed
from kata.sprites import load_frames
from kata.window import Desktop, PetWindow, to_rect

type Point = tuple[float, float]

SHEET = read_sheet_info()
SCALE = 3
SPEED = walk_speed(SHEET, SCALE)  # 45 per s
# The tests' own numbers, so tuning the app's defaults doesn't break them.
PHYSICS = PhysicsConfig(gravity=2400.0, max_fall_speed=2400.0, max_throw_speed=1500.0, release_window=0.08)
STAY_IDLE = BehaviourConfig(idle_time=(1000.0, 1000.0))  # longer than any test here
# Idle for half a second (32 ticks), then walk for longer than any test here.
WALK_SOON = BehaviourConfig(idle_time=(0.5, 0.5), walk_time=(1000.0, 1000.0), after_idle=((State.WALK, 1.0),))
AREA = Rect(37, 23, 1280, 697)  # the floor is row 720
FLOOR = 720
START = (611.4, 720.0)  # Kata's feet, standing on the floor
WALK_ENDS = feet_bounds(AREA, SHEET, SCALE)  # the feet walk from 109 to 1245
TICK = 1 / 64
LEFT = Qt.MouseButton.LeftButton
RIGHT = Qt.MouseButton.RightButton
NO_BUTTON = Qt.MouseButton.NoButton


class Rig:
    """A PetWindow with a fake clock, a made-up desktop, a recording log, and a mouse."""

    def __init__(
        self,
        physics: PhysicsConfig = PHYSICS,
        behaviour: BehaviourConfig = STAY_IDLE,
        start: Point = START,
        area: Rect = AREA,
        seed: int = 0,
    ) -> None:
        self.now = 10.0
        self.desktop = Desktop(area=area, screens=(area,))
        self.logged: list[tuple[str, dict[str, object]]] = []
        self.clicks = 0
        self.window = PetWindow(
            load_frames(SHEET, SCALE),
            SHEET,
            SCALE,
            Body(*start, physics),
            Brain(behaviour, SPEED, random.Random(seed)),
            clock=lambda: self.now,
            desktop=lambda: self.desktop,
            log=self.log,
        )
        self.window.clicked.connect(self.count_click)
        self.window.show()

    def log(self, event: str, **fields: object) -> None:
        self.logged.append((event, fields))

    def count_click(self) -> None:
        self.clicks += 1

    def animation(self) -> str:
        return self.window.animator.animation.name

    def facing(self) -> Facing:
        return self.window.brain.facing

    def drawn_from(self, facing: Facing) -> bool:
        """Whether the frame the window draws now is the current frame of `facing`'s set."""
        frame = self.window.frames[facing][self.animation()][self.window.animator.frame]
        return self.window.frame() is frame

    def scruff(self) -> Point:
        """Where the scruff is on screen now: the middle of held's anchor pixel, scaled up.

        Facing left, the frames are flipped, and the scruff with them.
        """
        anchor = SHEET.animations["held"].anchor
        assert anchor is not None
        if self.facing() is Facing.LEFT:
            anchor = mirrored_anchor(anchor, SHEET)
        return (
            self.window.x() + anchor[0] * SCALE + SCALE // 2,
            self.window.y() + anchor[1] * SCALE + SCALE // 2,
        )

    def states(self) -> list[tuple[object, object, object]]:
        """The `state` log lines so far: from, to, facing."""
        return [(f["from"], f["to"], f["facing"]) for event, f in self.logged if event == "state"]

    def others(self) -> list[str]:
        """The names of the log lines that aren't `state` lines."""
        return [event for event, _ in self.logged if event != "state"]

    def run(self, ticks: int) -> None:
        """Let `ticks` ticks of the window's timer go by."""
        for _ in range(ticks):
            self.now += TICK
            self.window.tick()

    def press(self, at: Point, button: Qt.MouseButton = LEFT) -> None:
        self._send(QEvent.Type.MouseButtonPress, at, button, button)

    def move(self, at: Point, buttons: Qt.MouseButton = LEFT) -> None:
        self._send(QEvent.Type.MouseMove, at, NO_BUTTON, buttons)

    def release(self, at: Point, button: Qt.MouseButton = LEFT) -> None:
        self._send(QEvent.Type.MouseButtonRelease, at, button, NO_BUTTON)

    def _send(self, kind: QEvent.Type, at: Point, button: Qt.MouseButton, buttons: Qt.MouseButton) -> None:
        local = QPointF(at[0] - self.window.x(), at[1] - self.window.y())
        event = QMouseEvent(kind, local, QPointF(*at), button, buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.window, event)


@pytest.fixture
def kata(app: QApplication) -> Iterator[Rig]:
    rig = Rig()
    yield rig
    rig.window.close()


def on_floor(x: int) -> QPoint:
    """The window's top-left corner with the feet at column x on the floor."""
    return QPoint(*window_origin((x, FLOOR), SHEET, SCALE))


def lift(kata: Rig, height: float) -> Point:
    """Press on the scruff, a little right of its middle, and lift Kata by `height`."""
    x, y = kata.scruff()
    kata.press((x + 0.4, y))
    kata.run(1)
    above = (x + 0.4, y - height)
    kata.move(above)
    return above


def test_a_qrect_becomes_a_rect_by_its_width_and_height() -> None:
    # QRect.right() and bottom() are a column and a row short; the floor maths needs w and h.
    assert to_rect(QRect(37, 23, 1280, 697)) == Rect(37, 23, 1280, 697)


def test_kata_starts_where_its_body_stands(kata: Rig) -> None:
    assert kata.window.pos() == on_floor(611)
    assert kata.animation() == "idle"


def test_carrying_kata_by_the_scruff_moves_the_window_with_the_pointer(kata: Rig) -> None:
    start = kata.window.pos()
    x, y = kata.scruff()
    kata.press((x + 0.4, y))
    kata.run(1)
    kata.move((x + 50.4, y))
    # It moves on the mouse event itself, not on the next tick.
    assert kata.window.pos() == start + QPoint(50, 0)
    assert kata.animation() == "held"
    kata.run(1)
    kata.move((x + 50.4, y - 100))
    assert kata.window.pos() == start + QPoint(50, -100)
    kata.run(30)  # held up there, it doesn't fall
    assert kata.window.pos() == start + QPoint(50, -100)
    assert kata.animation() == "held"


def test_a_press_and_release_in_place_is_a_click_and_kata_stays_put(kata: Rig) -> None:
    start = kata.window.pos()
    x, y = kata.scruff()
    nearly = QApplication.startDragDistance() - 1  # counted sideways plus up and down
    kata.press((x, y))
    kata.run(1)
    kata.move((x + nearly - 4, y + 4))
    kata.run(3)
    kata.release((x + nearly - 4, y + 4))
    kata.run(30)
    assert kata.clicks == 1
    assert kata.window.pos() == start
    assert kata.animation() == "idle"
    assert [event for event, _ in kata.logged] == ["click"]


def test_a_drop_falls_straight_down_lands_on_the_floor_then_plays_idle(kata: Rig) -> None:
    start_x = kata.window.x()
    above = lift(kata, 300)
    kata.run(32)  # held still for half a second, then let go: no speed
    kata.release(above)
    assert kata.animation() == "fall"
    for _ in range(31):
        kata.run(1)
        assert kata.window.x() == start_x
        assert kata.animation() == "fall"
    assert kata.window.y() < on_floor(611).y()
    kata.run(1)  # the 32nd tick: 0.5 s, when a 300 px drop lands
    assert kata.window.pos() == on_floor(611)
    assert kata.animation() == "idle"


def test_a_flick_carries_kata_as_far_as_the_pointer_was_moving(kata: Rig) -> None:
    x, y = lift(kata, 300)
    for k in range(1, 7):  # 10 px right each tick: 640 px/s
        kata.run(1)
        kata.move((x + 10 * k, y))
    kata.release((x + 10 * k, y))  # let go at 611.4 + 60 = 671.4
    kata.run(32)  # 0.5 s of fall, 320 px further right
    assert kata.window.pos() == on_floor(991)  # 991.4, rounded
    assert kata.animation() == "idle"


def test_a_hard_flick_stops_at_the_screen_edge(kata: Rig) -> None:
    x, y = lift(kata, 300)
    for k in range(1, 7):  # 20 px right each tick: 1280 px/s, enough to fly 640 px
        kata.run(1)
        kata.move((x + 20 * k, y))
    kata.release((x + 20 * k, y))
    kata.run(32)
    assert kata.window.x() + kata.window.width() == AREA.x + AREA.w
    assert kata.window.y() == on_floor(611).y()
    assert kata.animation() == "idle"


def test_a_falling_kata_is_caught_by_a_press_and_a_move(kata: Rig) -> None:
    above = lift(kata, 300)
    kata.run(32)
    kata.release(above)
    kata.run(10)
    assert kata.animation() == "fall"
    before = kata.window.pos()
    x, y = kata.scruff()
    kata.press((x, y))
    kata.run(1)
    assert kata.window.y() > before.y()  # a press alone doesn't stop the fall
    kata.move((x + 20, y))  # a drag: the scruff jumps back under the pointer
    assert kata.window.pos() == before + QPoint(20, 0)
    assert kata.animation() == "held"
    assert kata.logged[-1][0] == "grab"
    kata.run(30)
    assert kata.window.pos() == before + QPoint(20, 0)  # held in mid-air, not falling


def test_dragging_past_the_screen_edges_keeps_the_window_on_the_desktop(kata: Rig) -> None:
    x, y = kata.scruff()
    kata.press((x, y))
    kata.run(1)
    kata.move((-400.3, y))
    assert kata.window.x() == AREA.x
    kata.run(1)
    kata.move((-400.3, -250.6))
    assert kata.window.pos() == QPoint(AREA.x, AREA.y)
    kata.run(1)
    kata.move((2000.2, -250.6))
    assert kata.window.x() + kata.window.width() == AREA.x + AREA.w
    assert kata.window.y() == AREA.y
    kata.run(1)
    kata.move((2000.2, 1500.7))  # the feet stop on the floor
    assert kata.window.x() + kata.window.width() == AREA.x + AREA.w
    assert kata.window.y() == on_floor(611).y()


def test_a_right_button_press_does_not_start_a_drag(kata: Rig) -> None:
    start = kata.window.pos()
    x, y = kata.scruff()
    kata.press((x, y), RIGHT)
    kata.run(1)
    kata.move((x + 50, y), RIGHT)
    kata.run(1)
    kata.release((x + 50, y), RIGHT)
    kata.run(30)
    assert kata.window.pos() == start
    assert kata.animation() == "idle"
    assert kata.clicks == 0
    assert kata.logged == []


def test_a_move_with_no_button_down_counts_as_the_release(kata: Rig) -> None:
    # The release went to another window, after Alt+Tab for example. Held still first, since
    # the lift itself, 300 px in one tick, would count as a fast throw upwards.
    above = lift(kata, 300)
    kata.run(32)
    kata.move(above, NO_BUTTON)
    assert kata.animation() == "fall"
    kata.run(32)
    assert kata.window.pos() == on_floor(611)
    assert kata.animation() == "idle"


def test_a_floor_that_rises_lifts_kata_onto_it(kata: Rig) -> None:
    shorter = Rect(AREA.x, AREA.y, AREA.w, AREA.h - 20)  # a taskbar appears: the floor is row 700
    kata.desktop = Desktop(area=shorter, screens=(shorter,))
    kata.run(1)
    assert kata.window.pos() == on_floor(611) - QPoint(0, 20)


def test_the_apps_own_physics_numbers_carry_and_drop_kata(app: QApplication) -> None:
    # Every other test uses PHYSICS. This one uses the defaults app.py runs with, so a default that
    # breaks carrying fails here: a negative release window, for one, makes Grip lose every sample.
    kata = Rig(PhysicsConfig())
    try:
        x, y = lift(kata, 300)
        for k in range(1, 4):
            kata.run(1)
            kata.move((x + 10 * k, y))
        assert kata.window.pos() == on_floor(641) - QPoint(0, 300)  # 611.4 + 30, and lifted
        kata.run(32)  # held still, so the drop has no speed
        kata.release((x + 30, y))
        kata.run(64)  # a second: plenty for a 300 px drop
        assert kata.window.pos() == on_floor(641)
        assert kata.animation() == "idle"
        assert kata.others() == ["grab", "release", "landed"]
    finally:
        kata.window.close()


def test_the_log_records_the_grab_the_release_and_the_landing(kata: Rig) -> None:
    above = lift(kata, 300)
    kata.run(32)
    kata.release(above)
    kata.run(32)
    bounds = feet_bounds(AREA, SHEET, SCALE)
    edges = (bounds.left, bounds.right, bounds.top)
    assert [(event, fields) for event, fields in kata.logged if event != "state"] == [
        ("grab", {"feet": (611.4, 420.0), "floor": FLOOR, "bounds": edges}),
        ("release", {"feet": (611.4, 420.0), "speed": (0.0, 0.0), "floor": FLOOR, "bounds": edges}),
        ("landed", {"feet": (611.4, 720.0), "floor": FLOOR}),
    ]


# --- The brain drives it --------------------------------------------------------------------


@pytest.fixture
def make(app: QApplication) -> Iterator[Callable[..., Rig]]:
    """Build Rigs with other behaviour, starting places or desktops; all closed afterwards."""
    made: list[Rig] = []

    def build(
        behaviour: BehaviourConfig = STAY_IDLE, start: Point = START, area: Rect = AREA, seed: int = 0
    ) -> Rig:
        rig = Rig(behaviour=behaviour, start=start, area=area, seed=seed)
        made.append(rig)
        return rig

    yield build
    for rig in made:
        rig.window.close()


def test_left_alone_kata_walks_at_the_sheet_s_speed(make: Callable[..., Rig]) -> None:
    kata = make(behaviour=WALK_SOON, start=(WALK_ENDS.left, FLOOR))
    kata.run(31)
    assert kata.animation() == "idle"
    kata.run(1)  # half a second: the idle is over
    assert (kata.animation(), kata.facing()) == ("walk", Facing.RIGHT)  # away from the left end
    x, where = kata.window.body.x, kata.window.pos()
    kata.run(64)
    assert kata.window.body.x == x + SPEED  # 45 px in a second, to the last bit
    assert kata.window.pos() == where + QPoint(45, 0)
    assert kata.drawn_from(Facing.RIGHT)


def test_at_the_end_of_its_range_kata_turns_and_the_frames_mirror_in_place(
    make: Callable[..., Rig],
) -> None:
    narrow = Rect(37, 23, 400, 697)  # the feet walk from 109 to 365
    kata = make(behaviour=WALK_SOON, start=(109.0, FLOOR), area=narrow)
    kata.run(32)
    assert kata.facing() is Facing.RIGHT
    before = kata.window.pos()
    for _ in range(64 * 10):  # 256 px at 45 per s takes under 6 s
        before = kata.window.pos()
        kata.run(1)
        if kata.facing() is Facing.LEFT:
            break
    assert (kata.animation(), kata.facing()) == ("walk", Facing.LEFT)
    assert before.x() == 365 - 72  # it had reached the end
    assert abs(kata.window.x() - before.x()) <= 1  # one tick of walking: no jump as it turns
    assert kata.drawn_from(Facing.LEFT)
    assert kata.states()[-1] == ("walk", "walk", "left")  # a turn gets a log line too


def test_picked_up_facing_left_it_dangles_mirrored_by_its_own_scruff(make: Callable[..., Rig]) -> None:
    kata = make(behaviour=WALK_SOON, start=(WALK_ENDS.right, FLOOR))  # its walk heads left
    kata.run(32 + 16)
    assert (kata.animation(), kata.facing()) == ("walk", Facing.LEFT)
    where = kata.window.pos()
    x, y = kata.scruff()
    kata.press((x, y))
    kata.move((x - 50, y))  # at the same instant, so it doesn't walk in between
    assert kata.window.pos() == where - QPoint(50, 0)  # the flipped scruff stayed under the pointer
    assert (kata.animation(), kata.facing()) == ("held", Facing.LEFT)
    assert kata.drawn_from(Facing.LEFT)


def test_thrown_left_kata_faces_left_and_lands_that_way(kata: Rig) -> None:
    x, y = lift(kata, 300)
    for k in range(1, 7):  # 10 px left each tick: 640 px/s
        kata.run(1)
        kata.move((x - 10 * k, y))
    assert kata.facing() is Facing.RIGHT  # carried, it faces the way it did
    kata.release((x - 60, y))
    assert (kata.animation(), kata.facing()) == ("fall", Facing.LEFT)
    assert kata.drawn_from(Facing.LEFT)
    kata.run(32)
    assert (kata.animation(), kata.facing()) == ("idle", Facing.LEFT)


def test_a_click_on_a_sleeping_kata_wakes_it(make: Callable[..., Rig]) -> None:
    nap_soon = BehaviourConfig(
        idle_time=(0.5, 0.5),
        sit_time=(0.5, 0.5),
        sleep_time=(1000.0, 1000.0),
        sleep_after=0.0,
        after_idle=((State.SIT, 1.0),),
    )
    kata = make(behaviour=nap_soon)
    kata.run(64)  # half a second idle, half a second sitting, then a nap
    assert kata.animation() == "sleep"
    x, y = kata.scruff()
    kata.press((x, y))
    kata.run(1)
    kata.release((x, y))
    assert kata.animation() == "idle"
    assert kata.clicks == 1


def test_a_floor_dropping_away_drops_kata_and_it_lands_idle(kata: Rig) -> None:
    taller = Rect(AREA.x, AREA.y, AREA.w, AREA.h + 50)  # the taskbar hides: the floor drops to 770
    kata.desktop = Desktop(area=taller, screens=(taller,))
    kata.run(1)
    assert kata.animation() == "fall"
    kata.run(64)
    assert kata.window.pos() == on_floor(611) + QPoint(0, 50)
    assert kata.animation() == "idle"
    assert kata.states() == [("idle", "fall", "right"), ("fall", "idle", "right")]


def test_each_change_of_state_gets_a_log_line(kata: Rig) -> None:
    above = lift(kata, 300)
    kata.run(32)
    kata.release(above)
    kata.run(32)
    assert kata.states() == [("idle", "held", "right"), ("held", "fall", "right"), ("fall", "idle", "right")]
    grabbed = next(fields for event, fields in kata.logged if event == "state")
    assert grabbed["feet"] == (611.4, 420.0)  # where the scruff put the feet


@pytest.mark.slow
def test_ten_minutes_alone_with_the_app_s_own_behaviour(make: Callable[..., Rig]) -> None:
    # The smoke test: the real window, brain, body and animator, wired as app.py wires them.
    kata = make(behaviour=BehaviourConfig(), seed=7)
    columns: set[int] = set()
    for _ in range(10 * 60 * 16):  # ticks of 1/16 s
        kata.now += 1 / 16
        kata.window.tick()
        where = kata.window.pos()
        assert AREA.x <= where.x() and where.x() + kata.window.width() <= AREA.x + AREA.w
        assert AREA.y <= where.y() and where.y() + SHEET.ground_y * SCALE <= FLOOR
        columns.add(where.x())
    assert len(columns) > 1  # it wandered
    assert {"walk", "sit", "sleep"} <= {to for _, to, _ in kata.states()}
