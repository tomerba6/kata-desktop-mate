"""Developer switches read from the environment, and the line format KATA_LOG prints.

A switch is on when its variable is 1 or true, in any case. Anything else is off, "yes" included,
so there is one way to spell on. The environment is passed in, so tests never touch the real one.

This module is plain Python with no Qt.
"""

from __future__ import annotations

from collections.abc import Mapping

ON = frozenset({"1", "true"})


def is_on(name: str, environ: Mapping[str, str]) -> bool:
    """Whether the switch `name` is on in `environ` (pass os.environ in the app)."""
    return environ.get(name, "").lower() in ON


def log_line(seconds: float, event: str, **fields: object) -> str:
    """One KATA_LOG line: `kata <seconds since start> <event> key=value ...`.

    A tuple value is written with commas between its items, so a point reads `feet=640,720`.
    """
    parts = ["kata", f"{seconds:.3f}", event]
    for key, value in fields.items():
        text = ",".join(str(item) for item in value) if isinstance(value, tuple) else str(value)
        parts.append(f"{key}={text}")
    return " ".join(parts)
