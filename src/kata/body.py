"""Kata's body: the feet point, its velocity, gravity, and landing on the floor.

Positions are Qt screen coordinates as floats, with y growing downwards; the window is placed
from the rounded feet point. step() moves the body on by dt seconds of real time. The fall is
worked out exactly for constant gravity, with the speed capped, so where Kata is doesn't depend on
how the time was cut into steps.

A body is standing or airborne. Standing, it stays on the floor, and follows it up if the floor
rises (a taskbar appearing). If the floor drops away, it starts to fall. A throw or a hold makes
it airborne, and step() reports True on the step it lands. Landing stops all motion; hitting a side
edge stops only the sideways speed, and hitting the top stops upward speed.

This module is plain Python with no Qt, so it is tested without a window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from kata.geometry import Bounds


@dataclass(frozen=True)
class PhysicsConfig:
    """How Kata moves through the air, in Qt units and seconds."""

    gravity: float = 2400.0  # per s²: a drop down a 720-high screen lands in about 0.77 s
    max_fall_speed: float = 2400.0  # per s
    max_throw_speed: float = 1500.0  # per s, the speed a release can give Kata


class Body:
    def __init__(self, x: float, y: float, config: PhysicsConfig) -> None:
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.config = config
        self._airborne = False

    @property
    def airborne(self) -> bool:
        """True from a throw, a hold or a floor dropping away, until the body lands."""
        return self._airborne

    def hold(self, x: float, y: float, floor_y: float, bounds: Bounds) -> None:
        """Put the body where the pointer has it, inside the bounds and not below the floor."""
        self.x = min(max(x, bounds.left), bounds.right)
        self.y = min(max(y, bounds.top), floor_y)
        self.vx = self.vy = 0.0
        self._airborne = True

    def throw(self, vx: float, vy: float) -> None:
        """Set off at this velocity, cut down to the throw cap if faster, in the same direction."""
        speed = math.hypot(vx, vy)
        cap = self.config.max_throw_speed
        scale = cap / speed if speed > cap else 1.0
        self.vx, self.vy = vx * scale, vy * scale
        self._airborne = True

    def step(self, dt: float, floor_y: float, bounds: Bounds) -> bool:
        """Move on by dt seconds. True on the step the body lands, and only then."""
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        if not self._airborne:
            if self.y >= floor_y:
                self.y = floor_y  # follow a floor that rose
                return False
            self._airborne = True  # the floor dropped away

        fall, self.vy = _fall(self.vy, dt, self.config.gravity, self.config.max_fall_speed)
        self.x += self.vx * dt
        self.y += fall
        if self.x < bounds.left or self.x > bounds.right:
            self.x = min(max(self.x, bounds.left), bounds.right)
            self.vx = 0.0
        if self.y < bounds.top:
            self.y = bounds.top
            self.vy = 0.0
        if self.y >= floor_y:
            self.y = floor_y
            self.vx = self.vy = 0.0
            self._airborne = False
            return True
        return False


def _fall(v0: float, dt: float, gravity: float, cap: float) -> tuple[float, float]:
    """How far a body moving down at v0 falls in dt seconds, and its speed then.

    Exact for constant gravity: it speeds up until it reaches the cap, then keeps the cap. A
    negative v0 is upward speed, slowed by the same gravity.
    """
    v0 = min(v0, cap)
    to_cap = (cap - v0) / gravity  # seconds until the cap is reached
    if dt <= to_cap:
        return v0 * dt + gravity * dt * dt / 2, v0 + gravity * dt
    return v0 * to_cap + gravity * to_cap * to_cap / 2 + cap * (dt - to_cap), cap
