#!/usr/bin/env python3
"""Measure TH07 layouts from real screenshots.

The screenshots let the layout numbers be *verified* instead of inferred.
This script finds edges and colour bands in a screenshot so playfield bounds,
HUD columns and text rows can be read off in pixels.

Usage:
    python tools/shot_measure.py work/shots/05_game.png --columns
    python tools/shot_measure.py work/shots/05_game.png --rows
    python tools/shot_measure.py work/shots/05_game.png --playfield
"""
from __future__ import annotations

import argparse
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def load(path: str):
    img = Image.open(path).convert("RGB")
    return img, img.load()


def column_profile(px, w: int, h: int, y0: int, y1: int):
    """Per-column mean brightness, to find vertical bands/edges."""
    out = []
    for x in range(w):
        s = 0
        n = 0
        for y in range(y0, y1, 3):
            r, g, b = px[x, y]
            s += r + g + b
            n += 1
        out.append(s / (3 * n))
    return out


def row_profile(px, w: int, h: int, x0: int, x1: int):
    out = []
    for y in range(h):
        s = 0
        n = 0
        for x in range(x0, x1, 3):
            r, g, b = px[x, y]
            s += r + g + b
            n += 1
        out.append(s / (3 * n))
    return out


def find_edges(profile: list[float], thresh: float = 12.0):
    """Indices where the profile jumps by more than `thresh`."""
    edges = []
    for i in range(1, len(profile)):
        if abs(profile[i] - profile[i - 1]) > thresh:
            edges.append(i)
    return edges


def cluster(edges: list[int], gap: int = 4):
    if not edges:
        return []
    out = [[edges[0]]]
    for e in edges[1:]:
        if e - out[-1][-1] <= gap:
            out[-1].append(e)
        else:
            out.append([e])
    return [int(sum(c) / len(c)) for c in out]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--columns", action="store_true")
    ap.add_argument("--rows", action="store_true")
    ap.add_argument("--playfield", action="store_true")
    ap.add_argument("--y0", type=int, default=0)
    ap.add_argument("--y1", type=int, default=0)
    ap.add_argument("--x0", type=int, default=0)
    ap.add_argument("--x1", type=int, default=0)
    args = ap.parse_args()
    if Image is None:
        print("Pillow required", file=sys.stderr)
        return 1

    img, px = load(args.path)
    w, h = img.size
    print(f"{args.path}: {w}x{h}")

    if args.playfield:
        # The playfield is the bright region on the left; scan the middle row
        # band for the first strong brightness step.
        y0 = args.y0 or h // 4
        y1 = args.y1 or (3 * h) // 4
        prof = column_profile(px, w, h, y0, y1)
        edges = cluster(find_edges(prof, 18.0), 6)
        print(f"  vertical edges at x = {edges}")
        rprof = row_profile(px, w, h, 0, 384)
        redges = cluster(find_edges(rprof, 18.0), 6)
        print(f"  horizontal edges (x<384) at y = {redges}")

    if args.columns:
        y0 = args.y0 or 0
        y1 = args.y1 or h
        prof = column_profile(px, w, h, y0, y1)
        print("  column edges:", cluster(find_edges(prof), 5))

    if args.rows:
        x0 = args.x0 or 0
        x1 = args.x1 or w
        prof = row_profile(px, w, h, x0, x1)
        print("  row edges:", cluster(find_edges(prof), 5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
