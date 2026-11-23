#!/usr/bin/env python3
"""Group unnamed functions by which object they operate on.

A name like `init_8d64` is worthless, but knowing that 40 functions all touch
offset +0x930 on the same base pointer is not: it means they act on the same
object, and that object's identity can be established once and applied to the
whole group.

This clusters unnamed functions by their dominant struct offset and reports the
clusters, so one careful read of an object's layout can name many functions at
once.

Usage:
    python tools/cluster_objects.py
    python tools/cluster_objects.py --offset 0x930
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys

PROFILE = "work/func_profile.json"
SYM_DIR = "ghidra/symbols"
OFF = re.compile(r"\+ (0x[0-9a-f]{3,5})\)")


def load_named() -> dict[str, str]:
    out = {}
    for path in glob.glob(f"{SYM_DIR}/[0-9]*.txt"):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^(FUN_[0-9a-f]{8})\s+(\w+)", line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset")
    ap.add_argument("--min", type=int, default=6)
    args = ap.parse_args()

    prof = json.load(open(PROFILE, encoding="utf-8"))
    named = load_named()

    # Dominant offset must be the one that identifies the object, so ignore
    # small offsets that every struct has (list links, timers at 0x0..0x30).
    # Those are exactly the ones that made the first version of this tool
    # cluster unrelated functions together.
    GENERIC = range(0x00, 0x40)
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for name, info in prof.items():
        if not name.startswith("FUN_") or name in named:
            continue
        offs = [int(o, 16) for o in info["offsets"]]
        specific = [o for o in offs if o not in GENERIC]
        if not specific:
            continue
        groups[hex(specific[0])].append(name)
    clusters = groups

    if args.offset:
        key = args.offset.lower()
        members = clusters.get(key, [])
        print(f"functions whose dominant non-generic offset is {key}: "
              f"{len(members)}")
        for m in sorted(members):
            print(f"  {m}  {prof[m]['lines']}L")
        return 0

    print(f"{'offset':<10}{'count':>6}  sample functions")
    print("-" * 76)
    for off, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        if len(members) < args.min:
            continue
        sample = " ".join(members[:3])
        print(f"{off:<10}{len(members):>6}  {sample}")

    big = sum(len(v) for v in clusters.values())
    remaining = sum(1 for n in prof if n.startswith("FUN_") and n not in named)
    print(f"\nunnamed with a dominant offset: {big} / {remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
