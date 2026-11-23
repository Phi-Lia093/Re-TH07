#!/usr/bin/env python3
"""Render TH07 layout previews from *measured* screenshot geometry.

Unlike the first version, every constant here was measured from real 640x480
screenshots (see docs/14-screenshot-verification.md), so the previews can be
used to check the remaster's proportions against the original.

Measured facts baked in:
    screen             640 x 480
    playfield          x 32..416  (384 wide)
                       y 16..464  (448 tall)
    HUD text column    labels x 420, values x 505
    HUD rows           HiScore 50, Score 66, Player 98, Bomb 116,
                       Power 146, Graze 162, Point 178   (16px pitch)
    title menu         8 right-aligned rows, y 205..405, pitch ~27
    settlement         origin (144,128), title +32, rows +16

Usage:
    python tools/ui_preview.py
    python tools/ui_preview.py --screen game --res 1080p
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

# ---- measured geometry -----------------------------------------------------
PF_X0, PF_Y0 = 32, 16
PF_X1, PF_Y1 = 416, 464

HUD_LABEL_X = 420
HUD_VALUE_X = 505
HUD_ROWS = {
    "HiScore": 50,
    "Score": 66,
    "Player": 98,
    "Bomb": 116,
    "Power": 146,
    "Graze": 162,
    "Point": 178,
}

TITLE_MENU = ["Start", "Extra Start", "Practice Start", "Replay",
              "Result", "Music Room", "Option", "Quit"]
TITLE_MENU_Y0 = 205
TITLE_MENU_PITCH = 27
TITLE_MENU_RIGHT = 620

SETTLE_ORIGIN = (144, 128)
SETTLE_TITLE_DY = 32
SETTLE_ROW_DY = 16

OPTION_LABELS = ["Player", "Graphic", "BGM", "Sound", "Mode",
                 "SlowMode", "Reset", "KeyConfig", "Quit"]
OPTION_VALUES = ["1 2 3 4 5", "32Bit 16Bit", "Off Wav Midi", "Off On",
                 "FullScreen Window", "Off On", "", "", ""]
OPTION_Y0 = 116
OPTION_PITCH = 28

RESOLUTIONS = {"480p": (640, 480), "720p": (1280, 720), "1080p": (1920, 1080)}

BG = (16, 12, 22, 255)
PF = (24, 30, 44, 255)
PF_EDGE = (70, 90, 130, 255)
HUD_BG = (40, 26, 34, 255)
TEXT = (235, 235, 245, 255)
DIM = (140, 140, 160, 255)
YELLOW = (255, 255, 80, 255)
RED = (255, 90, 90, 255)
BLUE = (90, 140, 255, 255)
PURPLE = (210, 190, 255, 255)
CYAN = (150, 255, 220, 255)


def font(size: int):
    for name in ("consola.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, max(6, int(size)))
        except OSError:
            continue
    return ImageFont.load_default()


class Canvas:
    def __init__(self, res: str):
        self.sw, self.sh = RESOLUTIONS[res]
        self.scale = min(self.sw / LOGICAL_W, self.sh / LOGICAL_H)
        self.dw = int(LOGICAL_W * self.scale)
        self.dh = int(LOGICAL_H * self.scale)
        self.ox = (self.sw - self.dw) // 2
        self.oy = (self.sh - self.dh) // 2
        self.img = Image.new("RGBA", (self.sw, self.sh), (0, 0, 0, 255))
        self.d = ImageDraw.Draw(self.img)
        self.d.rectangle([self.ox, self.oy, self.ox + self.dw - 1,
                          self.oy + self.dh - 1], fill=BG)
        self.f = font(12 * self.scale)
        self.fs = font(9 * self.scale)

    def p(self, x, y):
        return (int(self.ox + x * self.scale), int(self.oy + y * self.scale))

    def rect(self, x0, y0, x1, y1, **kw):
        a, b = self.p(x0, y0), self.p(x1, y1)
        self.d.rectangle([a[0], a[1], b[0], b[1]], **kw)

    def text(self, x, y, s, fill=TEXT, f=None):
        self.d.text(self.p(x, y), s, fill=fill, font=f or self.f)

    def text_right(self, x, y, s, fill=TEXT, f=None):
        fnt = f or self.f
        w = self.d.textlength(s, font=fnt)
        self.d.text((self.p(x, y)[0] - w, self.p(x, y)[1]), s, fill=fill,
                    font=fnt)

    def save(self, path):
        self.img.convert("RGB").save(path)


def stars(c: Canvas, x: float, y: float, n: int, color) -> None:
    """Draw `n` 8x8 star icons starting at x, 16px apart (measured)."""
    for i in range(n):
        sx = x + i * 16
        c.rect(sx, y, sx + 7, y + 7, fill=color)


def screen_game(c: Canvas) -> None:
    c.rect(PF_X0, PF_Y0, PF_X1, PF_Y1, fill=PF, outline=PF_EDGE)
    c.rect(PF_X1, 0, LOGICAL_W, LOGICAL_H, fill=HUD_BG)
    c.text(PF_X0 + 8, PF_Y0 + 6, "PLAYFIELD 384x448 @ (32,16)", fill=DIM,
           f=c.fs)
    for name, y in HUD_ROWS.items():
        c.text(HUD_LABEL_X, y, name, fill=PURPLE, f=c.fs)
    c.text(HUD_VALUE_X, HUD_ROWS["HiScore"], "001000000", f=c.fs)
    c.text(HUD_VALUE_X, HUD_ROWS["Score"], "00000000", f=c.fs)
    stars(c, HUD_VALUE_X + 4, HUD_ROWS["Player"] + 1, 2, RED)
    stars(c, HUD_VALUE_X + 4, HUD_ROWS["Bomb"] + 1, 3, BLUE)
    c.text(HUD_VALUE_X, HUD_ROWS["Power"], "0", f=c.fs)
    c.text(HUD_VALUE_X, HUD_ROWS["Graze"], "0", f=c.fs)
    c.text(HUD_VALUE_X, HUD_ROWS["Point"], "0/50", f=c.fs)
    # vertical logo block + english title
    c.text(560, 300, "東方妖々夢", fill=PURPLE)
    c.text_right(545, 360, "Perfect", fill=CYAN, f=c.fs)
    c.text_right(545, 374, "Cherry", fill=CYAN, f=c.fs)
    c.text_right(545, 388, "Blossom", fill=CYAN, f=c.fs)
    c.text(536, 458, "60.00fps", fill=TEXT, f=c.fs)
    # stage title band
    c.text(70, 130, "Stage 1", fill=YELLOW)
    c.text(70, 150, "白銀の巻", fill=TEXT)
    c.text(70, 172, "Cherry petals must have fallen", fill=DIM, f=c.fs)
    # cherry counter bottom-left of playfield
    c.text(PF_X0 + 6, PF_Y1 - 18, "Cherry ↑   0/200000", fill=PURPLE, f=c.fs)


def screen_title(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(30, 24, 50, 255))
    c.text(150, 70, "東方妖々夢", fill=TEXT)
    c.text(150, 96, "Perfect Cherry Blossom", fill=PURPLE)
    for i, item in enumerate(TITLE_MENU):
        y = TITLE_MENU_Y0 + i * TITLE_MENU_PITCH - 180 + 185
        col = TEXT if i == 0 else DIM
        c.text_right(TITLE_MENU_RIGHT, y, item, fill=col)
    c.text_right(400, 440, "(C)opyright 2002-03 ZUN All rights reserved.",
                 fill=DIM, f=c.fs)
    c.text(340, 455, "ver 1.00b", fill=DIM, f=c.fs)
    c.text(560, 462, "60.02fps", fill=TEXT, f=c.fs)
    c.text(200, 350, "ゲームを開始します", fill=TEXT, f=c.fs)


def screen_option(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(30, 26, 60, 255))
    for i, (lab, val) in enumerate(zip(OPTION_LABELS, OPTION_VALUES)):
        y = OPTION_Y0 + i * OPTION_PITCH
        col = TEXT if i == 3 else DIM
        c.text(130, y, lab, fill=col)
        if val:
            c.text(240, y, val, fill=col)
        if i == 3:
            c.text(120, y, "*", fill=TEXT)
    c.text(150, 445, "プレイヤーの初期数を変更します。", fill=TEXT, f=c.fs)
    c.text(560, 462, "60.00fps", fill=TEXT, f=c.fs)


def screen_level(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(40, 20, 60, 255))
    c.text(210, 30, "難易度を選択すること", fill=TEXT)
    c.text(220, 48, "Choose Level", fill=PURPLE, f=c.fs)
    levels = [("入門", "Easy Level"), ("普通", "Normal Level"),
              ("困難", "Hard Level"), ("幻想", "Lunatic Level")]
    for i, (jp, en) in enumerate(levels):
        y = 100 + i * 80
        col = TEXT if i == 1 else DIM
        c.text(300, y, jp, fill=col)
        c.text(280, y + 18, en, fill=col)
        c.rect(260, y + 42, 380, y + 44, fill=DIM)


def screen_character(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(40, 20, 60, 255))
    c.text(230, 30, "主人公を選択すること", fill=TEXT)
    c.text(250, 48, "Choose Girl", fill=PURPLE, f=c.fs)
    c.rect(430, 60, 600, 400, fill=(60, 40, 80, 255), outline=DIM)
    c.text(440, 200, "[立绘]", fill=DIM)
    lines = ["楽園の素敵な巫女", "博麗 霊夢", "Reimu Hakurei",
             "", "移動速度  中", "低速速度  遅い", "攻撃能力  やや低"]
    for i, s in enumerate(lines):
        c.text(340, 250 + i * 16, s, fill=TEXT if i < 3 else DIM, f=c.fs)


def screen_settlement(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(10, 10, 18, 255))
    x, y = SETTLE_ORIGIN
    c.text(x, y, "Stage Clear", fill=YELLOW)
    y += SETTLE_TITLE_DY
    for s, col in [("Clear  =  3000000", YELLOW), ("Point  =  2500000", PURPLE),
                   ("Graze  =   500000", PURPLE), ("Cherry =    12000", PURPLE),
                   ("Player = 20000000", CYAN), ("Bomb   =  8000000", CYAN)]:
        c.text(x, y, s, fill=col, f=c.fs)
        y += SETTLE_ROW_DY
    c.text(x, y + 8, "Total = 123456780", fill=TEXT)
    c.text(x, y + 32, "Normal Rank  *1.0", fill=(255, 128, 128, 255), f=c.fs)


def screen_scoremenu(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(24, 16, 24, 255))
    c.text(40, 30, "幻想中", fill=TEXT)
    c.text(40, 54, "-- History of Score and Spell Card", fill=PURPLE, f=c.fs)
    items = ["Easy の記録を見る", "Normal の記録を見る", "Hard の記録を見る",
             "Lunatic の記録を見る", "Extra の記録を見る", "御札戦歴を見る",
             "その他の記録を見る", "戻る"]
    for i, s in enumerate(items):
        c.text(50, 100 + i * 28, s, fill=TEXT if i == 0 else DIM)
    c.rect(440, 60, 600, 420, fill=(50, 40, 55, 255), outline=DIM)
    c.text(450, 230, "[立绘]", fill=DIM)


def screen_scoretable(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(24, 16, 24, 255))
    c.text(40, 30, "幻想中", fill=TEXT)
    c.text(120, 76, "Normal", fill=(120, 200, 255, 255))
    for s, x in [("No", 30), ("Name", 60), ("Score(Stage)", 220),
                 ("Date", 420), ("Slow", 500)]:
        c.text(x, 120, s, fill=TEXT, f=c.fs)
    for i in range(10):
        c.text(30, 140 + i * 18, str(i + 1), fill=DIM, f=c.fs)
        c.text(60, 140 + i * 18, "-----------------", fill=DIM, f=c.fs)
        c.text(220, 140 + i * 18, "%8d0 (%d)" % (100 - i * 10, 1),
               fill=DIM, f=c.fs)
        c.text(420, 140 + i * 18, "--/--", fill=DIM, f=c.fs)
        c.text(500, 140 + i * 18, "0.00", fill=DIM, f=c.fs)
    c.rect(500, 60, 620, 420, fill=(50, 40, 55, 255), outline=DIM)


def screen_music(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(24, 14, 20, 255))
    c.text(30, 28, "妖々音楽室", fill=(150, 190, 255, 255))
    tracks = ["妖々夢 ～ Snow or Cherry Petal", "無何有の郷 ～ Deep Mountain",
              "クリスタライズシルバー", "遠野幻想物語",
              "ティアオイエツォン(withered leaf)", "ブクレシュティの人形師",
              "人形裁判 ～ 人の形弄びし少女", "天空の花の都",
              "幽霊楽団 ～ Phantom Ensemble", "東方妖々夢 ～ Ancient Temple"]
    for i, t in enumerate(tracks):
        mark = "▶" if i == 0 else "  "
        c.text(20, 60 + i * 18, f"{mark}{i + 1}. {t}",
               fill=TEXT if i == 0 else DIM, f=c.fs)
    c.rect(20, 250, 460, 430, fill=(0, 0, 0, 180))
    c.text(28, 258, "No.1 妖々夢 ～ Snow or Cherry Petal", fill=TEXT, f=c.fs)
    for i in range(4):
        c.text(28, 278 + i * 14, "コメント本文 ...", fill=DIM, f=c.fs)
    c.rect(470, 40, 620, 420, fill=(50, 40, 45, 255), outline=DIM)


def screen_replay(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(30, 20, 50, 255))
    c.text(180, 86, "眺美なるリプレイを見よう！", fill=YELLOW)
    for s, x in [("No.", 20), ("Name", 110), ("Date", 270),
                 ("Player", 370), ("Rank", 490)]:
        c.text(x, 130, s, fill=TEXT, f=c.fs)
    for i in range(10):
        c.text(20, 150 + i * 18, "%02d" % (i + 1), fill=DIM, f=c.fs)


def screen_staff(c: Canvas) -> None:
    c.rect(0, 0, LOGICAL_W, LOGICAL_H, fill=(0, 0, 0, 255))
    for i in range(12):
        c.text(64, 40 + i * 32, "staff roll line %d" % (i + 1),
               fill=DIM, f=c.fs)


def screen_loading(c: Canvas) -> None:
    c.rect(PF_X0, PF_Y0, PF_X1, PF_Y1, fill=(60, 60, 70, 255), outline=PF_EDGE)
    c.text(PF_X0 + 100, PF_Y0 + 180, "LOADING", fill=TEXT)
    # progress bar: measured placement inside the playfield band
    bx0, bx1 = PF_X0 + 16, PF_X1 - 16
    c.rect(bx0, 384, bx1, 384 + 48, fill=(90, 90, 100, 255), outline=DIM)


SCREENS = {
    "game": screen_game,
    "title": screen_title,
    "option": screen_option,
    "level": screen_level,
    "character": screen_character,
    "settlement": screen_settlement,
    "scoremenu": screen_scoremenu,
    "scoretable": screen_scoretable,
    "music": screen_music,
    "replay": screen_replay,
    "staff": screen_staff,
    "loading": screen_loading,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", choices=sorted(SCREENS))
    ap.add_argument("--res", choices=sorted(RESOLUTIONS))
    ap.add_argument("--out", default="docs/layout-previews")
    args = ap.parse_args()
    if Image is None:
        print("Pillow required", file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)

    names = [args.screen] if args.screen else list(SCREENS)
    ress = [args.res] if args.res else list(RESOLUTIONS)
    n = 0
    for res in ress:
        for name in names:
            c = Canvas(res)
            SCREENS[name](c)
            c.text(4, LOGICAL_H - 11,
                   "%s %dx%d scale=%.2f canvas=%dx%d bars=(%d,%d)"
                   % (res, c.sw, c.sh, c.scale, c.dw, c.dh, c.ox, c.oy),
                   fill=(120, 120, 130, 255), f=c.fs)
            c.save(os.path.join(args.out, f"{name}_{res}.png"))
            n += 1
    print(f"{n} previews -> {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
