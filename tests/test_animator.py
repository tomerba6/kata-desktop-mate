"""kata.animator steps through an animation's frames from elapsed time, without Qt.

The animations here are made up rather than read from kata.json, so the tests don't change when
the sprites are redrawn. Durations are chosen to be exact in binary (fps 2: half a second a frame).
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kata.animator import Animator
from kata.sheet import AnimationInfo

LOOP = AnimationInfo(name="loop", row=0, frames=3, fps=2, loop=True)
ONCE = AnimationInfo(name="once", row=1, frames=3, fps=2, loop=False)
ANIMATIONS = {"loop": LOOP, "once": ONCE}


def test_starts_on_frame_0_of_the_named_animation() -> None:
    animator = Animator(ANIMATIONS, "once")
    assert animator.animation is ONCE
    assert animator.frame == 0
    assert not animator.finished


def test_a_looping_animation_wraps_to_frame_0() -> None:
    animator = Animator(ANIMATIONS, "loop")
    animator.advance(1.0)
    assert animator.frame == 2
    animator.advance(0.5)
    assert animator.frame == 0
    assert not animator.finished


def test_a_one_shot_stops_on_its_last_frame_and_then_finishes() -> None:
    animator = Animator(ANIMATIONS, "once")
    animator.advance(1.0)
    # The last frame is showing but hasn't had its time on screen yet.
    assert (animator.frame, animator.finished) == (2, False)
    animator.advance(0.5)
    assert (animator.frame, animator.finished) == (2, True)
    animator.advance(10.0)
    assert (animator.frame, animator.finished) == (2, True)


def test_play_restarts_at_frame_0_and_clears_finished() -> None:
    animator = Animator(ANIMATIONS, "once")
    animator.advance(2.0)
    animator.play("once")
    assert (animator.frame, animator.finished) == (0, False)
    # Time counts from the restart, not from the start of the first play.
    animator.advance(0.4)
    assert animator.frame == 0


def test_play_switches_to_the_named_animation() -> None:
    animator = Animator(ANIMATIONS, "once")
    animator.advance(0.5)
    animator.play("loop")
    assert animator.animation is LOOP
    assert animator.frame == 0


def test_a_negative_dt_raises() -> None:
    animator = Animator(ANIMATIONS, "loop")
    with pytest.raises(ValueError):
        animator.advance(-0.001)


def test_a_zero_dt_is_allowed_and_changes_nothing() -> None:
    # Two timer ticks can arrive with no measurable time between them.
    animator = Animator(ANIMATIONS, "loop")
    animator.advance(0.5)
    animator.advance(0.0)
    assert animator.frame == 1


def test_many_small_steps_reach_a_frame_boundary() -> None:
    # Twelve float steps of 1/60 s add up to a hair under 0.2 s, one frame at 5 fps. A timer
    # ticking at 60 Hz must still show the next frame then, not one tick late.
    five_fps = AnimationInfo(name="five", row=0, frames=6, fps=5, loop=True)
    animator = Animator({"five": five_fps}, "five")
    for _ in range(12):
        animator.advance(1 / 60)
    assert animator.frame == 1


animations = st.builds(
    AnimationInfo,
    name=st.just("any"),
    row=st.just(0),
    frames=st.integers(min_value=1, max_value=20),
    fps=st.integers(min_value=1, max_value=60),
    loop=st.booleans(),
)
steps = st.lists(st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False))


@given(animations, steps)
def test_the_frame_stays_in_range_and_a_one_shot_only_moves_forward(
    anim: AnimationInfo, dts: list[float]
) -> None:
    animator = Animator({"any": anim}, "any")
    previous = animator.frame
    for dt in dts:
        was_finished = animator.finished
        animator.advance(dt)
        assert 0 <= animator.frame < anim.frames
        if anim.loop:
            assert not animator.finished
        else:
            assert animator.frame >= previous
            assert animator.finished or not was_finished
        previous = animator.frame
