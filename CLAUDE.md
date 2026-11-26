# Kata desktop mate

A pixel-art desktop pet for Windows 10/11. Python 3.14+, PySide6 (Qt 6 Widgets). The roadmap is in BRIEF.md; each milestone gets its own plan in `docs/plans/` and is built one at a time.

## Commands (PowerShell, from the repo root)

- Run the app: `.venv\Scripts\python -m kata` (right-click Kata, then Quit, to close it)
- Sprite preview: `.venv\Scripts\python -m kata.preview`
- Tests: `.venv\Scripts\python -m pytest`
- Coverage gate (the no-Qt modules, 90% of lines and branches): `.venv\Scripts\python -m coverage run -m pytest`, then `.venv\Scripts\python -m coverage report`
- Coverage as HTML, after a coverage run: `.venv\Scripts\python -m coverage html`, then open `htmlcov\index.html`. To see every file, Qt ones included: `.venv\Scripts\python -m coverage html --include="*/kata/*" -d htmlcov-all --fail-under=0`
- Lint: `.venv\Scripts\python -m ruff check .`
- Types (strict, over `src`, `tests` and `tools`): `.venv\Scripts\python -m mypy`
- Mutation testing, by hand and not in CI (settings in `cosmic-ray.toml`). It changes the no-Qt modules on disk, runs the suite once per change and puts them back. Run `.venv\Scripts\cosmic-ray init cosmic-ray.toml mutation.sqlite --force`, then `.venv\Scripts\cosmic-ray exec cosmic-ray.toml mutation.sqlite`, then `.venv\Scripts\cr-report mutation.sqlite`. Every job must end killed or survived; `incompetent` means the test command never started.
- Format: `.venv\Scripts\python -m ruff format .`
- Redraw the sprites: `.venv\Scripts\python tools\make_sprites.py`
- Measure Kata on the desktop (the run-kata skill, `.claude/skills/run-kata/SKILL.md`): `.venv\Scripts\python tools\inspect_kata.py --launch LOG --capture PNG` to start Kata and report, the same without `--launch` to report on a running Kata, and `--kill` to stop it. Add `--cpu SECONDS` to a report to measure Kata's CPU use. LOG and PNG go in the scratchpad, never the repo. It is read-only: it never clicks or types.

## Working agreement

- Read the Progress list in BRIEF.md to find the current milestone. Work on that one only.
- M0 is a checklist in BRIEF.md. Every later milestone starts with `/staged-plan`, with the milestone's section in BRIEF.md as its input. The plan's "How to work this plan" section sets the rules for steps, tests, stops and commits.
- You can start the app but you cannot see my desktop. After any change that affects what is on screen, measure it first with the run-kata skill: the window's styles (title bar, border, taskbar button, topmost, see-through), whether launching took focus, the window rectangle, where a click on a see-through or a drawn pixel goes, and whether the paws sit on the floor. Then list the exact things for me to check by hand: what the skill can't measure (how it looks, how the animation feels, menus and clicks, anything on a second monitor) and anything its report leaves in doubt. Ask for pass or fail on each, with what I saw, and wait for my answer before going on.
- A milestone is done when its plan's last step is committed, its "Check by hand" items pass, and ruff, mypy, the tests with the coverage gate, and CI on the milestone branch are all green. From M2 on, a mutation run on the no-Qt modules must also end with every surviving mutant killed or explained in the plan's Session log. Then tick it in BRIEF.md, cut its section there down to the goal and a link to the plan, and propose the pull request that merges it into `main`.
- If a Qt or Win32 call behaves differently from what BRIEF.md expects, say so and update the brief rather than working around it silently.

## Architecture rules

- Kata's position is the feet point: bottom centre of the sprite on its ground line, in Qt screen coordinates. The window rectangle is derived from it. Physics, walking and landing all become simple, and mirroring the sprite never shifts Kata sideways.
- GUI code (anything that imports PySide6) stays thin: windows, painting, input, timers.
- Behaviour, physics, animation playback, settings and platform maths are plain Python with no Qt imports, each with pytest tests. They take time as `dt`, randomness as an injected `random.Random` and file paths as arguments, so the code under test is deterministic.
- A rule that must hold for any input (the frame index stays in range, the feet stay inside the bounds) is a Hypothesis property test. Locally Hypothesis tries new inputs each run; CI runs `--hypothesis-profile=ci`, which repeats the same inputs, so a CI result can be reproduced.
- A new no-Qt module goes into `[tool.coverage.report] include` in pyproject.toml and into `module-path` in cosmic-ray.toml; `tests/test_no_qt.py` fails until it is in both.
- Windows-only code (ctypes, winreg) in the app lives in `src/kata/platform/windows.py` behind small functions, with imports guarded by `sys.platform == "win32"`. A developer tool in `tools/`, such as `inspect_kata.py`, may call ctypes itself, behind the same guard.
- Never hard-code sprite facts: frame counts, frame size, fps, the ground line, the `held` anchor, the walk stride. Read them from `kata.json` through `kata.sheet`, which has no Qt, so any module can import it. Behaviour and physics numbers (timings, weights, gravity) go in config dataclasses such as `BehaviourConfig`, not as literals in the code.
- Scale pixel art by whole numbers with `Qt.TransformationMode.FastTransformation`.

## Layout

```text
src/kata/
  __main__.py        entry point (exists)
  app.py             QApplication setup, wiring, tray (exists)
  window.py          PetWindow: painting, the main tick, mouse input (exists)
  animator.py        current frame, looping and one-shot (exists)   no Qt
  sheet.py           reads kata.json into sprite facts (exists)     no Qt
  sprites.py         cuts kata.png into QPixmap frames, and mirrors them (exists)
  body.py            feet, velocity, gravity, landing (exists)      no Qt
  drag.py            click or drag, and the release speed (exists)  no Qt
  brain.py           behaviour state machine (exists)               no Qt
  platforms.py       floors and window tops Kata can stand on       no Qt
  geometry.py        placement: floors, grip, bounds (exists)       no Qt
  settings.py        load and save user settings                    no Qt
  switches.py        developer switches, KATA_LOG lines (exists)    no Qt
  crashlog.py        uncaught crashes appended to a file            no Qt
  platform/
    windows.py       ctypes and winreg: window rectangles, autostart
  preview.py         sprite preview (exists)
tests/
  test_<module>.py   one per no-Qt module
  test_window.py     PetWindow headless: fake clock, made-up mouse events (exists)
tools/
  make_sprites.py    draws kata.png and kata.json (exists)
  inspect_kata.py    run-kata: measures Kata on the desktop (exists)
```

## Conventions

- Type hints on everything, dataclasses for plain data, `pathlib` for paths.
- ruff for lint and format, mypy in strict mode for types (settings for both in pyproject.toml). pytest for tests, files named `tests/test_<module>.py`; `tests/test_no_qt.py` checks the no-Qt rule itself.
- Kata's window is tested headless. `tests/conftest.py` puts Qt on its offscreen platform, so no test opens a window. `tests/test_window.py` gives `PetWindow` a fake clock, a made-up desktop, a brain with a seeded `random.Random` and synthetic mouse events, and calls `tick()` itself. Hand checks are for what this can't show: looks, feel, the menu, a second screen.
- A test that takes most of a second gets `@pytest.mark.slow`, and `tests/conftest.py` runs those after all the others. The mutation run stops each mutant at its first failing test, so most mutants never wait for the slow ones. Every test still runs, in CI too.
- Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`.
- One branch per milestone (`m1-window`, `m2-drag`). It reaches `main` through a pull request once its CI is green, merged with "Create a merge commit". Squash would collapse the step commits that the plan refers to, and rebase would leave no record of the PR. Show me the PR's title and description before opening it, since they are public.

## References

- Qt for Python: https://doc.qt.io/qtforpython-6/
- Sprite sheet layout: `src/kata/assets/kata.json`, drawn by `tools/make_sprites.py`
