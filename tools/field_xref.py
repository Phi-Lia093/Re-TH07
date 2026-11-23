#!/usr/bin/env python3
"""Cross-reference a struct offset across every function that touches it.

This exists because of a real mistake: I named FUN_00441960 `player_die_sequence`
after seeing it hide sprites, spawn an effect and run stages -- all of which a
bomb also does. What settled it was looking at the OTHER functions that write
the same state field, which showed a spell-card ring being built.

So before naming anything by behaviour, dump every reader/writer of the field
that defines its state. A field's full usage pattern is far harder to
misinterpret than one function's surface.

Usage:
    python tools/field_xref.py 0x2408
    python tools/field_xref.py 0x2408 --writes-only
    python tools/field_xref.py 0x930 --context 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys

C_FILE = "th07.exe.c"
PROFILE = "work/func_profile.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("offset", help="e.g. 0x2408")
    ap.add_argument("--writes-only", action="store_true")
    ap.add_argument("--context", type=int, default=0,
                    help="extra lines of context around each hit")
    ap.add_argument("--max", type=int, default=40)
    args = ap.parse_args()

    off = args.offset.lower().replace("0x", "")
    # match `+ 0x2408)` and also byte-indexed forms like `+ 0x2408 +`
    pat = re.compile(r"\+ 0x" + off + r"\)")
    write_pat = re.compile(r"\+ 0x" + off + r"\)\s*=")

    prof = json.load(open(PROFILE, encoding="utf-8"))
    lines = open(C_FILE, encoding="utf-8", errors="replace").read().splitlines()

    # function ranges
    starts = sorted((info["line"] - 1, name) for name, info in prof.items())

    def owner(idx: int) -> str:
        lo, hi = 0, len(starts) - 1
        best = "(global)"
        while lo <= hi:
            mid = (lo + hi) // 2
            if starts[mid][0] <= idx:
                best = starts[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    hits = []
    for i, line in enumerate(lines):
        if args.writes_only:
            if not write_pat.search(line):
                continue
        elif not pat.search(line):
            continue
        hits.append((i + 1, owner(i), line.strip()))

    print(f"offset +0x{off}: {len(hits)} hit(s)\n")
    by_func: dict[str, int] = {}
    for _, fn, _ in hits:
        by_func[fn] = by_func.get(fn, 0) + 1

    print("functions touching this field:")
    for fn, n in sorted(by_func.items(), key=lambda kv: -kv[1]):
        print(f"  {fn:<16} {n} hit(s)")

    print()
    shown = 0
    for ln, fn, text in hits:
        print(f"{ln:>6} [{fn}] {text[:110]}")
        if args.context:
            for k in range(1, args.context + 1):
                if ln - 1 + k < len(lines):
                    print(f"       | {lines[ln - 1 + k].strip()[:100]}")
        shown += 1
        if shown >= args.max:
            print(f"... ({len(hits) - shown} more)")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
