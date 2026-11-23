#!/usr/bin/env python3
"""Review batches of small functions with their bodies inline, and record names.

The bottleneck in covering the long tail is tool round-trips, not reading.
This script prints N function bodies with an index so a whole batch can be
reviewed in one output, and accepts names back as a compact list that it
appends to a symbol file.

Workflow:
    python tools/batch_review.py --max-lines 15 --count 40      # read
    python tools/batch_review.py --save <file> --assign "addr=name,..."

Usage:
    python tools/batch_review.py --max-lines 15 --count 40
    python tools/batch_review.py --save ghidra/symbols/16_misc.txt \
        --assign FUN_004017b0=counter_inc_capped,FUN_00418110=stub_empty
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

C_FILE = "th07.exe.c"
PROFILE = "work/func_profile.json"
GAME_LO, GAME_HI = 0x401000, 0x461000
DONE = "work/batch_review_done.txt"


def load_named() -> set[str]:
    out = set()
    for path in glob.glob("ghidra/symbols/*.txt"):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^(FUN_[0-9a-f]{8})\s", line)
            if m:
                out.add(m.group(1))
    if os.path.exists(DONE):
        out.update(l.strip() for l in open(DONE) if l.strip())
    return out


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
    ap.add_argument("--min-lines", type=int, default=0)
    ap.add_argument("--max-lines", type=int, default=15)
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--save")
    ap.add_argument("--assign")
    ap.add_argument("--mark-done", action="store_true")
    args = ap.parse_args()

    prof = json.load(open(PROFILE, encoding="utf-8"))
    lines = open(C_FILE, encoding="utf-8", errors="replace").read().splitlines()
    named = load_named()

    if args.assign:
        entries = []
        for pair in args.assign.split(","):
            addr, _, name = pair.partition("=")
            entries.append((addr.strip(), name.strip()))
        if args.save:
            os.makedirs(os.path.dirname(args.save), exist_ok=True)
            with open(args.save, "a", encoding="utf-8") as f:
                for addr, name in entries:
                    f.write(f"{addr}  {name}\n")
        if args.mark_done:
            with open(DONE, "a", encoding="utf-8") as f:
                for addr, _ in entries:
                    f.write(addr + "\n")
        print(f"assigned {len(entries)} name(s)"
              + (f" -> {args.save}" if args.save else ""))
        return 0

    pick = []
    for name, info in sorted(prof.items(), key=lambda kv: kv[1]["line"]):
        if not name.startswith("FUN_") or name in named:
            continue
        a = int(name.split("_")[1], 16)
        if not (GAME_LO <= a < GAME_HI):
            continue
        if args.min_lines <= info["lines"] <= args.max_lines:
            pick.append(name)
        if len(pick) >= args.count:
            break

    for idx, name in enumerate(pick):
        info = prof[name]
        body = body_of(lines, info["line"] - 1)
        print(f"\n[{idx}] {name} ({info['lines']}L in={len(info['callers'])} "
              f"out={len(info['calls'])})")
        print("\n".join(body))
    print(f"\n--- {len(pick)} function(s); reply with idx=name pairs ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
