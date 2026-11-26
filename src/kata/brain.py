"""Kata's brain: what it does next, and for how long.

Left alone, Kata is in one of four states it picks itself: IDLE, WALK, SIT and SLEEP. Each lasts a
time drawn from its range in BehaviourConfig; when that time is up, the next state is a weighted
pick, except that a sit ending after a long quiet spell (no click or grab, and no nap just ended)
becomes a nap, and a nap always ends in IDLE. update(dt) carries leftover time into the next
state, so however the time is cut into steps, no state outlasts its range and the outcome is the
same.

Three more states come from outside, through the window's events: grabbed() goes to HELD from
anything, released(vx) to FALL (a floor dropping away under Kata counts too), and landed() back to
IDLE. A release with enough sideways speed turns Kata to face the way it flies.

clicked() wakes a sleeping Kata into IDLE. Idling, walking or sitting, Kata hops instead: HAPPY,
on the spot, until the window reports with finished() that the `happy` animation has played. Then
Kata goes back to what the click interrupted, with the time it had left. A click while Kata hops,
is held or falls is ignored, and a grab or a fall mid-hop cancels the hop.

HELD, FALL and HAPPY end on the window's word, not on the clock. While Kata is in one of them, no
time passes for the brain, the quiet spell included, and nothing is drawn from the random.Random,
so a hop leaves what Kata does afterwards as it would have been.

While walking, Kata heads left or right by a coin and turns at either end of its walking range, so
a walk that starts at an end heads away from it. The window moves the body at walk_velocity.

This module is plain Python with no Qt. Time comes in as dt and randomness as an injected
random.Random, so the tests choose both.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum


class State(Enum):
    """What Kata is doing. Each value is the name of the animation it plays."""

    IDLE = "idle"
    WALK = "walk"
    SIT = "sit"
    SLEEP = "sleep"
    HAPPY = "happy"
    HELD = "held"
    FALL = "fall"


# The states that last until the window ends them, rather than for a time drawn from a range.
UNTIMED = (State.HAPPY, State.HELD, State.FALL)


class Facing(Enum):
    """Which way Kata looks, and the sign of its walking speed. The sprites are drawn facing right."""

    LEFT = -1
    RIGHT = 1


type Weights = tuple[tuple[State, float], ...]


@dataclass(frozen=True)
class BehaviourConfig:
    """How Kata behaves when left alone. Times in seconds, speeds in screen pixels per second."""

    idle_time: tuple[float, float] = (2.0, 6.0)  # each stay lasts a random time in this range
    walk_time: tuple[float, float] = (3.0, 8.0)
    sit_time: tuple[float, float] = (5.0, 12.0)
    sleep_time: tuple[float, float] = (30.0, 60.0)
    sleep_after: float = 90.0  # quiet this long, and the next sit to end becomes a nap
    turn_speed: float = 60.0  # a release this fast sideways turns Kata; slower is a shaky drop
    after_idle: Weights = ((State.WALK, 3.0), (State.SIT, 1.0), (State.IDLE, 1.0))
    after_walk: Weights = ((State.IDLE, 2.0), (State.SIT, 1.0), (State.WALK, 1.0))
    after_sit: Weights = ((State.IDLE, 1.0), (State.WALK, 2.0))

    def time_range(self, state: State) -> tuple[float, float]:
        """How long a stay in `state` may last. HAPPY, HELD and FALL last until the window says."""
        ranges = {
            State.IDLE: self.idle_time,
            State.WALK: self.walk_time,
            State.SIT: self.sit_time,
            State.SLEEP: self.sleep_time,
        }
        return ranges.get(state, (math.inf, math.inf))

    def weights_after(self, state: State) -> Weights:
        """What may follow `state`, and how likely each is."""
        return {State.IDLE: self.after_idle, State.WALK: self.after_walk, State.SIT: self.after_sit}[state]


class Brain:
    # What Kata is doing, and how far into it: set by _enter(), and put back by finished().
    _state: State
    _elapsed: float
    _duration: float

    def __init__(self, config: BehaviourConfig, walk_speed: float, rng: random.Random) -> None:
        self._config = config
        self._speed = walk_speed
        self._rng = rng
        self._facing = Facing.RIGHT
        self._quiet = 0.0  # seconds since the last click, grab or nap
        self._interrupted: tuple[State, float, float] | None = None  # what a hop goes back to
        self._enter(State.IDLE)

    @property
    def state(self) -> State:
        return self._state

    @property
    def animation(self) -> str:
        """The name of the animation to play."""
        return self._state.value

    @property
    def facing(self) -> Facing:
        return self._facing

    @property
    def walk_speed(self) -> float:
        """How fast to walk, in screen pixels per second: the sheet's speed while walking, else 0."""
        return self._speed if self._state is State.WALK else 0.0

    @property
    def walk_velocity(self) -> float:
        """The walking speed with its direction: negative is leftwards, as on screen."""
        return self._facing.value * self.walk_speed

    @property
    def elapsed(self) -> float:
        """Seconds spent in the current state so far."""
        return self._elapsed

    @property
    def time_left(self) -> float:
        """Seconds until the current state ends; infinite while hopping, held or falling."""
        return self._duration - self._elapsed

    def update(self, dt: float, x: float, walk_range: tuple[float, float]) -> None:
        """Move on by dt seconds, with the feet at column x and the walking range's two ends."""
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        if self._state in UNTIMED:
            return
        left, right = walk_range
        while True:
            if self._state is State.WALK:
                self._turn_at_the_ends(x, left, right)
            remaining = self._duration - self._elapsed
            if dt < remaining:
                self._elapsed += dt
                self._quiet += dt
                return
            dt -= remaining
            self._quiet += remaining
            self._next()

    def grabbed(self) -> None:
        """Picked up: held until released, whatever Kata was doing."""
        self._quiet = 0.0
        self._enter(State.HELD)

    def released(self, vx: float) -> None:
        """Let go at sideways speed vx, or the floor dropped away (vx 0): Kata falls."""
        if vx >= self._config.turn_speed:
            self._facing = Facing.RIGHT
        elif vx <= -self._config.turn_speed:
            self._facing = Facing.LEFT
        self._enter(State.FALL)

    def landed(self) -> None:
        """The body touched the floor. Ends a fall; means nothing otherwise."""
        if self._state is State.FALL:
            self._enter(State.IDLE)

    def clicked(self) -> None:
        """A click on Kata: it wakes a nap, or else hops. Either way the quiet spell restarts."""
        if self._state in UNTIMED:
            return  # hopping already, held or falling: the click means nothing
        self._quiet = 0.0
        if self._state is State.SLEEP:
            self._enter(State.IDLE)
        else:
            self._interrupted = (self._state, self._elapsed, self._duration)
            self._enter(State.HAPPY)

    def finished(self) -> None:
        """The one-shot animation has played to its end. Ends a hop; means nothing otherwise."""
        if self._state is State.HAPPY:
            assert self._interrupted is not None  # every hop starts by keeping what it interrupted
            self._state, self._elapsed, self._duration = self._interrupted

    def _next(self) -> None:
        """The current state's time is up: pick what follows."""
        if self._state is State.SLEEP:
            self._quiet = 0.0
            self._enter(State.IDLE)
        elif self._state is State.SIT and self._quiet >= self._config.sleep_after:
            self._enter(State.SLEEP)
        else:
            weights = self._config.weights_after(self._state)
            states = [state for state, _ in weights]
            (chosen,) = self._rng.choices(states, weights=[weight for _, weight in weights])
            self._enter(chosen)
            if chosen is State.WALK:
                # By a coin. At an end of the range, the turn in update() runs straight after this
                # and sends Kata away from it, so the coin needn't look at x.
                self._facing = Facing.RIGHT if self._rng.random() < 0.5 else Facing.LEFT

    def _enter(self, state: State) -> None:
        """Start `state` afresh, with a time drawn from its range (none for the untimed states)."""
        self._state = state
        self._elapsed = 0.0
        if state in UNTIMED:
            self._duration = math.inf
        else:
            self._duration = self._rng.uniform(*self._config.time_range(state))

    def _turn_at_the_ends(self, x: float, left: float, right: float) -> None:
        """Walking into either end of the range, turn round."""
        if self._facing is Facing.RIGHT and x >= right:
            self._facing = Facing.LEFT
        elif self._facing is Facing.LEFT and x <= left:
            self._facing = Facing.RIGHT
