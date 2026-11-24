# Dev tooling before M1

**Status:** active · **Branch:** `dev-tooling` off `main` at `a6999e6` · **Started:** 2026-11-24

## Context

M1 adds kata's first logic module (`animator.py`). Before it lands, the rules that CLAUDE.md states
but nothing checks should become checks:

- **"No Qt in the logic":** stated in CLAUDE.md, enforced by nothing.
- **"Type hints on everything":** stated in CLAUDE.md, enforced by nothing.
- **Coverage:** never measured.
- **Sprite sheet:** nothing notices when `tools/make_sprites.py` and the committed sheet drift apart.
- **Test strength:** unknown.
- **Housekeeping:**
  - the first commit printed CRLF warnings for 12 files;
  - the version lives in two places (`pyproject.toml` and `src/kata/__init__.py`);
  - there is no CI.

This plan takes items 1–5 from the scoundrel comparison and items 1–4 from the test-hardening
options. When it's done, every later milestone is built under the gates: CI, type checking, the
no-Qt boundary test, the coverage gate, property tests and a mutation baseline.

Not in scope: any M1 code, the `run-kata` screenshot driver, ruff's docstring rules,
pytest-randomly, and the release workflow (M8).

## Decisions

From the interview (2026-11-24):

1. **Split `sprites.py`:** the Qt-free JSON reader (`read_sheet_info`, `AnimationInfo`,
   `SheetInfo`) moves to a new `sheet.py` with no Qt; `sprites.py` keeps `load_frames`. The
   gates then have a real module to check from day one, and later modules can import the sprite
   types without pulling in PySide6.
2. **Minimum Python is 3.14:** `requires-python = ">=3.14"`. 3.10 is past end of life
   (2026-10-01), and the current Hypothesis and coverage releases need 3.11 or later.
3. **Type checker:** mypy in strict mode.
4. **Branch:** first commit the uncommitted BRIEF.md and CLAUDE.md edits on `main` as
   `docs: place the scoundrel lessons in the milestones`, then branch `dev-tooling` off that commit.
5. **CI check:** in step 8 only, I ask before pushing `dev-tooling` to `origin`, then follow the
   run with `gh run watch`. This is the one exception to "Never push" below.

Defaults chosen without asking (approved with the plan):

- **One version copy:** `kata.__version__` stays the source, and setuptools reads it
  (`dynamic = ["version"]`). Reading it back through `importlib.metadata` would break in M8's
  PyInstaller exe, which carries no package metadata unless told to.
- **CI Pythons:** 3.14 (the minimum) and 3.15 (newest stable).
  - `setup-python` lists 3.14.10 and 3.15.2.
  - PySide6-Essentials 6.12.0 declares `<3.16`.
  - Runner: `windows-latest` only, since kata is Windows-only.
  - Triggers: every push to any branch, so the branch gets checked before it's merged.
  - Matrix: `fail-fast: false`.
  - Actions: `checkout@v7`, `setup-python@v7` (latest majors, checked 2026-11-24).
- **Coverage:** coverage.py run directly (`coverage run -m pytest`, then `coverage report`), with
  no pytest-cov.
  - Branch coverage is on.
  - The gate is `fail_under = 90` on coverage.py's combined line-and-branch figure.
  - It covers only the modules listed in `[tool.coverage.report] include`.
- **The coverage `include` list is the single list of no-Qt modules.** `tests/test_no_qt.py`
  checks it against what each module really imports, and against the "no Qt" marks in
  CLAUDE.md's Layout.
  - Each module is imported in a fresh interpreter, so an indirect Qt import counts.
  - Package `__init__` files are exempt.
- **Golden-file test:** it runs `build()` from `tools/make_sprites.py` into a temporary folder,
  then compares JSON as parsed data and the two PNGs pixel by pixel (Pillow), never as file
  bytes.
- **Hypothesis:** `tests/conftest.py` registers a `ci` profile with `derandomize=True`, no
  deadline and `print_blob=True`.
  - Local runs use Hypothesis's defaults; `.hypothesis/` is ignored by git.
  - The first property test pins `frame_ms` in step 2.
  - The docs step adds property tests to the milestones' Tests lists.
- **Mutation testing:** cosmic-ray on the no-Qt modules, run by hand and not in CI; step 7
  records the result as a baseline.
  - cosmic-ray 8.9.0 declares Python up to 3.13 only. If it doesn't run on 3.14, I stop and ask.
  - The fallback is mutmut in WSL (Ubuntu-22.04 is installed), but that would need Python 3.14
    installed inside WSL first.
- **mypy setup:** `files = ["src", "tests", "tools"]` with `mypy_path = "src"`, because mypy may
  not follow setuptools' editable-install finder.
- **New test files:**
  - `tests/test_sheet.py`: pure, no Qt.
  - `tests/test_no_qt.py`
  - `tests/test_make_sprites.py`
- **pytest-randomly:** dropped.

## Approach

Each step is one commit that leaves the project building with its tests passing. Commands run
from the repo root in PowerShell.

### 1. LF line endings, one version, Python 3.14

Git stops rewriting line endings, the version has one home, and the claimed Python matches the
one used. Files: `.gitattributes`, `.editorconfig`, `pyproject.toml`, `README.md`, `CLAUDE.md`,
`BRIEF.md`.

- [x] `.gitattributes`: `* text=auto eol=lf` and `*.png binary`, then `git add --renormalize .`
- [x] `.editorconfig`:
      - UTF-8, LF, a final newline and trimmed whitespace for every file;
      - Python indented 4 with a maximum line length of 110, matching ruff;
      - YAML indented 2;
      - Markdown keeps trailing whitespace.
- [x] `pyproject.toml`: drop the static `version` and add `dynamic = ["version"]` with
      `[tool.setuptools.dynamic] version = {attr = "kata.__version__"}`. Set
      `requires-python = ">=3.14"`.
- [x] Reinstall (`.venv\Scripts\python -m pip install -e ".[dev]"`). ruff now targets
      Python 3.14, so fix whatever new findings it reports.
- [x] Change "3.10" to "3.14" in README.md (Quick start), CLAUDE.md (line 3) and BRIEF.md (line 3).

**Verify (me):**
- `git ls-files --eol` → every text file shows `i/lf` and `attr/text=auto eol=lf`.
- `.venv\Scripts\python -c "import importlib.metadata as m, kata; print(m.version('kata-desktop-mate'), kata.__version__)"` → `0.1.0 0.1.0`.
- pytest → 4 passed; ruff check and `ruff format --check` → clean.

**Verify (you):** nothing beyond the tests
**Commit:** `chore: LF line endings, one version, Python 3.14 minimum`

### 2. Hypothesis, and pin the sheet reader before it moves

The refactor in step 3 gets tests that pin what it must not change, and Hypothesis gets its first
real use. Files: `pyproject.toml`, `tests/conftest.py`, `tests/test_sprites.py`, `.gitignore`.

- [x] Add `hypothesis>=6.170` to the `dev` extra. Register the `ci` profile in `tests/conftest.py`
      and ignore `.hypothesis/` in git.
- [x] Write the pinning tests in `tests/test_sprites.py`, against today's `kata.sprites`:
      - a property: for any `fps` from 1 to 1000, `frame_ms` is `1000 / fps` rounded to the
        nearest millisecond (within 0.5);
      - `read_sheet_info()` matches `kata.json` parsed independently with `json`, field by field
        (image, frame size, `ground_y`, and each animation's row, frames, fps, loop and anchor).
- [x] These describe existing behaviour, so they pass at once. To see them fail for the right
      reason, swap `round` for `math.floor` in `frame_ms`, then drop the anchor parsing; run;
      revert each.

**Verify (me):**
- pytest → 6 passed.
- `.venv\Scripts\python -m pytest --hypothesis-profile=ci` → 6 passed.
- `--hypothesis-profile=nope` → an error naming the unknown profile, which proves `ci` is
  registered.

**Verify (you):** nothing beyond the tests
**Commit:** `test: pin the sheet reader with a property test and a JSON check`

### 3. Move the sheet reader into a no-Qt `sheet.py`

Kata gets its first Qt-free module, and no later module needs a workaround to import the sprite
types. This is a refactor: no behaviour changes.

Files: `src/kata/sheet.py` (new), `src/kata/sprites.py`, `src/kata/preview.py`,
`tests/test_sheet.py` (new), `tests/test_sprites.py`, `CLAUDE.md`, `BRIEF.md`, `README.md`.

- [x] Run the full suite: 6 passed.
- [x] Move `AnimationInfo`, `SheetInfo` and `read_sheet_info` to `sheet.py` verbatim.
      `sprites.py` keeps `load_frames` and imports `SheetInfo` from `kata.sheet`. `preview.py`
      imports `read_sheet_info` from `kata.sheet`. Update both module docstrings.
- [x] Move the tests that need no Qt to `tests/test_sheet.py`. The two that read the PNG with
      `QImage` stay in `tests/test_sprites.py`.
- [x] Update the docs this changes:
      - CLAUDE.md Layout: the `sheet.py` and `sprites.py` lines.
      - CLAUDE.md line 27: read sprite facts "through `kata.sheet`, which has no Qt", and drop
        the PySide6 caveat.
      - BRIEF M1: drop the `TYPE_CHECKING` watch-out.
      - BRIEF M8: the `importlib.resources` check covers `sheet.py` and `sprites.py`.
      - README "What's here": one row per module.

**Verify (me):**
- pytest → 6 passed, the same count as before.
- `.venv\Scripts\python -c "import sys, kata.sheet; print('PySide6' in sys.modules)"` → `False`.
- `.venv\Scripts\python -m kata` still opens the preview window.

**Verify (you):** the preview still plays all seven animations (Left/Right to switch, Esc to quit). Pass or fail, with what you saw.
**Commit:** `refactor: move the sheet reader into a no-Qt sheet.py`

### 4. The no-Qt boundary test and the coverage gate

From here, a no-Qt module that picks up a Qt import fails the build. So does a new no-Qt module
missing from the gate, and so does the gate's coverage dropping under 90.

Files: `tests/test_no_qt.py` (new), `pyproject.toml`, `CLAUDE.md`.

- [x] Write the failing test, `tests/test_no_qt.py`:
      - every module under `src/kata` is imported in a fresh interpreter, which classifies it as
        Qt or no-Qt;
      - the coverage `include` list must equal exactly the set of no-Qt modules;
      - CLAUDE.md's "no Qt" Layout marks must agree for every module that exists;
      - a guard on the scanner itself: it finds `sheet` as no-Qt and `sprites` as Qt.
- [x] Run it and see it fail for the right reason: `pyproject.toml` has no coverage config, so
      `kata.sheet` is reported as missing from the gate.
- [x] Add `coverage>=7.17` to the `dev` extra. Add `[tool.coverage.run] branch = true`,
      `source = ["kata"]`, and `[tool.coverage.report] include = ["*/kata/sheet.py"]`,
      `fail_under = 90`, `show_missing = true`.
- [x] Add the coverage commands to CLAUDE.md's Commands list: run, report, and the HTML report
      (`coverage html`, then open `htmlcov\index.html`). Add `htmlcov/` to `.gitignore`.
- [x] Check that `coverage html --include="*/kata/*" -d htmlcov-all` really overrides the
      config's `include` and shows the Qt files too. If it does, document it next to the HTML
      command; if not, find what does and document that.

**Verify (me):**
- `.venv\Scripts\python -m coverage run -m pytest` → all passed.
- `.venv\Scripts\python -m coverage report` → `sheet.py` and its percentage, exit code 0.
- `.venv\Scripts\python -m coverage html` → `htmlcov\index.html` lists `sheet.py` with the same
  percentage; `git status` doesn't show `htmlcov/`.
- Add a temporary `from PySide6 import QtCore` to `sheet.py` → `test_no_qt` fails and names it;
  revert.

**Verify (you):** open `htmlcov\index.html` and click through to `sheet.py`: lines coloured as
run, missed or partly run.
**Commit:** `test: enforce the no-Qt boundary and gate its coverage`

### 5. Golden-file test for the sprite sheet

Changing the drawing code without regenerating the committed files now fails a test.

Files: `tests/test_make_sprites.py` (new).

- [x] Check first that the output is deterministic: run `build()` twice into two folders in the
      scratchpad and compare. The code has no `random` or `time`, but that should be observed,
      not assumed.
- [x] Write the test. It loads `tools/make_sprites.py` by path (the `tools` folder isn't a
      package), runs `build(tmp_path)`, then compares:
      - `kata.json` as parsed data;
      - `kata.png` and `docs/sprites-preview.png` pixel by pixel.

      The failure message says to rerun the tool and commit its outputs.
- [x] See it fail for the right reason: change idle's fps in `ANIMATIONS` → fails on `kata.json`;
      change one `PALETTE` colour → fails on `kata.png`. Revert each.

**Verify (me):** pytest → all passed, with the new test included; `git status` shows no changed
assets.
**Verify (you):** nothing beyond the tests
**Commit:** `test: the committed sprite sheet is what make_sprites draws`

### 6. Type checking with mypy, strict

"Type hints on everything" becomes a check.

Files: `pyproject.toml`, `CLAUDE.md`, plus annotation fixes across `src/`, `tests/` and `tools/`.

- [x] Add `mypy>=2.4` to the `dev` extra, with `[tool.mypy] strict = true`,
      `files = ["src", "tests", "tools"]`, `mypy_path = "src"`.
- [x] Run it and record the error count in the Session log. Then fix the errors, with no
      behaviour changes: tests get `-> None`, Qt overrides get their event types.
- [x] If the count is far larger than a few dozen, or a fix would change behaviour, stop and ask.
- [x] Add the mypy command to CLAUDE.md's Commands list.

**Verify (me):**
- `.venv\Scripts\python -m mypy` → `Success: no issues found`.
- A temporary `x: int = "a"` in `sheet.py` → mypy fails on that line; revert.
- pytest → all passed; ruff → clean.

**Verify (you):** nothing beyond the tests
**Commit:** `chore: check types with mypy --strict`

### 7. Mutation testing with cosmic-ray

A by-hand measure of whether the tests would catch a bug in the no-Qt code, with today's result
as the baseline.

Files: `pyproject.toml`, `cosmic-ray.toml` (new), `.gitignore`, `CLAUDE.md`.

- [ ] Add `cosmic-ray>=8.9` to the `dev` extra. Write `cosmic-ray.toml` by hand from its current
      docs (`new-config` is interactive):
      - it mutates the no-Qt modules (today `src/kata/sheet.py`);
      - its test command is the full pytest suite.

      Ignore the session database in git.
- [ ] Run init, exec and the report. If cosmic-ray fails on Python 3.14, stop and ask (see
      Decisions).
- [ ] Record killed and survived counts in the Session log, and list each survivor in the report
      to you. Killing them is your call, not part of this step.
- [ ] Add the commands to CLAUDE.md's Commands list, marked "by hand".

**Verify (me):** the report shows every mutant either killed or survived, with none left
incomplete, and the counts are recorded.
**Verify (you):** read the list of survivors and say which, if any, to kill now.
**Commit:** `chore: mutation testing with cosmic-ray`

### 8. CI on GitHub Actions

Every push runs the whole check on the Pythons kata supports.

Files: `.github/workflows/ci.yml` (new).

- [ ] One `check` job on `windows-latest`, with a matrix of Python 3.14 and 3.15 and
      `fail-fast: false`. Steps:
      - checkout and setup-python (with pip caching);
      - `pip install -e ".[dev]"`;
      - ruff check and `ruff format --check`;
      - mypy;
      - `coverage run -m pytest --hypothesis-profile=ci`;
      - `coverage html --fail-under=0`, run even when the tests failed (`coverage html` applies
        the gate too, so `--fail-under=0` leaves the gate to `coverage report` alone);
      - `coverage report`, which enforces the gate;
      - upload `htmlcov/` with `actions/upload-artifact@v7` on every run, pass or fail, as
        `coverage-html-<python version>`, kept 7 days.

      It runs on every push, with `concurrency` cancelling an older run on the same branch and
      `permissions: contents: read`. Mutation testing stays out of CI.
- [ ] Run the same commands locally in the `.venv`. Stop uncommitted as usual.
- [ ] After your ok and the commit: ask before `git push -u origin dev-tooling`, then
      `gh run watch`. If a job fails, fix it in a follow-up commit (`ci: ...`), push again after
      asking, and note it under Deviations.

**Verify (me):** locally, every command passes. On GitHub, both matrix jobs are green, read with
`gh run view`, and each run lists its `coverage-html-*` artifact.
**Verify (you):** download one `coverage-html-*` artifact from the run's page in the Actions tab
and open its `index.html`.
**Commit:** `ci: lint, types, tests and the coverage gate on every push`

### 9. Docs and memory sync

- [ ] Update the README, docs and CLAUDE.md wherever this feature changed what they say, and
      re-measure every number they quote.
      - README: a CI badge; Quick start and the "What's here" table cover the new commands and
        files.
      - CLAUDE.md working agreement: a milestone is done when ruff, mypy, the coverage gate and
        CI are green; from M2, a cosmic-ray run on the no-Qt modules leaves every survivor
        killed or explained.
      - CLAUDE.md architecture rules: add Hypothesis next to the `dt`/`random.Random` rule,
        noting that CI runs the derandomized `ci` profile.
      - BRIEF milestone Tests lists get property tests:
        - M1 animator: the frame stays in range for any `dt` sequence;
        - M2 body: the feet stay in bounds and never below the floor for any `dt` sequence;
        - M3–M4 brain: stateful tests over random grab, release and click sequences;
        - M5 settings: round-trip for any valid settings;
        - M7 platforms: random overlapping windows.
- [ ] Update the memory files, if the project keeps them. It doesn't today.

**Verify (me):** each changed claim checked against the code or a command
**Verify (you):** read the diff
**Commit:** `docs: dev tooling docs sync`

## Files

- **To change:**
  - `pyproject.toml`: dynamic version, Python 3.14, dev extras (`hypothesis`, `coverage`,
    `mypy`, `cosmic-ray`), coverage and mypy config.
  - `src/kata/sprites.py` and `src/kata/preview.py`: imports after the split.
  - `tests/test_sprites.py`: pinning tests in step 2; its pure tests move out in step 3.
  - `.gitignore`: `.hypothesis/`, `htmlcov/` and cosmic-ray's session file.
  - `README.md`, `CLAUDE.md`, `BRIEF.md`.
- **New:** `.gitattributes`, `.editorconfig`, `src/kata/sheet.py`, `tests/conftest.py`,
  `tests/test_sheet.py`, `tests/test_no_qt.py`, `tests/test_make_sprites.py`, `cosmic-ray.toml`,
  `.github/workflows/ci.yml`.
- **To reuse:**
  - `read_sheet_info`, `AnimationInfo` and `SheetInfo` in `src/kata/sprites.py`: moved verbatim
    to `sheet.py`.
  - `build(root)` in `tools/make_sprites.py`: it already takes the output root, so the golden
    test calls it with `tmp_path`.
  - The two `QImage` tests in `tests/test_sprites.py`: unchanged.

## Verification

Once step 9 is in:

- **A clean checkout builds:** clone the branch into the scratchpad, create a fresh Python 3.14
  venv there, `pip install -e ".[dev]"`, then run:
  - ruff check and `ruff format --check`;
  - mypy;
  - `coverage run -m pytest --hypothesis-profile=ci` and `coverage report`.
- **CI:** the last push's run is green on 3.14 and 3.15.
- **Line endings:** `git ls-files --eol` shows LF throughout.
- **The app:** `python -m kata` opens the preview.

## How to work this plan

- **Resume:** be on the branch above, read this whole file, and take the first step not `[x]`.
  `git log --oneline` on this file shows one commit per finished step; check the ticks against it.
- **One step per request.** For "do 3 and 4", commit each once its checks pass unless it needs
  the user's eyes or ears; the last one waits.
- **Mark the step *(in progress)*** before starting. Wrong branch, or changes that belong to no
  step: stop and ask.
- **Tests first** for logic: see the new test fail for the right reason, then implement.
- **Stop uncommitted:** run *Verify (me)*, mark it *(built, awaiting your ok)*, add a Session log
  line naming any choice this plan didn't settle, and report: what changed, the check and its
  result, what the user should check, what you decided on your own, and "ok to commit it, or tell
  me what to change".
- **The user's ok commits it** ("ok", "approved", or moving on): tick `[x]` with the date, stage
  the step's files and this file by path, and use the step's *Commit* line. Never push.
- **Feedback** on a waiting step: change it, check again, keep it waiting.
- **Plan wrong?** Do the right thing and note it under Deviations; ask first if it changes a
  decision or the scope.
- **Last step committed:** set **Status:** to `done` and add a closing note under the title.

## Progress

- [x] **Plan approved** (2026-11-24)
- [x] **1. LF line endings, one version, Python 3.14** (2026-11-24)
- [x] **2. Hypothesis, and pin the sheet reader before it moves** (2026-11-24)
- [x] **3. Move the sheet reader into a no-Qt `sheet.py`** (2026-11-24)
- [x] **4. The no-Qt boundary test and the coverage gate** (2026-11-24)
- [x] **5. Golden-file test for the sprite sheet** (2026-11-24)
- [x] **6. Type checking with mypy, strict** (2026-11-24)
- [ ] **7. Mutation testing with cosmic-ray**
- [ ] **8. CI on GitHub Actions**
- [ ] **9. Docs and memory sync**

### Deviations

<One line each, with the step number: what the plan said, what was done, and why.>

### Session log

- **2026-11-24:** Plan approved. Baseline: 4 tests passing, HEAD `a6999e6`.
- **2026-11-24:** Added at your request, before step 1: the HTML coverage report (step 4), and CI
  uploading it as an artifact (step 8). My choice: CI uploads it on every run, not only on
  failure, so coverage can be read after a green run too.
- **2026-11-24:** Step 1 built.
  - All 13 tracked text files are LF in the index and the working copy under `text=auto eol=lf`,
    and the 2 PNGs are binary. `git add --renormalize .` changed no line endings.
  - Both version readings say `0.1.0`.
  - ruff targets Python 3.14 now and reports nothing new.
  - My choices: `.editorconfig` indents TOML by 4 (as `pyproject.toml` already is), and it gives
    `*.png` an explicit `binary`.
- **2026-11-24:** Step 2 built.
  - Hypothesis 6.170.17 is installed.
  - 6 passed, both with the default profile and with `--hypothesis-profile=ci`; `nope` is refused
    with "Profile 'nope' is not registered".
  - Broken on purpose, then restored:
    - `frame_ms` truncating instead of rounding: Hypothesis found `fps=101` (9 ms against 9.9 ms);
    - no anchor parsing: the JSON check and the existing anchor test both failed.
  - My choice: the new tests carry `-> None` already, ahead of step 6's mypy.
- **2026-11-24:** Step 3 built.
  - 6 passed before the move and 6 after, with both profiles.
  - Comparing against the committed `sprites.py`, the moved 45-line block and `load_frames` are
    identical.
  - `import kata.sheet` loads no PySide6. ruff is clean.
  - My choices:
    - README's table gains a `tests/test_sheet.py` row as well as the `sheet.py` row;
    - `test_sprites.py` keeps its name, although it checks the PNG against the JSON rather than
      `load_frames`, which still has no test. That gap is the one Qt function left untested, and
      the mutation run in step 7 covers only the no-Qt modules.
  - Your check: the preview plays all seven animations. Pass.
- **2026-11-24:** Step 4 built.
  - Written first, the test failed naming `kata.sheet` as missing from the gate.
  - coverage 7.17.5 is installed. 9 passed under coverage, and `sheet.py` measured 26
    statements, 0 missed: 100%.
  - It also measured 0 branches: coverage.py counts only jumps between lines, so the one-line
    `... if "anchor" in a else None` is not a branch to it. Mutation testing (step 7) checks that
    kind of choice.
  - `coverage report --include="*/kata/*"` does override the config, and lists all 5 files at
    21% (exit code 2, under the gate).
  - With a Qt import planted in `sheet.py`, all three tests failed naming `kata.sheet`.
  - My choices:
    - `.coverage` (the data file) and `htmlcov*/` are ignored;
    - the all-files HTML command carries `--fail-under=0`, because `coverage html` applies the
      gate too and would exit 2;
    - for the same reason, step 8's CI HTML step now uses `--fail-under=0`, leaving the gate to
      `coverage report`.
  - Your check: `htmlcov\index.html` shows `sheet.py` at 100%. Pass.
- **2026-11-24:** Step 5 built.
  - Two `build()` runs into the scratchpad were byte-identical.
  - Against the committed files, the pixels and the JSON data match, but the bytes don't:
    - the PNGs are encoded differently;
    - on Windows, `write_text` writes the JSON with CRLF line endings.

    So comparing pixels and parsed data was the right call.
  - 3 new tests (the JSON plus 2 images), 12 passed in all; coverage is still 100%, ruff clean.
  - Broken on purpose, then restored, with `git diff` on `tools/` and the assets showing nothing:
    - idle at 6 fps: the JSON test failed;
    - the heart pink one step bluer: both image tests failed.
  - My choices:
    - the drawn sheet is shared by the three tests (a module-scoped fixture), so it is drawn once
      per run;
    - the failure message tells you to rerun the tool and commit its outputs.
- **2026-11-24:** Step 6 built.
  - mypy 2.4.1, strict, first run: 11 errors in 3 files (11 source files checked):
    - 4 tests without `-> None`;
    - 4 functions in `make_sprites.py` with untyped parameters;
    - 2 indexing errors from `build()`'s untyped `meta` dict;
    - `Image.NEAREST`, which Pillow's type hints don't declare.
  - `preview.py` and the Qt code needed no fixes.
  - All fixed with no behaviour change. The golden test still passes, so the sheet and preview
    are drawn pixel for pixel as before.
  - A planted `x: int = "a"` in `sheet.py` failed mypy on that line; reverted.
  - 12 passed; ruff clean.
  - My choices:
    - `build()` names its `animations` dict up front instead of reaching into `meta`;
    - `Image.NEAREST` becomes `Image.Resampling.NEAREST`, the same value under the name Pillow
      declares;
    - a `type Point = tuple[float, float]` alias keeps `tail()`'s signature under 110 columns.
