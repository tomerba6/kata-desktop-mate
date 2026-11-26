---
name: run-kata
description: Launch Kata on the real Windows desktop and measure it without seeing the screen. It reports the window's styles (title bar, border, taskbar button, topmost, see-through), whether launching took keyboard focus, the window's rectangle in physical pixels and Qt units, which window a click on a see-through or a drawn pixel reaches, whether the paws sit on the floor, and how much CPU Kata uses. Use it after any change that affects what is on screen, before asking the user to check by hand, and when asked to run, start, stop or look at Kata. Read-only, it never clicks or types. Not for looks, animation feel or multiple monitors, which stay with the user.
---

# run-kata

`tools/inspect_kata.py` asks Windows about Kata's window and captures Kata's square plus 8 px
around it. It never clicks, types or moves anything on the user's desktop. Keep it that way: no
synthetic input, ever.

## When to use it

- After a change that affects what is on screen: run it first, then ask the user by hand only
  about what it can't measure.
- When asked to run, start, stop or look at Kata.

What stays with the user: how the art looks (including the unevenness at 150%), whether the
animation plays smoothly, the right-click menu, and anything on a second monitor.

## Commands (PowerShell, from the repo root)

LOG and PNG must be outside the repo; the tool refuses repo paths. Put them in the scratchpad.

```powershell
.venv\Scripts\python tools\inspect_kata.py --launch <scratchpad>\kata.log --capture <scratchpad>\kata.png
.venv\Scripts\python tools\inspect_kata.py --capture <scratchpad>\kata.png   # report on the running Kata
.venv\Scripts\python tools\inspect_kata.py --cpu 30                          # the report, plus CPU over 30 s
.venv\Scripts\python tools\inspect_kata.py --kill
```

- `--launch LOG` starts `python -m kata` with `KATA_LOG=1` and no console window, waits for the
  window, then reports. Kata keeps running after the tool exits, and keeps writing to LOG:
  - a `grab`, `release`, `landed` or `click` line each time it is handled;
  - a `state` line (`from`, `to`, `facing`, `feet`) whenever its state or facing changes. A turn
    mid-walk is `from=walk to=walk`. A state picked again, such as idle after idle, gets no line.

  Read LOG after the user's checks:
  - every `landed` should have feet y equal to its `floor`;
  - every `grab` and `release` should have feet inside its `bounds` (left, right, top) and not
    below its `floor`;
  - every `state` line's feet should be inside those bounds too;
  - a click that woke a nap is a `click` line followed by `state from=sleep to=idle`.
- `--capture PNG` saves the capture, and the outline it found as `<name>-outline.png`. Read
  both PNGs to see them.
- `--cpu SECONDS` adds a `cpu` line after the report: the CPU time Kata used over that many
  seconds. It goes with a report, with or without `--launch`, but not with `--kill`.
- Exit codes: 0 done; 1 Kata not running, or the launch failed; 2 bad arguments, or not Windows.

## Reading the report

Coordinates are physical pixels unless the line says Qt. Qt units are physical pixels divided
by the scale (1.5 at 150%).

| Line | What it says | Good since M1 |
| :-- | :-- | :-- |
| `focus` | The foreground window before the launch and after it (`--launch` only) | `kept` |
| `log` | Kata's KATA_LOG lines (`--launch` only) | `placed` with feet y = area y + height |
| `window` | Handle, title, Qt window class, process id | found |
| `styles` | Bits decoded from the window's style and extended style | caption no, border no, tool window yes, topmost yes, layered yes, app window no |
| `taskbar button` | Worked out from the tool window and app window bits | no |
| `rect` | The window's rectangle, physical and in Qt units | 216x216 physical, 144x144 Qt at scale 1.5 |
| `monitor`, `work area` | The screen and the part windows may use; the work area's bottom is the floor row | equal when the taskbar auto-hides |
| `outline` | Pixels of Kata's outline colour inside its rect, and in the margin | thousands inside, 0 in the margin |
| `see-through pixel` | Which window a click just inside Kata's top-left corner reaches, as Windows hit-tests it | the window behind Kata, not Kata |
| `drawn pixel` | The same, for an outline pixel near Kata's centre | `= Kata` |
| `floor` | The lowest drawn row against the floor row | gap 0 |
| `ground line` | Where the sprite's ground line lands: window top + ground_y x scale x screen scale | within 1 px of the floor row |
| `cpu` | CPU time Kata's process used over the measurement, as a percentage of one core and of all cores; the second is Task Manager's figure (`--cpu` only) | about 1% of one core: M1's baseline was 1.09% over 10 s (0.07% of all 16 cores); M2 read 1.41% and 0.78% over 30 s at rest; M3 read 1.46% over 30 s while Kata wandered |

The step 4 calibration of M1 (2026-11-24) matched the user's hand checks on every line it
measures.

## Gotchas

- **DPI:** the tool makes itself per-monitor DPI-aware before reading any coordinate, so Windows
  reports physical pixels. At 150%, Qt's fractional placement rounds: 579 Qt became 869
  physical, not 868.5. Expect differences of up to 1 px.
- **Finding Kata's pixels:** by exact colour match with the outline colour, read from
  `PALETTE["x"]` in `tools/make_sprites.py`. The outline rings the whole sprite, including the
  row under the paws. Comparing captures taken with and without layered windows does not work:
  on Windows 11 both show Kata, so nothing differs. If the background has the outline colour,
  the `outline` line counts pixels in the margin. Look at `-outline.png` before trusting the
  `floor` line.
- **Captures show the user's desktop:** a notification or a video behind Kata lands in them.
  Keep them in the scratchpad and say no more about what is behind Kata than the check needs.
  The `focus` and `see-through pixel` lines print the titles of the user's windows; don't repeat
  them needlessly.
- **Focus:** the `focus` line only means something if the user didn't click anything during the
  launch.
- **Two processes:** from the venv, `python -m kata` runs as two processes: the venv's launcher
  and the interpreter. `--kill` stops the interpreter, and the launcher exits with it.
- **CPU precision:**
  - Windows counts process time in whole clock ticks of 15.625 ms (measured: every step between
    readings was exactly 0.015625 s). So a 10 s measurement moves in steps of about 0.16% of one
    core. Measure 30 s or more to compare small differences.
  - Only the interpreter process, which owns the window, is measured. The venv's launcher
    process is not counted.
  - Since M3, Kata wanders on its own, so a measurement covers whatever it did meanwhile
    (`state` lines in LOG show what). Make sure nobody is dragging Kata during it.
- **Clicks for hand checks:** ask the user to click Kata's body itself. A click on a see-through
  pixel around Kata goes to the window behind it (the `see-through pixel` line), so Kata never
  hears it. In M3, a "click woke the nap" pass turned out to be a nap ending on its own; the log
  showed no click.
- **Clean up:** run `--kill` when done, unless the user is about to check Kata by hand.
  `--launch` refuses while Kata is already running.
