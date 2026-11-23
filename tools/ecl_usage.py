#!/usr/bin/env python3
"""Answer "how is this opcode actually used?" from the shipped ECL data.

Reading the interpreter tells you what an instruction *does*. It does not tell
you how scripts actually use it, and the two can differ in ways that matter: I
initially documented conditional ops as guarding a following jump, then found
that pattern occurs zero times in the real data.

This tool computes successor statistics so usage claims can be checked instead
of assumed.

Usage:
    python tools/ecl_usage.py --follow 30-39        # what follows compares
    python tools/ecl_usage.py --op 4                # what precedes op 4
    python tools/ecl_usage.py --common              # overall opcode frequency
"""
from __future__ import annotations

import argparse
import collections
import glob
import sys

sys.path.insert(0, "tools")

from ecl_dump import parse  # noqa: E402


def parse_range(spec: str) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--follow", help="opcode range, e.g. 30-39")
    ap.add_argument("--op", type=int, help="show neighbours of this opcode")
    ap.add_argument("--common", action="store_true")
    ap.add_argument("--files", default="work/th07_dat/ecldata*.ecl")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.files))
    if not paths:
        print("no ECL files found", file=sys.stderr)
        return 1

    total = 0
    subset = parse_range(args.follow) if args.follow else set()
    follow = collections.Counter()
    precede = collections.Counter()
    freq = collections.Counter()

    for path in paths:
        try:
            ecl = parse(path)
        except Exception as exc:                     # noqa: BLE001
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        for sub in ecl.subs:
            ins = sub.instrs
            total += len(ins)
            for i, cur in enumerate(ins):
                freq[cur.id] += 1
                if subset and cur.id in subset and i + 1 < len(ins):
                    follow[ins[i + 1].id] += 1
                if args.op is not None and cur.id == args.op and i > 0:
                    precede[ins[i - 1].id] += 1

    print(f"{len(paths)} files, {total} instructions\n")

    if args.common:
        print("opcode frequency (top 25):")
        for op, n in freq.most_common(25):
            print(f"  op{op:<4}{n:>7}")

    if subset:
        print(f"\nwhat follows op{args.follow}:")
        for op, n in follow.most_common(15):
            print(f"  op{op:<4}{n:>6}")

    if args.op is not None:
        print(f"\nwhat precedes op{args.op}:")
        for op, n in precede.most_common(15):
            print(f"  op{op:<4}{n:>6}")

    if not (args.common or subset or args.op is not None):
        print("pick --common, --follow or --op")
    return 0


if __name__ == "__main__":
    sys.exit(main())
