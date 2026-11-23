#!/usr/bin/env python3
"""Inventory the decompiled binary so symbol recovery can be planned.

Reading 90k lines is only tractable if the *work* is quantified first: how
many functions are there, how big are they, which ones matter, and how much
of the file is actually unique logic versus compiler/CRT noise.

This produces that census:
  * function count and size distribution
  * the CRC/CRT/library bulk (typically the tail of .text)
  * call-graph hubs (most-called functions = the real API surface)
  * the largest functions (the ones worth reading first)

Usage:
    python tools/census.py
    python tools/census.py --top 40
"""
from __future__ import annotations

import argparse
import collections
import re
import sys

C_FILE = "th07.exe.c"

FUNC_DEF = re.compile(r"^(?:[a-zA-Z_][\w \*]*?)\s+(FUN_[0-9a-f]{8}|[a-z_][\w]*)\s*\((.*)\)\s*$")
BODY_END = re.compile(r"^\}$")
CALL = re.compile(r"\b([A-Za-z_][\w]*)\s*\(")

# Names that are compiler/CRT/library machinery rather than game logic.
LIB_HINTS = re.compile(
    r"^(_|__)?(eh_|seh_|ftol|chkstk|memset|memcpy|memmove|strlen|strcpy|strcmp|"
    r"sprintf|malloc|free|calloc|realloc|operator|sqrt|fcos|fsin|floor|ceil|pow|"
    r"atan|tan|sin|cos|abs|fabs|rand|srand|abort|exit|printf|fprintf|vfprintf|"
    r"qsort|bsearch|getenv|atoi|strtol|toupper|tolower|isalpha|isdigit|"
    r"GetLastError|SetLastError|Rtl|Interlocked)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    funcs: dict[str, int] = {}          # name -> line count
    calls: collections.Counter = collections.Counter()
    current: str | None = None
    lines_by_func: dict[str, int] = {}

    with open(C_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    total = len(lines)
    for i, line in enumerate(lines):
        m = FUNC_DEF.match(line)
        if m and "(" in line and not line.strip().startswith("//"):
            name = m.group(1)
            # a real definition is followed (within 3 lines) by a brace
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            nxt2 = lines[i + 2] if i + 2 < len(lines) else ""
            if "{" in nxt or "{" in nxt2:
                current = name
                start = i
                continue
        if current is not None and BODY_END.match(line):
            funcs[current] = i - start + 1
            current = None

    for i, line in enumerate(lines):
        for m in CALL.finditer(line):
            calls[m.group(1)] += 1

    named = [n for n in funcs if not LIB_HINTS.match(n)]
    lib = [n for n in funcs if LIB_HINTS.match(n)]

    print(f"decompiled C file      : {total} lines")
    print(f"functions with bodies  : {len(funcs)}")
    print(f"  game/logic functions : {len(named)}")
    print(f"  library/CRT-looking  : {len(lib)}")
    print()

    sizes = sorted(funcs.items(), key=lambda kv: -kv[1])
    print("=== 最大的函数（优先阅读） ===")
    for name, n in sizes[:args.top]:
        tag = "LIB" if LIB_HINTS.match(name) else "   "
        print(f"  {tag} {name:<28} {n:>6} lines")
    print()

    print("=== 调用图枢纽（被调用最多的函数） ===")
    for name, n in calls.most_common(args.top):
        if name in funcs:
            print(f"  {name:<28} called {n:>5}x  ({funcs[name]} lines)")

    # how much do the top N functions cover?
    top50 = sum(n for _nm, n in sizes[:50])
    print()
    print(f"top 50 functions cover {top50} lines "
          f"({100 * top50 / max(1, total):.1f}% of the file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
