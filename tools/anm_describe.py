#!/usr/bin/env python3
"""Describe every TH07 ANM: what its sprites actually contain.

Produces the "ANM atlas inventory" used to reason about UI layout: for each
entry it reports the atlas size, pixel format, sprite count and the sprite
rect histogram, plus a per-sprite table when asked.

Key structural facts (all verified against the 63 shipped files):

  * `ascii.anm` is the font atlas.  Its 16x16 sprites are a character grid and
    **the sprite id equals the ASCII code** -- to draw the character 'A' the
    engine issues set_sprite(65).  There are 98 such sprites, ids 31..128.
  * Atlases may hold several entries chained by nextoffset; each entry has its
    own THTX pixels and sprite table.
  * Sprite rects give UV directly: (x/tw, y/th) .. ((x+w)/tw, (y+h)/th).

Usage:
    python tools/anm_describe.py                  # inventory of all ANMs
    python tools/anm_describe.py ascii --sprites  # per-sprite listing
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, "tools")

from anm_parse import FORMATS, AnmFile  # noqa: E402

# What each animation file is for, in the game's own terms.  Established from
# the exported atlases (see docs/11-anm-atlas-inventory.md).
PURPOSE = {
    "ascii": "字体图集：ASCII 字符表 + HUD 标签（PowerUp/Bonus/Cherry/Enemy/Pause 等）",
    "etama": "敌弹图集：多颜色 × 多形状子弹",
    "player00": "自机 灵梦（行走/倾斜帧 + Bomb 特效 + Spellcard 背景）",
    "player01": "自机 魔理沙",
    "player02": "自机 咲夜",
    "eff01": "全屏特效层 1",
    "eff02": "全屏特效层 2",
    "eff03": "特效层 3",
    "eff04": "特效层 4",
    "eff04b": "特效层 4b",
    "eff05": "特效层 5（双条目：底色 + 叠加）",
    "eff06": "特效层 6（双条目）",
    "eff07": "特效层 7（双条目）",
    "eff08": "特效层 8（双条目）",
    "front": "前景装饰（标题画面樱花等）",
    "loading": "读盘画面背景（384x448 = 游戏区尺寸）",
    "loading2": "读盘画面 2",
    "loading3": "读盘画面 3",
    "title01": "标题界面（e0: 主视觉；e1: 全部菜单文字 94 项）",
    "result00": "成绩查看菜单（e0: 难度列表；e1: 成绩表头/行）",
    "music00": "音乐室背景",
    "staff01": "STAFF 名单（512x32 每行一条）",
    "capture": "截屏保存（占位，无 THTX）",
}


def describe(path: str, show_sprites: bool) -> None:
    name = os.path.basename(path)[:-4]
    anm = AnmFile(path)
    print(f"\n=== {name}.anm ===")
    print(f"  {PURPOSE.get(name, '(未知用途)')}")
    for ei, e in enumerate(anm.entries):
        if not e.thtx_ok:
            print(f"  [entry{ei}] 无 THTX（占位条目）")
            continue
        fmt = FORMATS.get(e.thtx_format, (f"fmt{e.thtx_format}",))[0]
        hist = collections.Counter(f"{s['w']:.0f}x{s['h']:.0f}"
                                  for s in e.sprite_list)
        print(f"  [entry{ei}] atlas {e.tw}x{e.th} {fmt}  "
              f"sprites={e.sprites} scripts={e.scripts}")
        print(f"            尺寸分布: "
              + " ".join(f"{k}:{v}" for k, v in hist.most_common(6)))
        if show_sprites:
            for s in e.sprite_list:
                u0, v0 = s["x"] / e.tw, s["y"] / e.th
                u1, v1 = (s["x"] + s["w"]) / e.tw, (s["y"] + s["h"]) / e.th
                note = ""
                if name == "ascii" and abs(s["w"] - 16) < 0.5 and abs(s["h"] - 16) < 0.5:
                    if 32 <= s["id"] < 127:
                        note = f"  glyph {chr(s['id'])!r}"
                print(f"      id={s['id']:>3}  uv=({s['x']:>4.0f},{s['y']:>4.0f})"
                      f"  size=({s['w']:>4.0f}x{s['h']:>4.0f})"
                      f"  norm=({u0:.4f},{v0:.4f})-({u1:.4f},{v1:.4f}){note}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="ANM base names, e.g. ascii title01")
    ap.add_argument("--sprites", action="store_true", help="list every sprite")
    args = ap.parse_args()

    if args.names:
        paths = [f"work/th07_dat/{n}.anm" for n in args.names]
    else:
        paths = sorted(glob.glob("work/th07_dat/*.anm"))

    for path in paths:
        describe(path, args.sprites)
    return 0


if __name__ == "__main__":
    sys.exit(main())
