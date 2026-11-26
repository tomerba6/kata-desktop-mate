# Kata desktop mate: build brief

Kata is a pixel-art fox that lives on the Windows desktop. This brief is the roadmap for building it in Claude Code, one milestone at a time. Python 3.14+, PySide6 (Qt 6 Widgets), Windows 10/11.

## What the finished app does

- Shows Kata in a transparent, frameless, always-on-top window with no taskbar button. Clicks on empty pixels go to whatever is underneath.
- Kata stands on the taskbar, wanders left and right, sits, and naps when left alone.
- Click Kata and it hops with hearts.
- Pick Kata up with the mouse and it dangles. Let go and it falls and lands.
- Kata can land on, walk along and sit on the top edge of other windows, and falls when the window goes away.
- A tray icon gives a menu: pause, sit, sleep, size, start with Windows, quit. Settings are remembered.
- It ships as a Windows exe that runs without Python installed.

## Progress

- [x] M0 Run the starter
- [x] M1 Kata on the desktop
- [x] M2 Pick up, carry, drop
- [x] M3 Wander, sit, sleep
- [x] M4 React to a click
- [ ] M5 Tray menu and settings
- [ ] M6 Start with Windows
- [ ] M7 Stand on windows
- [ ] M8 Package and polish

## How to run a session

1. Open this folder in Claude Code. It reads `CLAUDE.md` at the start of every session, so the project rules are already loaded.
2. For M0, paste:

   ```text
   Read BRIEF.md. We are on Milestone 0. Help me finish its checklist, then stop.
   ```

3. For every later milestone, type `/staged-plan the next unticked milestone in BRIEF.md`. It asks its questions, then saves a plan of one-commit steps in `docs/plans/`.
4. Say "next" to build one step. Claude Code can start the app and measure some of what is on screen with its run-kata skill, but it cannot see your desktop, so it asks you about the rest. Answer each check with pass or fail and what you saw.
5. When the last step is committed, it ticks the milestone above and proposes a pull request into `main`, showing you its title and description first.

If a session gets long, start a new one; the plan file carries the state.

## What already exists

See the "What's here" table in [README.md](README.md). Sprite facts (frame counts, fps, ground line, the `held` anchor, the walk's stride) are in `src/kata/assets/kata.json`; the file layout and architecture rules are in `CLAUDE.md`.

## Milestones

Each section below is the input for that milestone's staged plan. When the milestone is done, its section shrinks to the goal and a link to the plan.

### M0 Run the starter

**Do**

- Create the virtual environment and install: see README.md.
- Run the preview, the tests and ruff.
- `git init`, first commit. Optionally create the GitHub repo and push.

**Done when**

- The preview shows all seven animations.
- 4 tests pass and ruff reports no problems.

### M1 Kata on the desktop

**Goal:** Kata stands on the taskbar, or on the screen's bottom edge when the taskbar auto-hides, in a window that doesn't look like a window.

Done. The plan, with its decisions, what was measured on the way and the watch-outs found: [docs/plans/2026-11-24-m1-window.md](docs/plans/2026-11-24-m1-window.md).

### M2 Pick up, carry, drop

**Goal:** drag Kata anywhere; on release it falls and lands.

Done. The plan, with its decisions, what was measured on the way and what was left open (two real screens, unchecked): [docs/plans/2026-11-24-m2-drag.md](docs/plans/2026-11-24-m2-drag.md).

### M3 Wander, sit, sleep

**Goal:** left alone, Kata behaves like a pet.

Done. The plan, with its decisions, what was measured on the way and what was left open (two real screens, unchecked): [docs/plans/2026-11-25-m3-wander.md](docs/plans/2026-11-25-m3-wander.md). The smoke test M7 extends is the ten-minute one in `tests/test_window.py`, which drives the real `PetWindow`.

### M4 React to a click

**Goal:** click Kata, get a happy hop.

Done. The plan, with its decisions and what was measured on the way: [docs/plans/2026-11-26-m4-click.md](docs/plans/2026-11-26-m4-click.md). A click on a nap wakes Kata without a hop, and clicks during a hop are ignored.

### M5 Tray menu and settings

**Goal:** control Kata without a terminal, and keep choices between runs.

**Build**

- `QSystemTrayIcon` with a `QMenu`: Pause wandering, Sit, Sleep, Size (2x, 3x, 4x), Always on top, Start with Windows (disabled until M6), Quit. Right-clicking Kata opens the same menu.
- The tray image is Kata's head cropped from the first `idle` frame.
- `app.setQuitOnLastWindowClosed(False)`, so the app lives in the tray.
- `Settings` dataclass saved as JSON. `settings.py` has no Qt: it loads from and saves to a path it is given, and `app.py` builds that path from `QStandardPaths.StandardLocation.AppConfigLocation`. Loaded at start. The file carries a `version`: a missing file, a broken file or another version means defaults, and in a readable file a single bad value falls back to its own default without losing the rest. Changing size rebuilds the frames.
- One running copy only, using `QLockFile`.
- A crash log in `crashlog.py`, no Qt: a `sys.excepthook` that appends a timestamped traceback to `crash.log` in the settings folder, then hands the crash on to the previous hook. It never raises itself. The path and the clock are passed in, and `app.py` installs it. From M6 Kata runs under `pythonw.exe` with no console, so without this a crash would leave no trace.

**Check by hand**

- The tray icon appears (look in the overflow arrow too). Each menu item does what it says.
- Change the size, quit, start again: the size is kept.
- Starting a second copy does not add a second fox.

**Tests**

- Settings round-trip; defaults on a missing file; defaults on a corrupt file; defaults on another version; one bad value keeps the others. Use pytest's `tmp_path`.
- Crash log: an entry has the time and the full traceback, entries append, a failed write is swallowed, and the previous hook still runs.
- Property test: any valid `Settings` comes back unchanged after a save and a load.

**Watch out**

- Check how PySide6 reports an exception raised inside a slot or a timer callback before relying on `sys.excepthook` to catch it.

### M6 Start with Windows

**Goal:** an opt-in switch that brings Kata back after sign-in.

**Build**

- In `platform/windows.py`: `set_autostart(enabled)` and `is_autostart_enabled()` using `winreg` on `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value name `Kata`.
- The command to store: when packaged (`getattr(sys, "frozen", False)`), the exe path. From source, the virtual environment's `pythonw.exe` with `-m kata`; `pythonw` runs without a console window.
- Wire the tray toggle to it.

**Check by hand**

- Toggle on, then run `reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Kata`: the value is there.
- Sign out and in: Kata appears, with no console window.
- Toggle off: the value is gone.

**Tests**

- The command-building function for both cases. Registry access sits behind a small interface so a fake can stand in.

**Watch out**

- Guard Windows imports with `sys.platform == "win32"` so the tests still collect on any machine.

### M7 Stand on windows

**Goal:** other windows become platforms. This is the hard milestone; build it in the order below and keep each step working.

**Build**

1. `list_windows()` in `platform/windows.py` with `ctypes`: `EnumWindows`, keeping windows that are visible (`IsWindowVisible`), not minimised (`IsIconic`), not cloaked (`DwmGetWindowAttribute` with `DWMWA_CLOAKED`, 14), not tool windows, titled, and not Kata's own (`winId()`). Take each rectangle from `DwmGetWindowAttribute` with `DWMWA_EXTENDED_FRAME_BOUNDS` (9); `GetWindowRect` includes invisible resize borders.
2. Convert from Win32 physical pixels to Qt coordinates by dividing by the screen's `devicePixelRatio()`.
3. `platforms.py`: turn the window list (front to back) plus the screen floors into segments `(x0, x1, y)`. A window's top edge counts only where no window in front covers it. Add `support_under(feet, segments)` and `landing(prev_feet, next_feet, segments)`.
4. Poll the window list every 250 ms or so, not every frame.
5. `Body` lands on a segment only when moving down through it. If the segment under Kata moves, Kata rides it. If it disappears, or Kata walks past its end, the brain gets `released()` and Kata falls.
6. The brain's walking range becomes the current segment's ends.

**Check by hand**

- Drop Kata above a Notepad window: it lands on the title bar.
- Drag Notepad: Kata rides along. Minimise or close it: Kata falls to the taskbar.
- Kata walks to the end of the title bar and steps off.
- Maximised windows are ignored, since there is no room above them.

**Tests**

- Segment building with overlapping windows; landing; riding a moving segment; losing support.
- The M3 smoke test also runs with platforms built from a fake window list.
- Property test: for random sets of overlapping windows, no segment lies where a window in front of it covers it.

**Watch out**

- `EnumWindows` returns top-level windows front to back in practice; the segment logic relies on that order.
- Monitors with different scaling have different `devicePixelRatio()` values. Convert per screen.

### M8 Package and polish

**Build**

- An app icon (`.ico`, several sizes) made from the sprite by a small script in `tools/`.
- A PyInstaller build with no console window that includes `kata/assets`. Start with a one-folder build. Take the exact flags from the current PyInstaller documentation, and confirm the `importlib.resources` loading in `sheet.py` and `sprites.py` works in the built exe.
- Autostart stores the exe path when running packaged.
- Crisp pixels at 125% and 150% display scaling: a pure, tested function chooses the scale so each sprite pixel covers a whole number of device pixels at the screen's `devicePixelRatio()`.
- Hide Kata while a fullscreen app is in front. Slow the tick while asleep.
- A release workflow: a `v*` tag runs the checks, builds the PyInstaller exe on `windows-latest`, zips it and publishes it as a GitHub Release. CI also builds the package on every push without publishing it, so a broken build shows up before the tag does.
- A `CHANGELOG.md` in the Keep a Changelog format, with a "Known limitations" section (an unsigned exe, Windows only).
- README with a short GIF, then the `v1.0.0` tag.

**Check by hand**

- The exe runs on a Windows account or machine that has no Python.
- Idle CPU stays under 1%.
- Windows SmartScreen may warn about an unsigned exe. That is expected.

## After v1

- A speech bubble, then reminders that use it: stretch, coffee, time to stop gaming.
- A study timer: Kata naps while you focus and wakes you when time is up.
- Come when called: Kata runs to the cursor on a hotkey.
- More art: new poses go in `tools/make_sprites.py`, new rows in the sheet.

## References

- Qt for Python: https://doc.qt.io/qtforpython-6/
- Claude Code setup: https://code.claude.com/docs/en/setup
- How Claude Code uses CLAUDE.md: https://code.claude.com/docs/en/memory
- Output styles, if you later want Claude Code to explain its choices as it builds: https://code.claude.com/docs/en/output-styles
