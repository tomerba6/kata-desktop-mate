"""Shared test setup.

Qt's offscreen platform. Windows are made, moved and sent events, but never drawn on a screen,
so the tests that build a PetWindow open nothing on your desktop and run the same on CI. It is
set here because pytest loads this file before any test module imports Qt, and it overrides any
platform already in the environment.

Hypothesis profiles. Local runs use Hypothesis's defaults: fresh random inputs each run, with any
failure saved in .hypothesis/ and tried first next time. CI runs `pytest --hypothesis-profile=ci`,
which makes the inputs the same on every run so a CI result can be repeated, drops the time
limit per example (shared runners are slow and uneven), and prints a blob that reproduces a
failure exactly.

Slow tests run last. A test marked `slow` (most of a second, such as the brain's seeded runs) is
moved to the end of the run, every other test keeping its order. The mutation run stops each
mutant's run at its first failure (`pytest -x`), so a mutant that a quick test catches never waits
for the slow ones. Every test still runs.
"""

import os

import pytest
from hypothesis import settings

os.environ["QT_QPA_PLATFORM"] = "offscreen"

settings.register_profile("ci", derandomize=True, deadline=None, print_blob=True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Move the tests marked slow to the end; the sort is stable, so each group keeps its order."""
    items.sort(key=lambda item: item.get_closest_marker("slow") is not None)
