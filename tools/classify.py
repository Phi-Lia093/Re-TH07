#!/usr/bin/env python3
"""Classify every function by body shape so reading can be batched.

With 1429 functions, most of the remaining work is small helpers that share
shapes: getters, setters, matrix builders, stubs, allocators.  This groups
them by measurable properties so that one representative read covers a whole
class instead of opening each function individually.

Classes (first match wins):
    stub         body is empty or only `return <constant>`
    getter       reads one field, no writes outside the return
    setter       writes fields, has no reads of the same struct
    math_*       float arithmetic with sin/cos/sqrt and no struct offsets
    dispatch     a switch whose cases all call something
    allocator    calls operator_new / malloc
    big          >= 60 lines, needs individual reading

Usage:
    python tools/classify.py                # summary counts
    python tools/classify.py --list getter  # list members of one class
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys

PROFILE = "work/func_profile.json"
C_FILE = "th07.exe.c"

RET_CONST = re.compile(r"return\s+(-?\d+(?:\.\d+)?|0x[0-9a-f]+);")
FIELD_WRITE = re.compile(r"\*\s*\(\s*\w+\s*\*\s*\)\s*\(")
FIELD_READ = re.compile(r"\*\s*\(\s*\w+\s*\*\s*\)\s*[\(\w]")
MATH_FN = re.compile(r"\b(fsin|fcos|fsqrt|fabs|atan|tan|sin|cos|sqrt|pow|floor|ceil)\s*\(")
OFFSET = re.compile(r"\+ 0x[0-9a-f]{2,4}\)")
SWITCH = re.compile(r"switch\s*\(")
CALL = re.compile(r"\b(FUN_[0-9a-f]{8})\s*\(")
ALLOC = re.compile(r"\b(operator_new|_malloc|malloc|calloc)\s*\(")


def body_of(lines: list[str], start: int) -> list[str]:
    """Return the body lines of the function starting at `start` (0-based)."""
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
    ap.add_argument("--list", help="list members of a class")
    args = ap.parse_args()

    prof = json.load(open(PROFILE, encoding="utf-8"))
    lines = open(C_FILE, encoding="utf-8", errors="replace").read().splitlines()

    classes: dict[str, list[str]] = collections.defaultdict(list)
    for name, info in sorted(prof.items()):
        if not name.startswith("FUN_"):
            continue
        start = info["line"] - 1
        body = "\n".join(body_of(lines, start))
        nlines = info["lines"]
        stmts = body.count(";")

        if stmts <= 2 and (RET_CONST.search(body) or "return;" in body):
            classes["stub"].append(name)
        elif nlines >= 60:
            classes["big"].append(name)
        elif MATH_FN.search(body) and stmts <= 14:
            classes["math_matrix"].append(name)
        elif ALLOC.search(body):
            classes["allocator"].append(name)
        elif SWITCH.search(body) and stmts >= 8:
            classes["dispatch"].append(name)
        elif FIELD_WRITE.search(body) and not FIELD_READ.search(body):
            classes["setter"].append(name)
        elif FIELD_READ.search(body) and not FIELD_WRITE.search(body):
            classes["getter"].append(name)
        else:
            classes["other"].append(name)

    total = sum(len(v) for v in classes.values())
    print(f"{'class':<14}{'count':>6}   {'%':>5}")
    print("-" * 32)
    for k in sorted(classes, key=lambda k: -len(classes[k])):
        print(f"{k:<14}{len(classes[k]):>6}   {100*len(classes[k])/total:5.1f}")
    print(f"{'TOTAL':<14}{total:>6}")

    if args.list:
        members = classes.get(args.list, [])
        print(f"\n{args.list}: {len(members)}")
        for m in members[:60]:
            print(f"  {m}  {prof[m]['lines']}L")
    return 0


if __name__ == "__main__":
    sys.exit(main())
