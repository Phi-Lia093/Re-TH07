#!/usr/bin/env python3
"""Render static layout previews of TH07 screens at 480p/720p/1080p.

This is a *layout* mockup, not a pixel-accurate screenshot: it draws the
geometry that the reverse engineering established (playfield rect, HUD anchor
points, settlement text origin and leading, menu rows) so the proportions and
scaling behaviour can be inspected and checked against the real game.

Everything here is derived from measured constants:
    screen            640 x 480
    playfield         384 x 448
    HUD anchor x      512
    HUD icon start x  496, step 16
    settlement origin (144, 128), title +32, rows +16
    menu sprite pairs differ by v+64

Usage:
    python tools/ui_preview.py                 # all resolutions, all screens
    python tools/ui_preview.py --screen hud    # one screen
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None

LOGICAL_W, LOGICAL_H = 640, 480
PLAYFIELD_W, PLAYFIELD_H = 384, 448
HUD_X = 512
HUD_ICON_X0 = 496
HUD_ICON_STEP = 16
SETTLE_ORIGIN = (144, 128)
SETTLE_TITLE_DY = 32
SETTLE_ROW_DY = 16

RESOLUTIONS = {
    "480p": (640, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}

# Palette (approximated from the game's own ARGB values).
BG = (20, 16, 24, 255)
PLAYFIELD = (28, 34, 48, 255)
PLAYFIELD_EDGE = (90, 110, 150, 255)
HUD_PANEL = (36, 32, 40, 255)
TEXT = (235, 235, 245, 255)
TEXT_DIM = (150, 150, 170, 255)
YELLOW = (255, 255, 64, 255)
CYAN = (255, 255, 128, 255)
PURPLE = (224, 224, 255, 255)
ORANGE = (255, 128, 128, 255)


def font(size: int):
    for name in ("consola.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Canvas:
    """Logical 640x480 canvas scaled to the target resolution."""

    def __init__(self, res: str):
        self.name = res
        self.sw, self.sh = RESOLUTIONS[res]
        self.scale = min(self.sw / LOGICAL_W, self.sh / LOGICAL_H)
        self.dw = int(LOGICAL_W * self.scale)
        self.dh = int(LOGICAL_H * self.scale)
        self.ox = (self.sw - self.dw) // 2
        self.oy = (self.sh - self.dh) // 2
        self.img = Image.new("RGBA", (self.sw, self.sh), (0, 0, 0, 255))
        self.d = ImageDraw.Draw(self.img)
        # logical canvas
        self.d.rectangle([self.ox, self.oy, self.ox + self.dw - 1,
                          self.oy + self.dh - 1], fill=BG)
        self.base_font = font(max(8, int(12 * self.scale)))
        self.small_font = font(max(7, int(9 * self.scale)))

    def pt(self, x: float, y: float) -> tuple[int, int]:
        return (int(self.ox + x * self.scale), int(self.oy + y * self.scale))

    def rect(self, x0, y0, x1, y1, **kw):
        a = self.pt(x0, y0)
        b = self.pt(x1, y1)
        self.d.rectangle([a[0], a[1], b[0], b[1]], **kw)

    def line(self, x0, y0, x1, y1, **kw):
        a = self.pt(x0, y0)
        b = self.pt(x1, y1)
        self.d.line([a, b], **kw)

    def text(self, x, y, s, fill=TEXT, fnt=None):
        self.d.text(self.pt(x, y), s, fill=fill, font=fnt or self.base_font)

    def save(self, path: str):
        self.img.convert("RGB").save(path)


def draw_playfield(c: Canvas, label: str = "PLAYFIELD 384x448") -> None:
    c.rect(0, 0, PLAYFIELD_W, PLAYFIELD_H, fill=PLAYFIELD,
           outline=PLAYFIELD_EDGE)
    c.text(8, 4, label, fill=TEXT_DIM, fnt=c.small_font)
    # HUD band
    c.rect(PLAYFIELD_W, 0, LOGICAL_W, LOGICAL_H, fill=HUD_PANEL)


def screen_game(c: Canvas) -> None:
    draw_playfield(c)
    c.text(HUD_X, 40, "HUD", fill=TEXT)
    rows = [
        (64, "HiScore  123456780"),
        (96, "Score     98765430"),
        (112, "Player  ***"),
        (144, "Bomb    ***"),
        (160, "Graze    1234"),
        (176, "Point    567"),
    ]
    for y, s in rows:
        c.text(HUD_X, y, s, fnt=c.small_font)
    # icon row: lives/bombs markers, 16px apart from x=496
    for i in range(3):
        x = HUD_ICON_X0 + i * HUD_ICON_STEP
        c.rect(x, 220, x + 8, 228, fill=YELLOW)
    c.text(HUD_ICON_X0, 232, "icon row x=496 step 16", fill=TEXT_DIM,
           fnt=c.small_font)
    c.text(8, PLAYFIELD_H - 14, "cherry", fill=PURPLE, fnt=c.small_font)


def screen_settlement(c: Canvas) -> None:
    d = c
    d.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(10, 10, 18, 255))
    x, y = SETTLE_ORIGIN
    d.text(x, y, "Stage Clear", fill=YELLOW)
    y += SETTLE_TITLE_DY
    lines = [
        ("Clear  =  3000000", YELLOW),
        ("Point  =  2500000", PURPLE),
        ("Graze  =   500000", PURPLE),
        ("Cherry =    12000", PURPLE),
        ("Player = 20000000", CYAN),
        ("Bomb   =  8000000", CYAN),
    ]
    for s, col in lines:
        d.text(x, y, s, fill=col)
        y += SETTLE_ROW_DY
    d.text(x, y + 8, "Total = 123456780", fill=TEXT)
    d.text(x, y + 32, "Normal Rank  *1.0", fill=ORANGE)


def screen_title(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(40, 20, 30, 255))
    c.text(180, 90, "Perfect Cherry Blossom", fill=YELLOW)
    items = ["Start", "Extra Start", "Practice Start", "Quit",
             "Replay", "Result", "Music Room", "Option"]
    for i, s in enumerate(items):
        col = TEXT if i else YELLOW
        c.text(240, 200 + i * 20, s, fill=col)
    c.text(240, 200 + 0 * 20 - 12, "(selected = sprite v+64)", fill=TEXT_DIM,
           fnt=c.small_font)


def screen_result(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(14, 22, 30, 255))
    items = ["Easy  no kiroku", "Normal no kiroku", "Hard  no kiroku",
             "Lunatic no kiroku", "Extra no kiroku"]
    for i, s in enumerate(items):
        c.text(160, 120 + i * 32, s, fill=PURPLE if i else YELLOW)
    c.text(160, 288, "ofuda senreki", fill=PURPLE)
    c.text(448, 288, "modoru", fill=PURPLE)


def screen_scoretable(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(12, 18, 26, 255))
    c.text(60, 40, "Stage    HI-Score", fill=TEXT)
    for i in range(8):
        c.text(60, 64 + i * 20, "Stage%d %9d0 (%2d)" % (i + 1, 12345678, i + 1),
               fill=TEXT_DIM, fnt=c.small_font)
    c.text(60, 240, "No.   Name     Date   Player Score", fill=TEXT)
    for i in range(5):
        c.text(60, 264 + i * 18, "No.%02d Player  07/11    Reimu  %9d0"
               % (i + 1, 9876543 - i * 1000), fill=TEXT_DIM, fnt=c.small_font)


def screen_music(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(18, 14, 26, 255))
    c.rect(0, 0, LOGICAL_W, 64, fill=(40, 30, 50, 255))
    c.text(16, 24, "Music Room", fill=YELLOW)
    for i in range(12):
        c.text(24, 80 + i * 22, "No.%02d  track title" % (i + 1),
               fill=TEXT if i == 0 else TEXT_DIM, fnt=c.small_font)


def screen_staff(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(0, 0, 0, 255))
    for i in range(12):
        c.text(64, 40 + i * 32, "staff roll line %d" % (i + 1),
               fill=TEXT_DIM, fnt=c.small_font)


def screen_replay(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(16, 20, 28, 255))
    c.text(200, 60, "Replay List", fill=YELLOW)
    for i in range(10):
        c.text(120, 110 + i * 24, "%02d  %-8s Stage%d  %8d"
               % (i + 1, "Player", i % 7 + 1, 1234567), fill=TEXT_DIM,
               fnt=c.small_font)


SCREENS = {
    "game": screen_game,
    "settlement": screen_settlement,
    "title": screen_title,
    "result": screen_result,
    "scoretable": screen_scoretable,
    "music": screen_music,
    "staff": screen_staff,
    "replay": screen_replay,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", choices=sorted(SCREENS))
    ap.add_argument("--out", default="work/ui_preview")
    args = ap.parse_args()
    if Image is None:
        print("Pillow required", file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)

    names = [args.screen] if args.screen else list(SCREENS)
    made = 0
    for res in RESOLUTIONS:
        for name in names:
            c = Canvas(res)
            SCREENS[name](c)
            c.text(4, LOGICAL_H - 12,
                   "%s  %dx%d  scale=%.2f  canvas=%dx%d  bars=%d,%d"
                   % (res, c.sw, c.sh, c.scale, c.dw, c.dh, c.ox, c.oy),
                   fill=(128, 128, 140, 255), fnt=c.small_font)
            path = os.path.join(args.out, "%s_%s.png" % (name, res))
            c.save(path)
            made += 1
            print(f"{path}")
    print(f"\n{made} previews written to {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
