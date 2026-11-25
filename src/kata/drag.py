"""One press of the mouse button on Kata: a click or a drag, and how fast it was let go.

A press becomes a drag once the pointer has moved `threshold` pixels from where it was pressed,
counted sideways plus up and down: Qt's own rule (QPoint.manhattanLength() against
QApplication.startDragDistance()). A press released before that is a click.

The release speed is the pointer's average velocity over the last `window` seconds before the
release. A pointer held still for that long before letting go gives no speed, so a careful drop
falls straight down.

This module is plain Python with no Qt. Positions are screen coordinates and times are seconds,
both passed in, so the tests choose them.
"""

from __future__ import annotations

type Point = tuple[float, float]


class Grip:
    def __init__(self, at: Point, time: float, threshold: int, window: float) -> None:
        self._start = at
        self._threshold = threshold
        self._window = window
        self._samples: list[tuple[float, Point]] = [(time, at)]
        self._dragging = False

    @property
    def dragging(self) -> bool:
        """True once the pointer has moved as far as the threshold."""
        return self._dragging

    def move(self, at: Point, time: float) -> bool:
        """The pointer moved. True on the move that turns the press into a drag, and only then."""
        if time < self._samples[-1][0]:
            raise ValueError(f"time went backwards: {time} after {self._samples[-1][0]}")
        self._samples.append((time, at))
        # Only the last `window` seconds matter for the speed; keep the list short.
        self._samples = [(t, p) for t, p in self._samples if t >= time - self._window]
        if self._dragging:
            return False
        distance = abs(at[0] - self._start[0]) + abs(at[1] - self._start[1])
        self._dragging = distance >= self._threshold
        return self._dragging

    def release(self, at: Point, time: float) -> bool:
        """The button came up. True if the press was a click: it never moved as far as a drag."""
        self.move(at, time)
        return not self._dragging

    def velocity(self) -> tuple[float, float]:
        """The pointer's average velocity over the last `window` seconds, in pixels per second."""
        (t0, (x0, y0)), (t1, (x1, y1)) = self._samples[0], self._samples[-1]
        if t1 == t0:
            return 0.0, 0.0
        return (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
