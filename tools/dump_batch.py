#!/usr/bin/env python3
"""Dump several function bodies at once for batch reading.

Reading one function per tool call does not scale to 1429 functions. This
prints N function bodies from the decompiled C in a single pass, so a batch of
small helpers can be reviewed together and named in one go.

Usage:
    python tools/dump_batch.py --max-lines 12 --count 30
    python tools/dump_batch.py --range 4017 4052
    python tools/dump_batch.py --names FUN_004017b0,FUN_004052d0
"""
from __future__ import annotations

import argparse
import json
import re
import sys

C_FILE = "th07.exe.c"
PROFILE = "work/func_profile.json"

HEAD_RE = re.compile(r"^(?:[a-zA-Z_][\w \*]*?)\s+(FUN_[0-9a-f]{8}|[A-Za-z_]\w*)\s*\(")


def body_of(lines: list[str], start: int) -> list[str]:
    depth = 0
    started = False
    out = []
    for i in range(start, min(start + 4000, len(lines))):
        line = lines[i]
        out.append(line)
        depth += line.count("{") - line.count("}")
        if "{" in line:
            started = True
        if started and depth <= 0:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lines", type=int, default=12)
    ap.add_argument("--min-lines", type=int, default=0)
    ap.add_argument("--count", type=int, default=25)
    ap.add_argument("--range", nargs=2, metavar=("LO", "HI"))
    ap.add_argument("--names")
    args = ap.parse_args()

    prof = json.load(open(PROFILE, encoding="utf-8"))
    lines = open(C_FILE, encoding="utf-8", errors="replace").read().splitlines()

    pick: list[str] = []
    if args.names:
        pick = args.names.split(",")
    else:
        for name, info in sorted(prof.items(),
                                 key=lambda kv: kv[1]["line"]):
            if not name.startswith("FUN_"):
                continue
            if args.range:
                a = int(name.split("_")[1], 16)
                lo = int(args.range[0], 16)
                hi = int(args.range[1], 16)
                if not (lo <= a <= hi):
                    continue
            n = info["lines"]
            if args.min_lines <= n <= args.max_lines:
                pick.append(name)
            if len(pick) >= args.count:
                break

    for name in pick:
        info = prof.get(name)
        if not info:
            continue
        body = body_of(lines, info["line"] - 1)
        print(f"\n=== {name} ({info['lines']}L, "
              f"in={len(info['callers'])}, out={len(info['calls'])}) ===")
        print("\n".join(body))
    print(f"\n--- {len(pick)} function(s) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
