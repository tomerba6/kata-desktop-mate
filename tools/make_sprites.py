"""Draw Kata's sprite sheet from code.

Run from the project root:

    python tools/make_sprites.py

It writes src/kata/assets/kata.png (the sheet), src/kata/assets/kata.json (what
is where) and docs/sprites-preview.png (an enlarged contact sheet for humans).

The fox is built like a paper puppet: a hand-drawn head stamp plus simple shapes
for body, legs and tail. Each animation frame just moves those parts a pixel or
two. To change the art, edit HEAD, the colours in PALETTE, or the pose
functions, then run the script again. Needs Pillow (pip install pillow).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image

FRAME = 48  # every frame is FRAME x FRAME pixels
GROUND_Y = 47  # the floor: first empty row under the paws and their outline
COLUMNS = 8  # frames per row in the sheet

PALETTE = {
    "o": (242, 122, 48),  # fur
    "d": (204, 90, 30),  # fur in shade
    "c": (255, 240, 220),  # cream
    "s": (230, 204, 178),  # cream in shade
    "k": (58, 41, 66),  # socks, ear tips
    "n": (29, 21, 34),  # eyes, nose
    "w": (247, 245, 255),  # headband, eye glint
    "b": (196, 190, 228),  # headband in shade
    "p": (255, 128, 156),  # hearts, tongue, inner ear
    "x": (38, 25, 44),  # outline
}
SHADE = {"o": "d", "c": "s", "w": "b"}

# The head, facing right. One character per pixel, "." is empty.
HEAD = [
    "..k......k......",
    ".kok....kok.....",
    ".ooo....ooo.....",
    ".opoo..oopo.....",
    ".opooooooopo....",
    ".ooooooooooo....",
    "oooooooooooo....",
    "wwwwwwwwwwww....",
    "oooooooooooo....",
    "ooooooooooooo...",
    "oooooooooooooonn",
    "ccccooooocccccc.",
    ".ccccccccccc....",
    "..ccccccccc.....",
    "...cccccc.......",
]
EYE_AT = (9, 9)  # top-left pixel of the eye inside HEAD
EYES = {
    "open": {(0, 0): "w", (1, 0): "n", (0, 1): "n", (1, 1): "n"},
    "blink": {(0, 1): "n", (1, 1): "n"},
    "happy": {(0, 1): "n", (1, 0): "n", (2, 1): "n"},
    "sleep": {(0, 0): "n", (1, 1): "n", (2, 0): "n"},
    "wide": {(0, -1): "w", (1, -1): "n", (0, 0): "n", (1, 0): "n", (0, 1): "n", (1, 1): "n"},
}
HEART = [".p.p.", "ppppp", "ppppp", ".ppp.", "..p.."]
ZED = ["wwww", "..w.", ".w..", "wwww"]


class Canvas:
    """A FRAME x FRAME grid of palette letters. None means transparent."""

    def __init__(self) -> None:
        self.px: list[list[str | None]] = [[None] * FRAME for _ in range(FRAME)]
        self.dy = 0  # added to every y: lets a pose hop without redoing its numbers

    def put(self, x: int, y: int, c: str) -> None:
        y += self.dy
        if 0 <= x < FRAME and 0 <= y < GROUND_Y - 1:  # keep one row above the floor free for the outline
            self.px[y][x] = c

    def get(self, x: int, y: int) -> str | None:
        if 0 <= x < FRAME and 0 <= y < FRAME:
            return self.px[y][x]
        return None

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, c: str) -> None:
        for y in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
            for x in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1:
                    self.put(x, y, c)

    def rect(self, x0: int, y0: int, x1: int, y1: int, c: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def stamp(self, rows: list[str], ox: int, oy: int) -> None:
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    self.put(ox + x, oy + y, ch)

    def part(self, draw) -> None:
        """Draw one body part on its own layer, then merge it.

        Where the new part overlaps what is already there, the pixels just
        outside its edge are darkened one step. That thin soft line is what
        keeps a leg readable in front of a body of the same colour.
        """
        layer = Canvas()
        layer.dy = self.dy
        draw(layer)
        for y in range(FRAME):
            for x in range(FRAME):
                if layer.px[y][x] is not None:
                    continue
                under = self.px[y][x]
                if under in SHADE and any(
                    layer.get(x + ax, y + ay) is not None for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    self.px[y][x] = SHADE[under]
        for y in range(FRAME):
            for x in range(FRAME):
                if layer.px[y][x] is not None:
                    self.px[y][x] = layer.px[y][x]

    def finish(self) -> Image.Image:
        """Shade undersides, add the dark outline, and return an RGBA image."""
        src = [row[:] for row in self.px]
        for y in range(FRAME):
            for x in range(FRAME):
                c = src[y][x]
                below = src[y + 1][x] if y + 1 < FRAME else None
                if c in ("o", "c") and below is None:
                    self.px[y][x] = SHADE[c]
        img = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
        for y in range(FRAME):
            for x in range(FRAME):
                c = self.px[y][x]
                if c is not None:
                    img.putpixel((x, y), PALETTE[c] + (255,))
                elif any(
                    self.get(x + ax, y + ay) is not None for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    img.putpixel((x, y), PALETTE["x"] + (255,))
        return img


# ---------- body parts ----------


def tail(c: Canvas, base, ctrl, tip, fat: float = 4.0) -> None:
    """A fluffy tail: a row of overlapping discs along a curve, cream at the end."""
    steps = 26
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * base[0] + 2 * (1 - t) * t * ctrl[0] + t**2 * tip[0]
        y = (1 - t) ** 2 * base[1] + 2 * (1 - t) * t * ctrl[1] + t**2 * tip[1]
        swell = math.sin(min(1.0, t / 0.62) * math.pi / 2)  # thin at the root, fat past the middle
        taper = 1.0 if t < 0.62 else 1 - ((t - 0.62) / 0.38) ** 1.6 * 0.72
        r = max(1.2, (1.7 + (fat - 1.7) * swell) * taper)
        c.ellipse(x, y, r, r, "c" if t > 0.7 else "o")


def leg(c: Canvas, hip_x: int, hip_y: int, foot_dx: int, lift: int, far: bool, length: int = 8) -> None:
    """A two-pixel-wide leg from hip to paw. foot_dx slants it, lift raises the paw."""
    foot_y = hip_y + length - lift
    rows = max(1, foot_y - hip_y)
    for y in range(hip_y, foot_y + 1):
        t = (y - hip_y) / rows
        x = hip_x + round(foot_dx * t)
        colour = "k" if y > foot_y - 4 else ("d" if far else "o")
        c.put(x, y, colour)
        c.put(x + 1, y, colour)
    c.put(hip_x + foot_dx + 2, foot_y, "k")  # toe


def head(c: Canvas, ox: int, oy: int, eye: str = "open", mouth: bool = False) -> None:
    c.stamp(HEAD, ox, oy)
    ex, ey = ox + EYE_AT[0], oy + EYE_AT[1]
    for (dx, dy), colour in EYES[eye].items():
        c.put(ex + dx, ey + dy, colour)
    if mouth:
        c.put(ox + 12, oy + 12, "p")
        c.put(ox + 13, oy + 12, "p")
        c.put(ox + 12, oy + 13, "p")


def ribbons(c: Canvas, x: int, y: int, wave: int, up: bool = False) -> None:
    """The two loose ends of the headband, trailing behind the head."""
    if up:
        shapes = [[(0, 0), (-1, -1), (-1, -2), (-2, -3)], [(0, 1), (-2, 0), (-3, -1), (-3, -2)]]
    else:
        a = [(0, 0), (-1, 0), (-2, 1), (-3, 1), (-4, 2)]
        b = [(0, 1), (-1, 2), (-2, 3), (-3, 4)]
        if wave == 1:
            a = [(0, 0), (-1, 1), (-2, 1), (-3, 2), (-4, 2)]
            b = [(0, 1), (-1, 2), (-2, 2), (-3, 3)]
        elif wave == 2:
            a = [(0, 0), (-1, 0), (-2, 0), (-3, 1), (-4, 1)]
            b = [(0, 1), (-1, 2), (-2, 3), (-2, 4)]
        shapes = [a, b]
    for i, shape in enumerate(shapes):
        for dx, dy in shape:
            c.put(x + dx, y + dy, "w" if i == 0 else "b")


# ---------- poses ----------


def stand(
    c: Canvas,
    *,
    bob: int = 0,
    head_dy: int = 0,
    eye: str = "open",
    mouth: bool = False,
    legs=((0, 0), (0, 0), (0, 0), (0, 0)),  # far back, near back, far front, near front: (foot_dx, lift)
    tail_tip=(0, 0),
    tail_pose: str = "up",
    wave: int = 0,
    ribbons_up: bool = False,
) -> None:
    by = bob
    if tail_pose == "up":
        base, ctrl, tip = (15, 32 + by), (5, 33 + by), (6 + tail_tip[0], 20 + by + tail_tip[1])
    elif tail_pose == "high":
        base, ctrl, tip = (15, 32 + by), (7, 30 + by), (9 + tail_tip[0], 15 + by + tail_tip[1])
    else:  # "down": hanging
        base, ctrl, tip = (15, 33 + by), (9, 36 + by), (10 + tail_tip[0], 45 + by + tail_tip[1])
    c.part(lambda p: tail(p, base, ctrl, tip))
    c.part(lambda p: ribbons(p, 21, 23 + by + head_dy, wave, ribbons_up))
    c.part(lambda p: leg(p, 17, 37 + by, legs[0][0], legs[0][1] + by, True))
    c.part(lambda p: leg(p, 28, 37 + by, legs[2][0], legs[2][1] + by, True))
    c.part(lambda p: p.ellipse(22, 33.5 + by, 8.5, 5, "o"))
    c.part(lambda p: p.ellipse(28.5, 34.5 + by, 3, 4.5, "c"))
    c.part(lambda p: leg(p, 14, 37 + by, legs[1][0], legs[1][1] + by, False))
    c.part(lambda p: leg(p, 25, 37 + by, legs[3][0], legs[3][1] + by, False))
    c.part(lambda p: head(p, 22, 15 + by + head_dy, eye, mouth))


def sit(c: Canvas, *, eye: str = "open", head_dy: int = 0, tail_tip=(0, 0), wave: int = 0) -> None:
    c.part(lambda p: tail(p, (15, 42), (6, 45), (7 + tail_tip[0], 34 + tail_tip[1])))
    c.part(lambda p: ribbons(p, 20, 21 + head_dy, wave))
    c.part(lambda p: leg(p, 28, 38, 0, 0, True, 7))
    c.part(lambda p: p.ellipse(19.5, 40, 6.5, 5.6, "o"))  # haunch
    c.part(lambda p: p.ellipse(24, 35, 5.2, 7.5, "o"))  # upright torso
    c.part(lambda p: p.ellipse(27, 35.5, 2.6, 5.2, "c"))
    c.part(lambda p: p.rect(19, 44, 24, 45, "k"))  # back paw tucked forward
    c.part(lambda p: leg(p, 25, 38, 0, 0, False, 7))
    c.part(lambda p: head(p, 21, 13 + head_dy, eye))


def held(c: Canvas, *, sway: int = 0, wave: int = 0) -> None:
    """Picked up by the scruff: head on top, body hanging, paws and tail dangling."""
    c.part(lambda p: tail(p, (19, 36), (12 + sway, 39), (14 + sway * 2, 45), fat=3.6))
    c.part(lambda p: ribbons(p, 19, 16, wave))
    c.part(lambda p: leg(p, 23, 35, 2 + sway, 0, True, 6))
    c.part(lambda p: leg(p, 27, 28, 3 + sway, 0, True, 6))
    c.part(lambda p: p.ellipse(22, 29.5, 5.6, 8.6, "o"))
    c.part(lambda p: p.ellipse(25.6, 27.5, 2.5, 5.2, "c"))
    c.part(lambda p: leg(p, 20, 35, 1 + sway, 0, False, 6))
    c.part(lambda p: leg(p, 25, 29, 2 + sway, 0, False, 6))
    c.part(lambda p: head(p, 20, 8, "wide"))


def sleep(c: Canvas, *, breath: float = 0.0, zed: int | None = None) -> None:
    c.part(lambda p: ribbons(p, 22, 34, 1))
    c.part(lambda p: p.ellipse(22.5, 39.6 - breath / 2, 10.5, 5.9 + breath / 2, "o"))
    c.part(lambda p: head(p, 23, 28, "sleep"))
    c.part(lambda p: tail(p, (12, 40), (13, 47), (31, 42.6), fat=3.2))
    if zed is not None:
        spots = [(39, 25), (41, 19), (42, 12)]
        for i in range(zed + 1):
            c.stamp(ZED, *spots[i])


def hearts(c: Canvas, step: int) -> None:
    spots = {1: [(38, 16)], 2: [(39, 12), (33, 8)], 3: [(40, 8), (32, 4)], 4: [(41, 5)]}
    for x, y in spots.get(step, []):
        c.stamp(HEART, x, y)


# ---------- animations ----------


def frames_idle() -> list[Canvas]:
    out = []
    for i in range(6):
        c = Canvas()
        stand(
            c,
            bob=1 if i in (2, 3) else 0,
            eye="blink" if i == 4 else "open",
            tail_tip=[(0, 0), (1, 0), (2, 1), (1, 0), (0, 0), (-1, 0)][i],
            wave=[0, 0, 1, 1, 2, 2][i],
        )
        out.append(c)
    return out


def frames_walk() -> list[Canvas]:
    def foot(p: float) -> tuple[int, int]:
        p %= 1.0
        if p < 0.5:  # on the ground, sliding back
            return round(3 - 12 * p), 0
        q = (p - 0.5) / 0.5  # in the air, swinging forward
        return round(-3 + 6 * q), round(2 * math.sin(q * math.pi))

    out = []
    for i in range(8):
        p = i / 8
        c = Canvas()
        stand(
            c,
            bob=1 if i in (1, 5) else 0,
            head_dy=1 if i in (2, 6) else 0,
            legs=(foot(p), foot(p + 0.5), foot(p + 0.5), foot(p)),
            tail_tip=[(0, 0), (1, 1), (1, 0), (0, 0), (-1, 0), (0, 1), (1, 0), (0, 0)][i],
            wave=i % 3,
        )
        out.append(c)
    return out


def frames_sit() -> list[Canvas]:
    out = []
    for i in range(6):
        c = Canvas()
        sit(
            c,
            eye="blink" if i == 3 else "open",
            head_dy=1 if i in (4, 5) else 0,
            tail_tip=[(0, 0), (0, 0), (1, 1), (2, 2), (1, 1), (0, 0)][i],
            wave=[0, 1, 1, 2, 2, 0][i],
        )
        out.append(c)
    return out


def frames_sleep() -> list[Canvas]:
    out = []
    for i in range(6):
        c = Canvas()
        sleep(c, breath=[0, 0.6, 1.2, 1.2, 0.6, 0][i], zed=[None, 0, 1, 2, 2, None][i])
        out.append(c)
    return out


def frames_happy() -> list[Canvas]:
    # crouch, spring, rise, peak, fall, land, settle, stand: the hop is drawn into the frames
    hop = [0, -4, -8, -9, -5, 0, 0, 0]
    bob = [2, 0, 0, 0, 0, 2, 1, 0]
    tuck = [(0, 0), (1, 1), (2, 3), (2, 3), (1, 1), (0, 0), (0, 0), (0, 0)]
    wag = [(0, 0), (2, 0), (-1, 0), (2, 0), (-1, 0), (2, 0), (0, 0), (1, 0)]
    out = []
    for i in range(8):
        c = Canvas()
        c.dy = hop[i]
        f, lift = tuck[i]
        stand(
            c,
            bob=bob[i],
            eye="happy",
            mouth=True,
            legs=((-f, lift), (-f, lift), (f, lift), (f, lift)),
            tail_pose="high",
            tail_tip=wag[i],
            wave=i % 3,
            ribbons_up=i in (4, 5),
        )
        c.dy = 0
        hearts(c, [0, 1, 2, 3, 4, 0, 0, 0][i])
        out.append(c)
    return out


def frames_held() -> list[Canvas]:
    out = []
    for i in range(4):
        c = Canvas()
        held(c, sway=[0, 1, 0, -1][i], wave=i % 3)
        out.append(c)
    return out


def frames_fall() -> list[Canvas]:
    out = []
    for i in range(2):
        c = Canvas()
        c.dy = -3
        stand(
            c,
            eye="wide",
            mouth=True,
            legs=((-3, 2 + i), (-4, 2), (4, 2 + i), (3, 2)),
            tail_pose="high",
            tail_tip=(i, -i),
            ribbons_up=True,
        )
        out.append(c)
    return out


ANIMATIONS = [
    # name, frames, fps, loop
    ("idle", frames_idle, 5, True),
    ("walk", frames_walk, 10, True),
    ("sit", frames_sit, 4, True),
    ("sleep", frames_sleep, 3, True),
    ("happy", frames_happy, 12, False),
    ("held", frames_held, 6, True),
    ("fall", frames_fall, 8, True),
]
HELD_ANCHOR = (22, 21)  # the scruff of the neck in "held" frames: put the cursor here


def build(root: Path) -> None:
    sheet = Image.new("RGBA", (COLUMNS * FRAME, len(ANIMATIONS) * FRAME), (0, 0, 0, 0))
    meta = {
        "image": "kata.png",
        "frame": {"w": FRAME, "h": FRAME},
        "ground_y": GROUND_Y,
        "facing": "right",
        "animations": {},
    }
    for row, (name, make, fps, loop) in enumerate(ANIMATIONS):
        frames = make()
        assert len(frames) <= COLUMNS, name
        for col, canvas in enumerate(frames):
            sheet.paste(canvas.finish(), (col * FRAME, row * FRAME))
        meta["animations"][name] = {"row": row, "frames": len(frames), "fps": fps, "loop": loop}
    meta["animations"]["held"]["anchor"] = list(HELD_ANCHOR)

    assets = root / "src" / "kata" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    sheet.save(assets / "kata.png")
    (assets / "kata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Enlarged contact sheet on a desktop-ish background, so the outline can be judged.
    scale = 4
    big = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    preview = Image.new("RGBA", big.size, (58, 92, 110, 255))
    preview.alpha_composite(big)
    preview.convert("RGB").save(root / "docs" / "sprites-preview.png")
    print(f"wrote {sheet.width}x{sheet.height} sheet with {len(ANIMATIONS)} animations")


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
