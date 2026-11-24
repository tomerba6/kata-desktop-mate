"""Which frame of which animation Kata shows, worked out from elapsed time.

The window feeds it real elapsed time with advance(dt) and draws whatever frame it reports. A
looping animation wraps round for ever; a one-shot stays on its last frame and reports finished
once that frame has had its time on screen, so the caller knows to play something else.

This module is plain Python with no Qt, so it is tested without a window.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from kata.sheet import AnimationInfo

# Elapsed time is a sum of float steps, which can land a hair short of a frame boundary: twelve
# steps of 1/60 s add up to 0.19999999999999998, not 0.2. Without this slack, measured in frames,
# the next frame would show a whole tick late.
FRAME_SLACK = 1e-4


class Animator:
    def __init__(self, animations: Mapping[str, AnimationInfo], first: str) -> None:
        self._animations = animations
        self.play(first)

    @property
    def animation(self) -> AnimationInfo:
        """The animation playing now."""
        return self._animation

    @property
    def frame(self) -> int:
        """The frame to draw, counted from 0."""
        return self._frame

    @property
    def finished(self) -> bool:
        """True once a one-shot has shown its last frame for a full frame's time. Never for loops."""
        return self._finished

    def play(self, name: str) -> None:
        """Start the named animation from frame 0, even if it is already playing."""
        self._animation = self._animations[name]
        self._elapsed = 0.0
        self._frame = 0
        self._finished = False

    def advance(self, dt: float) -> None:
        """Move on by dt seconds of real time."""
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        self._elapsed += dt
        anim = self._animation
        steps = math.floor(self._elapsed * anim.fps + FRAME_SLACK)
        if anim.loop:
            self._frame = steps % anim.frames
        else:
            self._frame = min(steps, anim.frames - 1)
            self._finished = steps >= anim.frames
