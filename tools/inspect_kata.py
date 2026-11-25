"""Measure Kata on the real desktop without looking at it: the tool behind the run-kata skill.

Read-only: it never clicks, types or moves anything. It asks Windows about Kata's window, and it
captures Kata's square plus a margin, finding Kata's pixels by the outline colour that rings the
whole sprite.

From the repo root:

    .venv\\Scripts\\python tools\\inspect_kata.py --launch LOG [--capture PNG] [--cpu SECONDS]
    .venv\\Scripts\\python tools\\inspect_kata.py [--capture PNG] [--cpu SECONDS]
    .venv\\Scripts\\python tools\\inspect_kata.py --kill

The first starts Kata and reports, the second reports on the running Kata, the third stops it.
LOG receives Kata's KATA_LOG output; PNG receives the capture, with -outline.png beside it. Both
must be outside the repo: a capture shows the user's desktop. --cpu adds a line measuring Kata's
CPU use over SECONDS.

Coordinates are physical pixels unless a line says Qt. Qt units are physical pixels divided by
the screen's scale (1.5 at 150%). The tool declares itself DPI-aware first, so Windows reports
physical pixels instead of numbers scaled for an unaware program.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageGrab

from kata.sheet import read_sheet_info

ROOT = Path(__file__).resolve().parent.parent
TITLE = "Kata"  # PetWindow's window title
MARGIN = 8  # physical pixels captured around Kata's square
WAIT_S = 15.0  # how long --launch waits for the window, and --kill for it to go
SETTLE_S = 1.0  # after the window appears, time for the first paint before capturing

# Style bits, from WinUser.h.
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_CAPTION = WS_BORDER | WS_DLGFRAME
WS_THICKFRAME = 0x00040000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000


# --- Pure helpers, tested in tests/test_inspect_kata.py ------------------------------------------


@dataclass(frozen=True)
class Traits:
    caption: bool  # a title bar
    border: bool  # a thin, dialog or resizing frame
    tool_window: bool  # no taskbar button, unless app_window is set too
    topmost: bool  # stays above ordinary windows
    layered: bool  # see-through per pixel
    app_window: bool  # forces a taskbar button


def decode_styles(style: int, ex_style: int) -> Traits:
    """What a window's style and extended style bits mean for how it looks."""
    style &= 0xFFFFFFFF  # GetWindowLongW returns a signed LONG
    ex_style &= 0xFFFFFFFF
    return Traits(
        caption=(style & WS_CAPTION) == WS_CAPTION,
        border=bool(style & (WS_BORDER | WS_DLGFRAME | WS_THICKFRAME)),
        tool_window=bool(ex_style & WS_EX_TOOLWINDOW),
        topmost=bool(ex_style & WS_EX_TOPMOST),
        layered=bool(ex_style & WS_EX_LAYERED),
        app_window=bool(ex_style & WS_EX_APPWINDOW),
    )


type Point = tuple[int, int]


def pixels_of_colour(image: Image.Image, colour: tuple[int, int, int]) -> list[Point]:
    """Every (x, y) whose colour is exactly `colour`, row by row."""
    data, want, width = image.convert("RGB").tobytes(), bytes(colour), image.width
    return [(i // 3 % width, i // 3 // width) for i in range(0, len(data), 3) if data[i : i + 3] == want]


def lowest_row(points: list[Point]) -> int | None:
    return max((y for _, y in points), default=None)


def nearest(points: list[Point], to: Point) -> Point | None:
    return min(points, key=lambda p: (p[0] - to[0]) ** 2 + (p[1] - to[1]) ** 2, default=None)


def bounding_box(points: list[Point]) -> tuple[int, int, int, int] | None:
    """left, top, right, bottom around the points; right and bottom are one past the last."""
    if not points:
        return None
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def outline_colour() -> tuple[int, int, int]:
    """The colour make_sprites.py draws Kata's outline in, read from its palette."""
    spec = importlib.util.spec_from_file_location("make_sprites", Path(__file__).with_name("make_sprites.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    colour: tuple[int, int, int] = module.PALETTE["x"]
    return colour


def inside_repo(path: Path) -> bool:
    return path.resolve().is_relative_to(ROOT)


def filetime_seconds(low: int, high: int) -> float:
    """A FILETIME in seconds: two 32-bit halves of one count of 100-nanosecond units."""
    return ((high << 32) | low) / 10_000_000


def cpu_percent(cpu_seconds: float, wall_seconds: float, cores: int) -> tuple[float, float]:
    """CPU time over wall time, as a percentage of one core and of all `cores`.

    The second is the figure Task Manager shows, since it counts every logical core as 100%.
    """
    if wall_seconds <= 0:
        raise ValueError(f"wall time must be positive, got {wall_seconds}")
    one_core = cpu_seconds * 100 / wall_seconds
    return one_core, one_core / cores


# --- Windows -------------------------------------------------------------------------------------

if sys.platform == "win32":
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    # Handles are pointer-sized; without these declarations ctypes would cut them to 32 bits.
    user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    MONITOR_DEFAULTTONEAREST = 2
    GA_ROOT = 2

    def set_dpi_aware() -> None:
        user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)

    def find_kata() -> int | None:
        hwnd: int | None = user32.FindWindowW(None, TITLE)
        return hwnd if hwnd and user32.IsWindowVisible(hwnd) else None

    def describe(hwnd: int | None) -> str:
        if not hwnd:
            return "none"
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        return f'0x{hwnd:x} "{title.value}" ({cls.value})'

    def window_pid(hwnd: int) -> int:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def window_styles(hwnd: int) -> tuple[int, int]:
        style: int = user32.GetWindowLongW(hwnd, GWL_STYLE)
        ex_style: int = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        return style, ex_style

    def window_rect(hwnd: int) -> tuple[int, int, int, int]:
        """left, top, right, bottom; right and bottom are one past the last pixel."""
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top, r.right, r.bottom

    def window_scale(hwnd: int) -> float:
        dpi: int = user32.GetDpiForWindow(hwnd)
        return dpi / 96

    def monitor_and_work_area(hwnd: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), ctypes.byref(info))
        m, w = info.rcMonitor, info.rcWork
        return (m.left, m.top, m.right, m.bottom), (w.left, w.top, w.right, w.bottom)

    def window_at(x: int, y: int) -> int | None:
        """The top-level window a click at (x, y) would reach, as Windows hit-tests it."""
        hwnd: int | None = user32.WindowFromPoint(wintypes.POINT(x, y))
        if not hwnd:
            return None
        root: int | None = user32.GetAncestor(hwnd, GA_ROOT)
        return root

    def foreground() -> int | None:
        hwnd: int | None = user32.GetForegroundWindow()
        return hwnd

    def process_cpu_seconds(pid: int) -> float:
        """The CPU time, kernel plus user, that the process has used since it started."""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
            times = (ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user))
            if not kernel32.GetProcessTimes(handle, *times):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(handle)
        return filetime_seconds(kernel.dwLowDateTime, kernel.dwHighDateTime) + filetime_seconds(
            user.dwLowDateTime, user.dwHighDateTime
        )

    def launch(log: Path) -> subprocess.Popen[bytes]:
        """Start `python -m kata` with KATA_LOG=1 and no console window, which would take focus."""
        with log.open("wb") as out:  # the child keeps its own copy of the handle
            return subprocess.Popen(
                [sys.executable, "-m", "kata"],
                cwd=ROOT,
                env={**os.environ, "KATA_LOG": "1"},
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


def wait_for(test: Callable[[], bool], seconds: float = WAIT_S) -> bool:
    """Poll `test()` every 0.1 s until it is true or `seconds` pass."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if test():
            return True
        time.sleep(0.1)
    return False


def yes(value: bool) -> str:
    return "yes" if value else "no"


def reaches(x: int, y: int, kata: int) -> str:
    """Which window a click at (x, y) would reach, named."""
    under = window_at(x, y)
    return f"({x},{y}): reaches {describe(under)}{' = Kata' if under == kata else ''}"


def report(hwnd: int, capture: Path | None) -> list[str]:
    lines = [f"window: {describe(hwnd)}, pid {window_pid(hwnd)}"]

    traits = decode_styles(*window_styles(hwnd))
    styles = ", ".join(f"{name.replace('_', ' ')} {yes(on)}" for name, on in vars(traits).items())
    lines.append(f"styles: {styles}")
    taskbar = traits.app_window or not traits.tool_window
    lines.append(f"taskbar button: {yes(taskbar)} (from the tool window and app window bits)")

    left, top, right, bottom = window_rect(hwnd)
    scale = window_scale(hwnd)
    width, height = right - left, bottom - top
    lines.append(
        f"rect: {left},{top} {width}x{height} physical; "
        f"{left / scale:g},{top / scale:g} {width / scale:g}x{height / scale:g} Qt at scale {scale:g}"
    )
    monitor, work = monitor_and_work_area(hwnd)
    lines.append(f"monitor: {monitor}; work area: {work} (left, top, right, bottom)")

    # Kata's pixels are found by the outline colour that rings the whole sprite. Comparing
    # captures taken with and without layered windows found nothing: on Windows 11 both show Kata.
    box = (left - MARGIN, top - MARGIN, right + MARGIN, bottom + MARGIN)
    shot = ImageGrab.grab(bbox=box, include_layered_windows=True)
    inside = (MARGIN, MARGIN, MARGIN + width, MARGIN + height)  # Kata's rect within the capture
    found = pixels_of_colour(shot, outline_colour())
    outline = [(x, y) for x, y in found if inside[0] <= x < inside[2] and inside[1] <= y < inside[3]]
    stray = len(found) - len(outline)
    lines.append(
        f"outline: {len(outline)} pixels inside Kata's rect, {stray} in the margin around it"
        + (" (the background has the outline colour too; check the capture)" if stray else "")
    )
    if capture is not None:
        capture.parent.mkdir(parents=True, exist_ok=True)
        shot.save(capture)
        mask = Image.new("L", shot.size, 0)
        for xy in outline:
            mask.putpixel(xy, 255)
        mask.save(capture.with_name(capture.stem + "-outline.png"))
        lines.append(f"capture: {capture} (and -outline.png beside it)")

    sprite = bounding_box(outline)  # the outline rings the sprite, so it bounds every drawn pixel
    corner = (MARGIN + 1, MARGIN + 1)  # just inside Kata's rect, top left
    if sprite is None or sprite[0] <= corner[0] < sprite[2] and sprite[1] <= corner[1] < sprite[3]:
        lines.append("see-through pixel: the corner may be drawn, so not tested")
    else:
        lines.append(f"see-through pixel {reaches(left + 1, top + 1, hwnd)}")
    drawn = nearest(outline, (MARGIN + width // 2, MARGIN + height // 2))
    if drawn is not None:
        lines.append(f"drawn pixel {reaches(left - MARGIN + drawn[0], top - MARGIN + drawn[1], hwnd)}")

    lowest = lowest_row(outline)
    floor = work[3]  # one past the work area's last row: the row Kata stands on
    if lowest is None:
        lines.append("floor: no outline found, so not measured")
    else:
        lowest_y = top - MARGIN + lowest
        lines.append(f"floor: lowest drawn row {lowest_y}, floor row {floor}, gap {floor - 1 - lowest_y}")
    sheet = read_sheet_info()
    kata_scale = height / scale / sheet.frame_h
    ground = top + sheet.ground_y * kata_scale * scale
    lines.append(
        f"ground line: window top {top} + {sheet.ground_y} x {kata_scale:g} x {scale:g} = {ground:g}; "
        f"floor row {floor}"
    )
    return lines


def measure_cpu(pid: int, seconds: float) -> str:
    """How much CPU the process uses over the next `seconds`, as a report line."""
    cpu_before, wall_before = process_cpu_seconds(pid), time.perf_counter()
    time.sleep(seconds)
    cpu = process_cpu_seconds(pid) - cpu_before
    wall = time.perf_counter() - wall_before
    cores = os.cpu_count() or 1
    one_core, all_cores = cpu_percent(cpu, wall, cores)
    return (
        f"cpu: {cpu:.3f} s of CPU over {wall:.1f} s: {one_core:.2f}% of one core, "
        f"{all_cores:.2f}% of all {cores} cores (pid {pid})"
    )


def kill() -> int:
    hwnd = find_kata()
    if hwnd is None:
        print("kill: Kata is not running")
        return 0
    pid = window_pid(hwnd)
    os.kill(pid, signal.SIGTERM)  # on Windows: TerminateProcess
    gone = wait_for(lambda: find_kata() is None)
    print(f"kill: pid {pid} stopped; window {'gone' if gone else 'STILL THERE'}")
    return 0 if gone else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Kata on the desktop. Read-only: never clicks.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--launch", metavar="LOG", type=Path, help="start Kata, its KATA_LOG output to LOG")
    action.add_argument("--kill", action="store_true", help="stop the running Kata")
    parser.add_argument("--capture", metavar="PNG", type=Path, help="save the capture of Kata's square")
    parser.add_argument("--cpu", metavar="SECONDS", type=float, help="measure Kata's CPU use for SECONDS")
    args = parser.parse_args(argv)
    for path in (args.launch, args.capture):
        if path is not None and inside_repo(path):
            parser.error(f"{path} is inside the repo; captures and logs go outside it, in the scratchpad")
    if args.kill and (args.capture or args.cpu is not None):
        parser.error("--capture and --cpu go with a report, not with --kill")
    if args.cpu is not None and args.cpu <= 0:
        parser.error("--cpu needs a positive number of seconds")
    if sys.platform != "win32":
        print("inspect_kata needs Windows")
        return 2

    set_dpi_aware()  # before reading any coordinate
    if args.kill:
        return kill()

    if args.launch is not None:
        if find_kata() is not None:
            print("launch: Kata is already running; --kill it first")
            return 1
        before = foreground()
        proc = launch(args.launch)
        if not wait_for(lambda: find_kata() is not None or proc.poll() is not None):
            print(f"launch: no Kata window after {WAIT_S:g} s")
            return 1
        if proc.poll() is not None:
            print(f"launch: Kata exited with code {proc.returncode}; its output is in {args.launch}")
            return 1
        time.sleep(SETTLE_S)
        after = foreground()
        print(f"focus: before launch {describe(before)}; after {describe(after)}")
        print(f"focus: {'kept' if after == before else 'CHANGED'}")
        for line in args.launch.read_text(encoding="utf-8", errors="replace").splitlines():
            print(f"log: {line}")

    hwnd = find_kata()
    if hwnd is None:
        print("report: Kata is not running")
        return 1
    for line in report(hwnd, args.capture):
        print(line)
    if args.cpu is not None:
        print(measure_cpu(window_pid(hwnd), args.cpu))
    return 0


if __name__ == "__main__":
    sys.exit(main())
