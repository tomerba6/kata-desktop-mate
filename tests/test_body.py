"""kata.body moves Kata's feet under gravity and lands them on the floor, without Qt.

The physics numbers here are made up rather than PhysicsConfig's defaults, so the tests don't
change when the feel is tuned. They are chosen so the expected positions are exact: gravity 1000,
falls capped at 500 (reached after 0.5 s), throws capped at 300. y grows downwards, as on screen.
"""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kata.body import Body, PhysicsConfig
from kata.geometry import Bounds

CONFIG = PhysicsConfig(gravity=1000.0, max_fall_speed=500.0, max_throw_speed=300.0)
WIDE = Bounds(left=0.0, right=1000.0, top=0.0)
FAR = 1_000_000.0  # a floor too far down to reach


def falling(x: float = 500.0, y: float = 0.0) -> Body:
    return Body(x, y, CONFIG)


def test_physics_numbers_cannot_be_changed_after_loading() -> None:
    # One PhysicsConfig is shared; a change made through one holder would reach every body.
    with pytest.raises(dataclasses.FrozenInstanceError):
        CONFIG.gravity = 0.0  # type: ignore[misc]


def test_a_dropped_body_falls_half_g_t_squared_straight_down() -> None:
    body = falling()
    body.step(0.4, FAR, WIDE)
    assert body.y == pytest.approx(80.0)  # 1000 * 0.4² / 2
    assert body.vy == pytest.approx(400.0)
    assert (body.x, body.vx) == (500.0, 0.0)


def test_a_sideways_throw_keeps_its_speed_while_it_falls() -> None:
    body = falling(x=100.0)
    body.throw(200.0, 0.0)
    for _ in range(5):
        body.step(0.1, FAR, WIDE)
    assert body.x == pytest.approx(200.0)  # 200 per s for 0.5 s
    assert body.vx == 200.0


def test_the_fall_speed_stops_at_the_cap() -> None:
    body = falling()
    body.step(1.5, FAR, WIDE)
    # 0.5 s speeding up (125) then 1 s at the cap of 500 (500).
    assert body.y == pytest.approx(625.0)
    assert body.vy == 500.0


def test_one_step_or_many_small_ones_fall_the_same() -> None:
    # The fall is worked out exactly, so the frame rate can't change where Kata is.
    once, often = falling(), falling()
    once.step(1.5, FAR, WIDE)
    for _ in range(90):
        often.step(1.5 / 90, FAR, WIDE)
    assert often.y == pytest.approx(once.y)
    assert often.vy == pytest.approx(once.vy)


def test_it_stops_exactly_on_the_floor_and_reports_landing_once() -> None:
    body = falling(y=900.0)
    landings = [body.step(1 / 60, 1000.0, WIDE) for _ in range(120)]
    assert landings.count(True) == 1
    assert (body.y, body.vx, body.vy) == (1000.0, 0.0, 0.0)
    assert not body.airborne


def test_a_step_that_ends_exactly_on_the_floor_is_a_landing() -> None:
    # 1000 * 0.5² / 2 = 125 is exact in binary, so this step ends on 1000.0 to the last digit.
    # Touching the floor counts as landing: Kata stops there, not one frame later.
    body = falling(y=875.0)
    assert body.step(0.5, 1000.0, WIDE)
    assert body.y == 1000.0
    assert not body.airborne


def test_a_body_standing_on_the_floor_stays_put() -> None:
    body = Body(300.0, 1000.0, CONFIG)
    assert not body.step(0.5, 1000.0, WIDE)
    assert (body.x, body.y, body.vy) == (300.0, 1000.0, 0.0)
    assert not body.airborne


def test_a_floor_that_rises_lifts_a_standing_body_onto_it() -> None:
    # The taskbar appearing, for example. Kata stands on it; that isn't a landing.
    body = Body(300.0, 1000.0, CONFIG)
    assert not body.step(0.1, 950.0, WIDE)
    assert body.y == 950.0
    assert not body.airborne


def test_a_floor_that_drops_makes_a_standing_body_fall_and_land() -> None:
    body = Body(300.0, 1000.0, CONFIG)
    body.step(0.1, 1100.0, WIDE)
    assert body.airborne
    assert 1000.0 < body.y < 1100.0
    landings = [body.step(1 / 60, 1100.0, WIDE) for _ in range(60)]
    assert landings.count(True) == 1
    assert body.y == 1100.0


def test_a_side_edge_stops_the_sideways_speed_only() -> None:
    body = falling(x=990.0, y=100.0)
    body.throw(300.0, 0.0)
    body.step(0.1, FAR, WIDE)
    assert body.x == 1000.0
    assert body.vx == 0.0
    assert body.vy > 0.0  # still falling
    body = falling(x=10.0, y=100.0)
    body.throw(-300.0, 0.0)
    body.step(0.1, FAR, WIDE)
    assert (body.x, body.vx) == (0.0, 0.0)


def test_the_top_edge_stops_upward_speed() -> None:
    body = falling(y=10.0)
    body.throw(0.0, -300.0)
    body.step(0.1, FAR, WIDE)  # it would reach -15
    assert (body.y, body.vy) == (0.0, 0.0)


def test_a_throw_is_capped_and_keeps_its_direction() -> None:
    body = falling()
    body.throw(3000.0, -4000.0)  # 5000 long; cut to 300, the same 3 : -4 direction
    assert (body.vx, body.vy) == pytest.approx((180.0, -240.0))
    body.throw(30.0, -40.0)  # under the cap: unchanged
    assert (body.vx, body.vy) == (30.0, -40.0)
    assert body.airborne


def test_a_landing_stops_a_throw_from_sliding() -> None:
    body = falling(y=990.0)
    body.throw(200.0, 0.0)
    while not body.step(1 / 60, 1000.0, WIDE):
        pass
    assert (body.vx, body.vy) == (0.0, 0.0)


def test_a_held_body_goes_where_it_is_put_inside_the_bounds() -> None:
    body = falling()
    body.throw(100.0, 100.0)
    body.hold(400.0, 300.0, 1000.0, WIDE)
    assert (body.x, body.y, body.vx, body.vy) == (400.0, 300.0, 0.0, 0.0)
    body.hold(-50.0, 1200.0, 1000.0, WIDE)  # past the left edge and below the floor
    assert (body.x, body.y) == (0.0, 1000.0)
    body.hold(1200.0, -50.0, 1000.0, WIDE)  # past the right edge and above the top
    assert (body.x, body.y) == (1000.0, 0.0)
    assert body.airborne  # let go, it falls and lands


def test_a_negative_dt_raises() -> None:
    with pytest.raises(ValueError):
        falling().step(-0.001, FAR, WIDE)


@st.composite
def scenes(draw: st.DrawFn) -> tuple[Body, float, Bounds]:
    """A floor, bounds around it, and a body somewhere inside them, maybe thrown."""
    left = draw(st.floats(min_value=-2000, max_value=2000))
    top = draw(st.floats(min_value=-2000, max_value=2000))
    bounds = Bounds(left, left + draw(st.floats(min_value=0, max_value=4000)), top)
    floor = top + draw(st.floats(min_value=0, max_value=4000))
    x = draw(st.floats(min_value=bounds.left, max_value=bounds.right))
    y = draw(st.floats(min_value=top, max_value=floor))
    body = Body(x, y, CONFIG)
    if draw(st.booleans()):
        speed = st.floats(min_value=-5000, max_value=5000)
        body.throw(draw(speed), draw(speed))
    return body, floor, bounds


steps = st.lists(st.floats(min_value=0, max_value=0.5), max_size=50)


@given(scenes(), steps)
def test_the_feet_never_leave_the_bounds_or_go_below_the_floor(
    scene: tuple[Body, float, Bounds], dts: list[float]
) -> None:
    body, floor, bounds = scene
    for dt in dts:
        body.step(dt, floor, bounds)
        assert bounds.left <= body.x <= bounds.right
        assert bounds.top <= body.y <= floor


@given(scenes(), steps)
def test_once_landed_a_body_stays_put(scene: tuple[Body, float, Bounds], dts: list[float]) -> None:
    body, floor, bounds = scene
    for _ in range(1000):  # long enough to land from anywhere in these scenes
        if body.step(0.05, floor, bounds):
            break
    assert not body.airborne
    where = (body.x, body.y)
    for dt in dts:
        assert not body.step(dt, floor, bounds)
        assert (body.x, body.y) == where
