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
"""

import os

from hypothesis import settings

os.environ["QT_QPA_PLATFORM"] = "offscreen"

settings.register_profile("ci", derandomize=True, deadline=None, print_blob=True)
