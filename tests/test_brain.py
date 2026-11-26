"""kata.brain decides what Kata does next and for how long, without Qt.

Most tests steer the brain with Scripted, a random.Random whose random() returns the numbers the
test lists. Random.uniform and the weighted Random.choices both draw through random() (checked in
CPython 3.14's source), so the brain's own calls run unchanged. The brain draws, in order: a time
for each state it enters (a fraction of the way through that state's range), a weighted pick when
a state's time is up, and a coin when a walk starts (below 0.5 heads right). A hop draws nothing.

The tests' BehaviourConfig is their own, so tuning the app's defaults doesn't break them. Its times
are exact in binary, so the expected times are exact too. The seeded runs at the end use the
app's defaults, since they check that the real tuning reaches every state.
"""

from __future__ import annotations

import dataclasses
import math
import random
from collections.abc import Callable

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from kata.animator import Animator
from kata.body import Body, PhysicsConfig
from kata.brain import BehaviourConfig, Brain, Facing, State, Weights
from kata.geometry import Bounds
from kata.sheet import read_sheet_info

CONFIG = BehaviourConfig(
    idle_time=(2.25, 6.5),
    walk_time=(3.5, 8.25),
    sit_time=(5.75, 12.5),
    sleep_time=(30.5, 60.25),
    sleep_after=16.0,  # two rounds of the shortest idle and sit: 2 x (2.25 + 5.75)
    turn_speed=60.0,
    after_idle=((State.WALK, 3.0), (State.SIT, 1.0), (State.IDLE, 1.0)),
    after_walk=((State.IDLE, 2.0), (State.SIT, 1.0), (State.WALK, 1.0)),
    after_sit=((State.IDLE, 1.0), (State.WALK, 2.0)),
)
SPEED = 45.0
RANGE = (109.5, 1245.25)  # the walking range: the feet's left and right ends
MIDDLE = 611.4
RIGHTWARD, LEFTWARD = 0.25, 0.75  # coin draws: below 0.5 heads right


class Scripted(random.Random):
    """A Random whose random() gives the listed numbers in turn, then `then` for ever."""

    def __init__(self, *draws: float, then: float = 0.0) -> None:
        super().__init__(0)
        self._draws = list(draws)
        self._then = then

    def random(self) -> float:
        return self._draws.pop(0) if self._draws else self._then


def pick(state: State, weights: Weights) -> float:
    """The random() draw that lands a weighted pick in the middle of `state`'s share."""
    total = sum(weight for _, weight in weights)
    start = 0.0
    for candidate, weight in weights:
        if candidate is state:
            return (start + weight / 2) / total
        start += weight
    raise AssertionError(f"{state} is not among {weights}")


def along(span: tuple[float, float], fraction: float) -> float:
    """The time a draw of `fraction` gives from a state's range."""
    low, high = span
    return low + (high - low) * fraction


def brain(*draws: float, then: float = 0.0) -> Brain:
    return Brain(CONFIG, SPEED, Scripted(*draws, then=then))


def run(b: Brain, seconds: float, x: float = MIDDLE) -> None:
    b.update(seconds, x, RANGE)


def walking(coin: float = RIGHTWARD) -> Brain:
    """A brain 1 s into a walk of 3.5 s, heading right unless the coin says left."""
    b = brain(0.0, pick(State.WALK, CONFIG.after_idle), 0.0, coin)
    run(b, 2.25 + 1.0)
    assert b.state is State.WALK
    return b


# Two rounds of the shortest idle and sit: 16 s, in a sit that ends exactly when the quiet spell
# is long enough to nap.
TWO_ROUNDS = (
    0.0,  # idle 2.25
    pick(State.SIT, CONFIG.after_idle),
    0.0,  # sit 5.75; the quiet spell is 8 s when it ends: too short to nap
    pick(State.IDLE, CONFIG.after_sit),
    0.0,  # idle 2.25
    pick(State.SIT, CONFIG.after_idle),
    0.0,  # sit 5.75, ending at 16 s
)


def asleep(*more: float) -> Brain:
    """A brain just fallen asleep for 45.375 s after 16 s of quiet; `more` are its next draws."""
    b = brain(*TWO_ROUNDS, 0.5, *more)  # sleep 30.5 + 0.5 x 29.75 = 45.375
    run(b, 16.0)
    assert b.state is State.SLEEP
    return b


def idling() -> Brain:
    """A brain 1.25 s into an idle of 3.3125 s."""
    b = brain(0.25)
    run(b, 1.25)
    return b


def walking_left() -> Brain:
    """A brain 1 s into a walk of 3.5 s, heading left."""
    return walking(LEFTWARD)


def sitting() -> Brain:
    """A brain 1 s into a sit of 5.75 s."""
    b = brain(0.0, pick(State.SIT, CONFIG.after_idle), 0.0)
    run(b, 2.25 + 1.0)
    assert b.state is State.SIT
    return b


def hopping() -> Brain:
    """A brain hopping, clicked 1 s into a walk heading right."""
    b = walking()
    b.clicked()
    return b


def held() -> Brain:
    """A brain picked up while it idled."""
    b = brain(0.0)
    b.grabbed()
    return b


def falling() -> Brain:
    """A brain falling: its floor dropped away 1 s into a walk."""
    b = walking()
    b.released(0.0)
    return b


type Snapshot = tuple[State, Facing, float, float]


def snapshot(b: Brain) -> Snapshot:
    """What the brain is doing, which way it faces, and how far into it it is."""
    return b.state, b.facing, b.elapsed, b.time_left


# --- Starting, and the time each state lasts -----------------------------------------------------


def test_the_settings_cannot_be_changed_after_loading() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        CONFIG.sleep_after = 1.0  # type: ignore[misc]


def test_kata_starts_idle_facing_right_for_a_time_from_idle_s_range() -> None:
    b = brain(0.25)
    assert (b.state, b.facing, b.animation) == (State.IDLE, Facing.RIGHT, "idle")
    assert b.time_left == along(CONFIG.idle_time, 0.25)  # 3.3125
    assert b.elapsed == 0.0


def test_time_passes_in_the_current_state() -> None:
    b = brain(0.25)
    run(b, 1.25)
    assert (b.elapsed, b.time_left) == (1.25, 3.3125 - 1.25)


def test_a_state_whose_time_is_used_up_exactly_ends_then() -> None:
    b = brain(0.0, pick(State.SIT, CONFIG.after_idle), 0.0)
    run(b, 2.25 - 2**-10)  # a hair short of idle's 2.25
    assert (b.state, b.time_left) == (State.IDLE, 2**-10)
    run(b, 2**-10)
    assert b.state is State.SIT


def test_time_left_over_carries_into_the_next_state() -> None:
    b = brain(0.0, pick(State.SIT, CONFIG.after_idle), 0.0)
    run(b, 2.25 + 0.75)
    assert (b.state, b.elapsed, b.time_left) == (State.SIT, 0.75, 5.75 - 0.75)


def test_one_long_update_or_many_short_ones_end_the_same() -> None:
    # 1/64 is exact in binary, so 1920 of them add up to exactly 30.
    once, often = Brain(CONFIG, SPEED, random.Random(5)), Brain(CONFIG, SPEED, random.Random(5))
    once.update(30.0, MIDDLE, RANGE)
    for _ in range(1920):
        often.update(1 / 64, MIDDLE, RANGE)
    assert (often.state, often.facing) == (once.state, once.facing)
    assert often.elapsed == pytest.approx(once.elapsed, abs=1e-9)
    assert often.time_left == pytest.approx(once.time_left, abs=1e-9)


def test_a_negative_dt_raises() -> None:
    with pytest.raises(ValueError):
        brain().update(-0.001, MIDDLE, RANGE)


# --- What comes next ---------------------------------------------------------------------------


@pytest.mark.parametrize("after", [State.WALK, State.SIT, State.IDLE])
def test_after_idle_the_next_state_is_a_weighted_pick(after: State) -> None:
    b = brain(0.0, pick(after, CONFIG.after_idle), 0.5, RIGHTWARD)
    run(b, 2.25)
    assert b.state is after
    span = {State.WALK: CONFIG.walk_time, State.SIT: CONFIG.sit_time, State.IDLE: CONFIG.idle_time}
    assert b.time_left == along(span[after], 0.5)


@pytest.mark.parametrize("after", [State.IDLE, State.SIT, State.WALK])
def test_after_a_walk_the_next_state_is_a_weighted_pick(after: State) -> None:
    b = brain(0.0, pick(State.WALK, CONFIG.after_idle), 0.0, RIGHTWARD, pick(after, CONFIG.after_walk))
    run(b, 2.25 + 3.5)
    assert b.state is after


@pytest.mark.parametrize("after", [State.IDLE, State.WALK])
def test_after_a_short_quiet_sit_the_next_state_is_a_weighted_pick(after: State) -> None:
    b = brain(0.0, pick(State.SIT, CONFIG.after_idle), 0.0, pick(after, CONFIG.after_sit))
    run(b, 2.25 + 5.75)  # 8 s of quiet: half the spell a nap needs
    assert b.state is after


def test_sitting_turns_to_sleep_once_the_quiet_spell_is_long_enough() -> None:
    b = asleep()
    assert (b.animation, b.time_left, b.walk_speed) == ("sleep", 45.375, 0.0)


def test_a_nap_ends_in_idle() -> None:
    b = asleep(0.0)
    run(b, 45.375)
    assert (b.state, b.time_left) == (State.IDLE, 2.25)  # woken, with no pick drawn


# A round of idle and sit that ends half a second short of the 16 s quiet spell.
SHORT_OF_A_NAP = (
    0.5,  # idle 4.375
    pick(State.SIT, CONFIG.after_idle),
    5.375 / 6.75,  # sit 11.125: it ends 15.5 s in
    pick(State.WALK, CONFIG.after_sit),
)


def quiet_since(event: str, *draws: float) -> Brain:
    """A brain whose quiet spell `event` has just begun, with `draws` as its next draws."""
    if event == "start":
        return brain(*draws)
    if event == "click":
        b = brain(*draws)
        b.clicked()
        b.finished()  # the hop
        return b
    if event == "grab":
        b = brain(0.0, *draws)
        b.grabbed()
        b.released(0.0)
        b.landed()
        return b
    b = asleep(*draws)
    run(b, 45.375)  # the nap ends
    return b


@pytest.mark.parametrize("event", ["start", "click", "grab", "nap"])
def test_the_quiet_spell_counts_from_zero(event: str) -> None:
    b = quiet_since(event, *SHORT_OF_A_NAP)
    run(b, 15.75)
    assert b.state is State.WALK  # the sit ended with 15.5 s of quiet: no nap
    b = quiet_since(event, *TWO_ROUNDS, 0.5)
    run(b, 16.0)
    assert b.state is State.SLEEP  # it ended with exactly 16 s: a nap


# --- What the window tells it -------------------------------------------------------------------


def test_a_click_wakes_a_sleeping_kata_into_idle_with_no_hop() -> None:
    b = asleep()
    b.clicked()
    awake = snapshot(b)
    assert awake == (State.IDLE, Facing.RIGHT, 0.0, 2.25)
    b.clicked()  # the next click hops
    assert snapshot(b) == (State.HAPPY, Facing.RIGHT, 0.0, math.inf)
    b.finished()
    assert snapshot(b) == awake


def test_a_click_mid_sit_restarts_the_quiet_spell() -> None:
    b = brain(*TWO_ROUNDS, pick(State.WALK, CONFIG.after_sit))
    run(b, 15.0)  # in the second sit, 1 s before it ends
    b.clicked()
    b.finished()  # the hop
    run(b, 1.0)  # the sit ends after 1 s of quiet, not 16: no nap
    assert b.state is State.WALK


@pytest.mark.parametrize("make", [brain, walking, asleep, hopping])
def test_a_grab_holds_kata_whatever_it_was_doing(make: Callable[[], Brain]) -> None:
    b = make()
    b.grabbed()
    assert (b.state, b.animation, b.walk_speed) == (State.HELD, "held", 0.0)
    run(b, 500.0)  # time doesn't run out while held
    assert b.state is State.HELD
    assert b.time_left == math.inf


def test_a_release_drops_kata_and_a_landing_stands_it_idle() -> None:
    b = brain(0.0, then=0.5)
    b.grabbed()
    b.released(0.0)
    assert (b.state, b.animation) == (State.FALL, "fall")
    run(b, 500.0)  # however long it falls
    assert (b.state, b.time_left) == (State.FALL, math.inf)
    b.landed()
    assert b.state is State.IDLE
    assert b.time_left == along(CONFIG.idle_time, 0.5)


@pytest.mark.parametrize("make", [walking, hopping])
def test_a_floor_dropping_away_drops_a_standing_kata(make: Callable[[], Brain]) -> None:
    b = make()
    b.released(0.0)
    assert b.state is State.FALL


@pytest.mark.parametrize("make", [brain, walking, asleep, hopping])
def test_a_landing_means_nothing_unless_kata_is_falling(make: Callable[[], Brain]) -> None:
    b = make()
    before = (b.state, b.elapsed, b.time_left)
    b.landed()
    assert (b.state, b.elapsed, b.time_left) == before
    b.grabbed()
    b.landed()
    assert b.state is State.HELD


def test_a_throw_turns_kata_to_face_its_flight() -> None:
    b = brain()
    b.grabbed()
    b.released(-60.0)  # exactly turn_speed, leftwards
    assert (b.state, b.facing) == (State.FALL, Facing.LEFT)
    b.grabbed()
    b.released(59.5)  # slower: a shaky drop, not a throw
    assert (b.state, b.facing) == (State.FALL, Facing.LEFT)
    b.grabbed()
    b.released(60.0)
    assert (b.state, b.facing) == (State.FALL, Facing.RIGHT)
    b.grabbed()
    b.released(-59.5)
    assert (b.state, b.facing) == (State.FALL, Facing.RIGHT)
    b.grabbed()
    b.released(-250.0)  # a real flick, well past the threshold
    assert (b.state, b.facing) == (State.FALL, Facing.LEFT)
    b.grabbed()
    b.released(250.0)
    assert (b.state, b.facing) == (State.FALL, Facing.RIGHT)


# --- A click: a hop -----------------------------------------------------------------------------

AWAKE = [idling, walking, walking_left, sitting]


@pytest.mark.parametrize("make", AWAKE)
def test_a_click_on_an_awake_kata_starts_a_hop_on_the_spot(make: Callable[[], Brain]) -> None:
    b = make()
    facing = b.facing
    b.clicked()
    assert snapshot(b) == (State.HAPPY, facing, 0.0, math.inf)
    assert (b.animation, b.walk_velocity) == ("happy", 0.0)


@pytest.mark.parametrize("make", AWAKE)
def test_when_the_hop_finishes_kata_carries_on_where_it_left_off(make: Callable[[], Brain]) -> None:
    b = make()
    before = snapshot(b)
    b.clicked()
    b.finished()
    assert snapshot(b) == before


def test_time_stands_still_for_the_interrupted_state_during_a_hop() -> None:
    b = walking()  # 1 s into a walk of 3.5 s, heading right
    before = snapshot(b)
    b.clicked()
    run(b, 100.0, x=RANGE[1])  # far past the walk's end, at the right end of the range
    assert snapshot(b) == (State.HAPPY, Facing.RIGHT, 0.0, math.inf)
    b.finished()
    assert snapshot(b) == before  # the same walk, heading the same way


def test_a_long_hop_does_not_count_towards_the_quiet_spell() -> None:
    b = brain(*TWO_ROUNDS, pick(State.WALK, CONFIG.after_sit))
    run(b, 15.0)  # in the second sit, 1 s before it ends
    b.clicked()  # the quiet spell restarts
    run(b, 100.0)  # a hop as long as this never happens, but the spell stays at 0 through it
    b.finished()
    run(b, 1.0)  # the sit ends after 1 s of quiet: no nap
    assert b.state is State.WALK


def test_a_hop_draws_nothing_from_the_random() -> None:
    # After the walk come a pick and a sit's time. Had the hop drawn a number, the pick would get
    # the sit's 0.125, which lands on idle.
    b = brain(
        0.0,  # idle 2.25
        pick(State.WALK, CONFIG.after_idle),
        0.0,  # walk 3.5
        RIGHTWARD,
        pick(State.SIT, CONFIG.after_walk),
        0.125,  # the sit's time
    )
    run(b, 2.25 + 1.0)  # 1 s into a walk of 3.5 s
    b.clicked()
    b.finished()
    run(b, 2.5)  # the rest of the walk
    assert (b.state, b.time_left) == (State.SIT, along(CONFIG.sit_time, 0.125))


def test_clicks_during_a_hop_are_ignored_so_one_finish_ends_it() -> None:
    b = walking()
    before = snapshot(b)
    b.clicked()
    for _ in range(10):
        b.clicked()
    assert snapshot(b) == (State.HAPPY, Facing.RIGHT, 0.0, math.inf)
    b.finished()
    assert snapshot(b) == before  # not stuck hopping, and no hop stacked on another
    b.finished()
    assert snapshot(b) == before


@pytest.mark.parametrize("make", [idling, walking, sitting, asleep, held, falling])
def test_a_finish_means_nothing_unless_kata_is_hopping(make: Callable[[], Brain]) -> None:
    b = make()
    before = snapshot(b)
    b.finished()
    assert snapshot(b) == before


@pytest.mark.parametrize("make", [held, falling])
def test_a_click_while_held_or_falling_changes_nothing(make: Callable[[], Brain]) -> None:
    b = make()
    before = snapshot(b)
    b.clicked()
    assert snapshot(b) == before


def test_a_click_while_falling_does_not_restart_the_quiet_spell() -> None:
    b = brain(0.0, 0.0, pick(State.SIT, CONFIG.after_idle), 0.9375)
    run(b, 2.0)  # 2 s of quiet
    b.released(0.0)  # the floor drops away
    b.clicked()
    b.landed()  # idle for 2.25 s, then a sit of 5.75 + 0.9375 x 6.75 = 12.078125 s
    run(b, 2.25 + 12.078125)  # the sit ends with 16.328125 s of quiet: a nap
    assert b.state is State.SLEEP  # restarted by the click, the spell would be 14.328125 s


def test_a_grab_mid_hop_cancels_it_and_after_the_fall_kata_stands_idle() -> None:
    b = brain(0.0, pick(State.WALK, CONFIG.after_idle), 0.0, RIGHTWARD, then=0.5)
    run(b, 2.25 + 1.0)  # 1 s into a walk
    b.clicked()
    b.grabbed()
    b.finished()  # a hop cut short has nothing to go back to
    assert snapshot(b) == (State.HELD, Facing.RIGHT, 0.0, math.inf)
    b.released(0.0)
    b.finished()
    assert snapshot(b) == (State.FALL, Facing.RIGHT, 0.0, math.inf)
    b.landed()
    landed = snapshot(b)
    assert landed == (State.IDLE, Facing.RIGHT, 0.0, along(CONFIG.idle_time, 0.5))  # not the walk
    b.finished()
    assert snapshot(b) == landed


# --- Walking ------------------------------------------------------------------------------------


def test_walk_speed_is_the_sheet_speed_only_while_walking() -> None:
    assert brain().walk_speed == 0.0
    assert walking().walk_speed == SPEED


def test_the_walking_velocity_points_the_way_kata_faces() -> None:
    # The window moves the body at this: negative is leftwards, as on screen.
    assert walking(RIGHTWARD).walk_velocity == SPEED
    assert walking(LEFTWARD).walk_velocity == -SPEED
    assert brain().walk_velocity == 0.0


@pytest.mark.parametrize(
    ("coin", "facing"), [(RIGHTWARD, Facing.RIGHT), (0.5, Facing.LEFT), (LEFTWARD, Facing.LEFT)]
)
def test_a_walk_in_the_middle_heads_the_way_the_coin_says(coin: float, facing: Facing) -> None:
    assert walking(coin).facing is facing


def test_a_walk_that_starts_at_an_edge_heads_away_from_it() -> None:
    b = brain(0.0, pick(State.WALK, CONFIG.after_idle), 0.0, RIGHTWARD)
    run(b, 2.25, x=RANGE[1])  # the coin says right, but Kata is at the right end
    assert (b.state, b.facing) == (State.WALK, Facing.LEFT)
    b = brain(0.0, pick(State.WALK, CONFIG.after_idle), 0.0, LEFTWARD)
    run(b, 2.25, x=RANGE[0])
    assert (b.state, b.facing) == (State.WALK, Facing.RIGHT)


def test_walking_turns_at_both_ends_of_the_range() -> None:
    b = walking(RIGHTWARD)
    run(b, 0.25, x=RANGE[1] - 0.5)  # not there yet
    assert (b.state, b.facing) == (State.WALK, Facing.RIGHT)
    run(b, 0.25, x=RANGE[1])
    assert (b.state, b.facing) == (State.WALK, Facing.LEFT)
    run(b, 0.25, x=RANGE[0] + 0.5)
    assert (b.state, b.facing) == (State.WALK, Facing.LEFT)
    run(b, 0.25, x=RANGE[0])
    assert (b.state, b.facing) == (State.WALK, Facing.RIGHT)
    run(b, 0.25, x=RANGE[1] + 3.0)  # past the end, after the range narrowed: turns too
    assert (b.state, b.facing) == (State.WALK, Facing.LEFT)
    run(b, 0.25, x=RANGE[0] - 3.0)  # and past the left end
    assert (b.state, b.facing) == (State.WALK, Facing.RIGHT)


def test_standing_still_at_an_edge_turns_nothing() -> None:
    b = brain(0.25)
    run(b, 1.0, x=RANGE[1])
    assert b.facing is Facing.RIGHT


# --- Any sequence of events ----------------------------------------------------------------------

SHEET = read_sheet_info()
GROUND = (State.IDLE, State.WALK, State.SIT, State.SLEEP)


def longest(config: BehaviourConfig, state: State) -> float:
    return config.time_range(state)[1]


class BrainMachine(RuleBasedStateMachine):
    """Random sequences of updates and of what the window tells the brain.

    An Animator over the real sheet stands in for the window's, wired the way PetWindow wires it:
    it plays the brain's animation, advances on each update, and when it reports finished, the
    brain is told.
    """

    def __init__(self) -> None:
        super().__init__()
        self.brain = Brain(CONFIG, SPEED, random.Random(0))
        self.animator = Animator(SHEET.animations, self.brain.animation)
        self.held = False
        self.interrupted: Snapshot | None = None  # what the hop playing now interrupted

    @initialize(seed=st.integers(0, 2**32 - 1))
    def seed(self, seed: int) -> None:
        self.brain = Brain(CONFIG, SPEED, random.Random(seed))
        self.animator = Animator(SHEET.animations, self.brain.animation)

    def show(self) -> None:
        """Play the brain's animation unless it is playing already, as PetWindow.follow_brain does."""
        if self.animator.animation.name != self.brain.animation:
            self.animator.play(self.brain.animation)

    @rule(dt=st.floats(0, 30), x=st.floats(RANGE[0], RANGE[1]))
    def update(self, dt: float, x: float) -> None:
        self.brain.update(dt, x, RANGE)
        self.show()
        self.animator.advance(dt)
        if self.animator.finished:
            self.brain.finished()
            self.show()
            assert self.interrupted is not None  # only the hop is a one-shot
            assert snapshot(self.brain) == self.interrupted  # back to what the hop interrupted
            self.interrupted = None

    @rule()
    def grabbed(self) -> None:
        self.brain.grabbed()
        self.held = True
        self.interrupted = None  # a grab cancels a hop
        self.show()

    @rule(vx=st.floats(-3000, 3000))
    def released(self, vx: float) -> None:
        self.brain.released(vx)
        self.held = False
        self.interrupted = None  # and so does a fall
        self.show()

    @rule()
    def landed(self) -> None:
        self.brain.landed()
        self.show()

    @rule()
    def clicked(self) -> None:
        before = snapshot(self.brain)
        self.brain.clicked()
        if self.brain.state is State.HAPPY and before[0] is not State.HAPPY:
            self.interrupted = before
        self.show()

    @invariant()
    def the_animation_is_one_the_sheet_has(self) -> None:
        assert self.brain.animation in SHEET.animations

    @invariant()
    def happy_only_while_the_hop_plays(self) -> None:
        # Once `happy` has finished, the brain has left HAPPY, so no sequence of clicks leaves it stuck.
        if self.brain.state is State.HAPPY:
            assert self.animator.animation.name == "happy"
            assert not self.animator.finished

    @invariant()
    def held_only_between_a_grab_and_the_next_release(self) -> None:
        assert (self.brain.state is State.HELD) == self.held

    @invariant()
    def no_state_outlasts_its_range(self) -> None:
        state = self.brain.state
        if state in GROUND:
            assert 0.0 <= self.brain.elapsed <= longest(CONFIG, state)
            assert self.brain.time_left >= 0.0

    @invariant()
    def it_walks_only_while_walking(self) -> None:
        assert self.brain.walk_speed == (SPEED if self.brain.state is State.WALK else 0.0)


test_any_sequence_of_events = pytest.mark.slow(BrainMachine.TestCase)


# --- Seeded runs of the app's own tuning ------------------------------------------------------

SEEDS = 180  # 200 took 1.06 s on the dev machine; the plan's budget for these runs is 1 s
MINUTES = 10
FLOOR = 720.0
BOUNDS = Bounds(left=109.0, right=1245.0, top=164.0)


def simulate(seed: int) -> tuple[set[State], set[Facing]]:
    """Ten minutes of a brain and a body left alone; returns the states seen and the walks' facings.

    The step sizes come from their own Random, so they don't shift the brain's draws.
    """
    config = BehaviourConfig()
    limit = {state: longest(config, state) for state in GROUND}  # looked up once: this loop is hot
    brain = Brain(config, SPEED, random.Random(seed))
    steps = random.Random(-1 - seed)
    body = Body(611.4, FLOOR, PhysicsConfig())
    walk_range = (BOUNDS.left, BOUNDS.right)
    seen: set[State] = set()
    walked: set[Facing] = set()
    shown: tuple[State, Facing] | None = None
    t = 0.0
    while t < MINUTES * 60:
        dt = steps.uniform(1 / 60, 1 / 4)
        t += dt
        brain.update(dt, body.x, walk_range)
        body.step(dt, FLOOR, BOUNDS, walk=brain.walk_velocity)
        state = brain.state
        # An assert's message is only built when it fails, so the f-strings cost nothing here.
        assert BOUNDS.left <= body.x <= BOUNDS.right, f"seed {seed}, {t:.3f} s in, {state.name}"
        assert body.y == FLOOR and not body.airborne, f"seed {seed}, {t:.3f} s in, {state.name}"
        assert brain.elapsed <= limit[state], f"seed {seed}, {t:.3f} s in, {state.name}"
        if (state, brain.facing) != shown:
            shown = (state, brain.facing)
            seen.add(state)
            if state is State.WALK:
                walked.add(brain.facing)
    return seen, walked


@pytest.mark.slow
def test_left_alone_kata_wanders_sits_and_naps_and_stays_inside_the_bounds() -> None:
    seen: set[State] = set()
    walked: set[Facing] = set()
    for seed in range(SEEDS):
        states, facings = simulate(seed)
        seen |= states
        walked |= facings
    assert seen == set(GROUND)
    assert walked == {Facing.LEFT, Facing.RIGHT}
