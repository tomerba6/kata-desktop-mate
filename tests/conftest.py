"""Shared test setup.

Hypothesis profiles. Local runs use Hypothesis's defaults: fresh random inputs each run, with any
failure saved in .hypothesis/ and tried first next time. CI runs `pytest --hypothesis-profile=ci`,
which makes the inputs the same on every run so a CI result can be repeated, drops the time
limit per example (shared runners are slow and uneven), and prints a blob that reproduces a
failure exactly.
"""

from hypothesis import settings

settings.register_profile("ci", derandomize=True, deadline=None, print_blob=True)
