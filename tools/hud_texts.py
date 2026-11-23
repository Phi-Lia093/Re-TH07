#!/usr/bin/env python3
"""Find every string passed to TH07's text drawer, with its call site.

The engine draws text through one helper:

    FUN_00402060(anm, &posStruct, "format", ...)

so *every* string literal that reaches a HUD/UI is distinguishable by locating
calls to that function.  This script scans the decompiled C for
`FUN_00402060(..., "literal", ...)` and reports each literal plus the function
it lives in, which is how the per-screen text inventory is built.

Usage:
    python tools/hud_texts.py                 # list all drawn strings
    python tools/hud_texts.py --func 428      # only one function (hex prefix)
"""
from __future__ import annotations

import argparse
import collections
import re
import sys

C_FILE = "th07.exe.c"
CALL_RE = re.compile(r'FUN_00402060\s*\([^;]*?"((?:[^"\\]|\\.)*)"')
FUNC_RE = re.compile(r"^[a-zA-Z_][\w \*]*\s+(FUN_[0-9a-f]{8})\(.*\)\s*$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--func", help="restrict to functions whose name contains this")
    args = ap.parse_args()

    with open(C_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    current = "(global)"
    by_func: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for n, line in enumerate(lines, 1):
        m = FUNC_RE.match(line)
        if m:
            current = m.group(1)
            continue
        for tm in CALL_RE.finditer(line):
            by_func[current].append((n, tm.group(1)))

    total = sum(len(v) for v in by_func.values())
    print(f"text draw calls with literal strings: {total}\n")
    for func in sorted(by_func, key=lambda k: str(by_func[k][0][0])):
        if args.func and args.func.lower() not in func.lower():
            continue
        print(f"=== {func} ===")
        seen = set()
        for line_no, text in by_func[func]:
            if text in seen:
                continue
            seen.add(text)
            print(f"  line {line_no:>6}  {text!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
