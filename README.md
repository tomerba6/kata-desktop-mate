# Kata desktop mate

[![CI](https://github.com/tomerba6/kata-desktop-mate/actions/workflows/ci.yml/badge.svg)](https://github.com/tomerba6/kata-desktop-mate/actions/workflows/ci.yml)

Kata is a pixel-art fox that will live on your Windows desktop: standing on the taskbar, wandering, sitting, napping, hopping when clicked, and riding on other windows.

Right now this repo is the starting point: the sprites, a sprite loader and a preview window. The rest gets built milestone by milestone in Claude Code. The roadmap is in [BRIEF.md](BRIEF.md).

![Kata's animations](docs/sprites-preview.png)

## Quick start (PowerShell)

```powershell
py --version                                   # needs Python 3.14 or newer
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m kata                   # Kata on the desktop; right-click it, then Quit
.venv\Scripts\python -m kata.preview           # the sprite preview
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy                   # types, strict
.venv\Scripts\python -m coverage run -m pytest # the tests again, measured
.venv\Scripts\python -m coverage report        # the 90% gate on the no-Qt modules
```

In the preview window, Left and Right switch animation, Space pauses and Esc quits.

CI runs ruff, mypy, the tests and the coverage gate on every push, on Python 3.14 and 3.15. The HTML coverage report and mutation testing (run by hand) are in the Commands list in [CLAUDE.md](CLAUDE.md).

Calling `.venv\Scripts\python` directly means you never have to activate the virtual environment, so PowerShell's script-execution policy can't get in the way.

## What's here

| Path | What it is |
| :-- | :-- |
| `BRIEF.md` | The roadmap: nine milestones, each built from its own plan in `docs/plans/` |
| `CLAUDE.md` | Project rules Claude Code reads at the start of every session |
| `src/kata/assets/kata.png` | The sprite sheet: 7 animations, 48x48 frames |
| `src/kata/assets/kata.json` | Which row is which animation, frame counts, speeds |
| `src/kata/sheet.py` | Reads the JSON: frame size, ground line, animations. No Qt |
| `src/kata/sprites.py` | Cuts the sheet into frames |
| `src/kata/preview.py` | A plain window that plays each animation |
| `tests/test_sheet.py` | Checks that the JSON is read correctly |
| `tests/test_sprites.py` | Checks that the JSON matches the PNG |
| `tests/test_make_sprites.py` | Checks that the committed sheet is what `make_sprites.py` draws |
| `tests/test_no_qt.py` | Checks that the no-Qt modules import no Qt, and that the coverage gate and the mutation run cover exactly them |
| `tests/conftest.py` | Hypothesis profiles, including the repeatable `ci` one |
| `tools/make_sprites.py` | Draws the sprite sheet from code |
| `docs/sprites-preview.png` | Enlarged contact sheet of every frame |
| `docs/plans/` | One plan per milestone, with its steps, decisions and session log |
| `.github/workflows/ci.yml` | CI: lint, types, tests and the coverage gate on every push |
| `cosmic-ray.toml` | Mutation testing settings, for runs by hand |

## Changing the art

The fox is drawn by `tools/make_sprites.py`: a hand-drawn head stamp plus simple shapes for body, legs and tail, moved a pixel or two per frame. Edit the head, the palette or a pose, then run:

```powershell
.venv\Scripts\python tools\make_sprites.py
```

It rewrites `kata.png`, `kata.json` and the preview image.
