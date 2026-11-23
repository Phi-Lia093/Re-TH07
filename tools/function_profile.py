#!/usr/bin/env python3
"""Profile every function in the decompiled C so reading scales.

Reading 1400 functions one tool call at a time is impractical.  This extracts,
for each function, the facts that make naming and comprehension tractable
without reading every line:

  * calls out         - which functions it invokes (gives its role)
  * called by         - hub functions are API surface, leaves are helpers
  * string literals   - often identify the function outright
  * numeric constants - coordinates/sizes reveal UI vs gameplay code
  * struct offsets    - `*(int *)(param_1 + 0xNNN)` clusters identify which
                        object the function operates on
  * callee-pattern    - a function that only calls one named helper is often
                        a thin wrapper and can be named mechanically

Output is one JSON file plus a compact table, used to plan and to fill in
symbols without re-scanning the 87k-line file each time.

Usage:
    python tools/function_profile.py                 # build work/func_profile.json
    python tools/function_profile.py --table 0000    # show a range
    python tools/function_profile.py --find ecl_     # functions calling ecl_*
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

C_FILE = "th07.exe.c"
OUT = "work/func_profile.json"

# Some definitions put the calling convention on its own line, e.g.
#   void __fastcall
#   FUN_00405370(int a, ...)
# so match the name at the start of ANY line and accept the signature on the
# same or next line. Without the \n? form these 79 functions were silently
# absent from the profile and every coverage figure was overstated.
FUNC_HEAD = re.compile(
    r"^(?:[a-zA-Z_][\w \*]*?\s+)?(FUN_[0-9a-f]{8}|__\w+|[a-z_][\w]*)\s*\(")
STR_RE = re.compile(r'"((?:[^"\\]|\\.){2,})"')
OFF_RE = re.compile(r"\+ (0x[0-9a-f]{2,4})\)")
FLOAT_RE = re.compile(r"=\s*(-?\d+\.\d+)\s*;")
HEX_RE = re.compile(r"=\s*0x([0-9a-f]{8})\s*;")
CALL_RE = re.compile(r"\b(FUN_[0-9a-f]{8})\s*\(")


def build() -> dict:
    with open(C_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    prof: dict[str, dict] = {}
    current = None
    body: list[str] = []
    start = 0

    def flush(name: str, body: list[str], start: int) -> None:
        text = "\n".join(body)
        offs = collections.Counter(int(m, 16) for m in OFF_RE.findall(text))
        prof[name] = {
            "line": start,
            "lines": len(body),
            "calls": sorted(set(CALL_RE.findall(text))),
            "strings": sorted({m for m in STR_RE.findall(text)})[:8],
            "offsets": [f"0x{o:03x}" for o, _ in offs.most_common(10)],
            "floats": sorted({m for m in FLOAT_RE.findall(text)})[:8],
            "hex32": sorted({m for m in HEX_RE.findall(text)})[:8],
        }

    for i, line in enumerate(lines):
        m = FUNC_HEAD.match(line)
        if m:
            nxt = "".join(lines[i + 1:i + 3])
            if "{" in nxt:
                if current:
                    flush(current, body, start)
                current = m.group(1)
                body = []
                start = i + 1
                continue
        if current is not None:
            body.append(line)
            if line == "}":
                flush(current, body, start)
                current = None
                body = []
    if current:
        flush(current, body, start)

    # reverse edges
    callers: dict[str, list[str]] = collections.defaultdict(list)
    for name, p in prof.items():
        for callee in p["calls"]:
            callers[callee].append(name)
    for name, p in prof.items():
        p["callers"] = sorted(callers.get(name, []))
    return prof


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", nargs=2, metavar=("LO", "HI"))
    ap.add_argument("--find", help="substring of a callee name")
    ap.add_argument("--top", type=int, default=0)
    args = ap.parse_args()

    os.makedirs("work", exist_ok=True)
    prof = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=0, sort_keys=True)
    print(f"profiled {len(prof)} functions -> {OUT}")

    if args.find:
        hits = [(n, p) for n, p in prof.items()
                if any(args.find in c for c in p["calls"])]
        print(f"\nfunctions calling *{args.find}* : {len(hits)}")
        for n, p in sorted(hits, key=lambda kv: -kv[1]["lines"])[:20]:
            print(f"  {n}  {p['lines']:>4}L  calls={len(p['calls'])}")

    if args.top:
        sizes = sorted(prof.items(), key=lambda kv: -kv[1]["lines"])
        print(f"\nlargest {args.top}:")
        for n, p in sizes[:args.top]:
            print(f"  {n}  {p['lines']:>4}L  in={len(p['callers'])} "
                  f"out={len(p['calls'])}  {p['strings'][:1]}")

    if args.table:
        lo, hi = args.table[0].lower(), args.table[1].lower()
        print(f"\n{'func':<14}{'lines':>6}{'in':>4}{'out':>5}  strings / offsets")
        for n in sorted(prof):
            addr = n.split("_")[-1]
            if not (lo <= addr <= hi):
                continue
            p = prof[n]
            s = p["strings"][0][:34] if p["strings"] else ""
            print(f"{n:<14}{p['lines']:>6}{len(p['callers']):>4}"
                  f"{len(p['calls']):>5}  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
