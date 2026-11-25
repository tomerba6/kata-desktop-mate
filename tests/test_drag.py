"""kata.drag tells a click from a drag and measures the release speed, without Qt.

Positions are floats, as Qt's globalPosition() gives them, and the press point has different x
and y, so a mix-up between them shows. The threshold is 10 px, the value Qt's offscreen platform
reports; the app passes the real one in.
"""

import pytest

from kata.drag import Grip

THRESHOLD = 10
WINDOW = 0.125  # seconds of movement the release speed is taken from
START = (100.0, 200.0)


def press(at: tuple[float, float] = START, t: float = 0.0) -> Grip:
    return Grip(at, t, THRESHOLD, WINDOW)


def test_a_press_and_release_in_place_is_a_click() -> None:
    grip = press()
    assert grip.release(START, 0.25)
    assert not grip.dragging


def test_moving_less_than_the_threshold_is_still_a_click() -> None:
    grip = press()
    assert not grip.move((103.0, 204.0), 0.125)  # 3 + 4 = 7 < 10
    assert grip.release((103.0, 204.0), 0.25)


def test_reaching_the_threshold_starts_a_drag_once() -> None:
    grip = press()
    assert grip.move((106.0, 204.0), 0.125)  # 6 + 4 = 10: a drag, and this move started it
    assert grip.dragging
    assert not grip.move((150.0, 204.0), 0.25)  # still dragging; it doesn't start again
    assert not grip.release((150.0, 204.0), 0.375)  # a drop, not a click


def test_the_distance_is_counted_sideways_plus_up_down() -> None:
    # Qt's own rule (manhattanLength). (7, 7) is only 9.9 px in a straight line, but 14 this way.
    assert press().move((107.0, 207.0), 0.125)
    assert not press().move((109.0, 200.0), 0.125)  # 9 sideways
    assert not press().move((100.0, 209.5), 0.125)  # 9.5 down
    assert press().move((94.0, 196.0), 0.125)  # 6 + 4, left and up


def test_a_release_far_from_the_press_with_no_moves_between_is_a_drop() -> None:
    grip = press()
    assert not grip.release((140.0, 200.0), 0.125)
    assert grip.dragging


def test_the_release_speed_comes_from_the_last_moments_only() -> None:
    grip = press((0.0, 0.0), 0.0)
    grip.move((5.0, 0.0), 0.5)  # slow at first
    grip.move((100.0, 50.0), 0.875)
    grip.release((260.3, 25.1), 1.0)  # the last 0.125 s: 160.3 right and 24.9 up
    assert grip.velocity() == pytest.approx((1282.4, -199.2))


def test_a_pointer_that_stopped_before_the_release_gives_no_speed() -> None:
    grip = press((0.0, 0.0), 0.0)
    grip.move((60.0, 0.0), 0.125)
    grip.move((120.0, 0.0), 0.25)
    grip.release((120.0, 0.0), 0.75)  # held still for half a second, then let go
    assert grip.velocity() == (0.0, 0.0)


def test_a_click_has_no_speed() -> None:
    grip = press()
    grip.release(START, 0.125)
    assert grip.velocity() == (0.0, 0.0)


def test_two_events_at_the_same_instant_are_fine() -> None:
    # Equal times in separate float objects, as two readings of a coarse clock would be.
    grip = press(t=0.5)
    assert grip.release(START, float("0.5"))
    assert grip.velocity() == (0.0, 0.0)


def test_time_going_backwards_is_refused_naming_the_latest_event() -> None:
    grip = press(t=1.0)
    grip.move((101.0, 200.0), 1.03125)
    grip.move((102.0, 200.0), 1.0625)
    # Later than the press and the first move, but earlier than the latest: still backwards.
    with pytest.raises(ValueError, match=r"1\.046875 after 1\.0625"):
        grip.move((103.0, 200.0), 1.046875)
