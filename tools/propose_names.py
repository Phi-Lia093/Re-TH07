#!/usr/bin/env python3
"""Propose symbol names for TH07 functions from body shape, for review.

Fully manual naming does not scale to 1147 remaining functions. Most of them
are mechanically recognisable: a function that only reads one field is a
getter, one that only calls a single named function is a wrapper, one that
only writes constants is an initialiser.

This generates a *proposal list* with evidence for each name. Nothing is
written into the symbol tables automatically -- the operator reviews the
proposals and promotes them, because a confidently-wrong name is worse than an
honest FUN_xxxxxxx. Proposals carry a `confidence` note saying what the guess
rests on.

Usage:
    python tools/propose_names.py --limit 60
    python tools/propose_names.py --category getter
    python tools/propose_names.py --emit ghidra/symbols/11_auto.txt  # reviewed
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys

C_FILE = "th07.exe.c"
PROFILE = "work/func_profile.json"
SYM_DIR = "ghidra/symbols"

HEAD = re.compile(r"^(?:[a-zA-Z_][\w \*]*?)\s+(FUN_[0-9a-f]{8})\s*\(")
RET = re.compile(r"return\s+([^;]+);")

# Code partition, established from string evidence (see
# docs/21-binary-partition-map.md).  Above GAME_HI the binary is third-party
# libraries -- zlib ("invalid chunk type"), libpng, DirectDraw/DirectShow and
# CRT -- whose functions need no TH07-specific naming because a remaster will
# use modern replacements.  Naming them would be pure noise in the table.
GAME_LO, GAME_HI = 0x401000, 0x461000


def addr_of(name: str) -> int:
    return int(name.split("_")[1], 16)


def in_game_code(name: str) -> bool:
    return GAME_LO <= addr_of(name) < GAME_HI


def load_named() -> dict[str, str]:
    """address -> current symbol name, from the reviewed tables."""
    out: dict[str, str] = {}
    for path in glob.glob(f"{SYM_DIR}/[0-9]*.txt"):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^(FUN_[0-9a-f]{8})\s+(\w+)", line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def body_of(lines: list[str], start: int) -> str:
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
    return "\n".join(out)


def propose(name: str, info: dict, body: str, named: dict[str, str]):
    """Return (kind, proposed_short_name, reason) or None."""
    stmts = [s.strip() for s in body.split(";") if s.strip()]
    nline = info["lines"]

    # 1. pure stub
    if nline <= 4 and len(stmts) <= 1:
        r = RET.search(body)
        if r:
            return ("stub", f"stub_ret_{abs(hash(r.group(1))) & 0xfff:03x}",
                    f"returns {r.group(1)[:20]}")
        return ("stub", "stub_empty", "empty body")

    # 2. single-callee wrapper
    if len(info["calls"]) == 1 and nline <= 12:
        callee = info["calls"][0]
        cn = named.get(callee, callee)
        return ("wrapper", f"wrap_{cn}"[:44], f"only calls {cn}")

    # 3. list teardown: two or more obj_list_remove calls, nothing else
    fl = named.get("FUN_00430140", "obj_list_remove")
    if body.count(fl) >= 2 and len(stmts) <= 6:
        return ("teardown", f"teardown_{abs(hash(name)) & 0xffff:04x}",
                f"{body.count(fl)}x {fl}")

    # 4. constant-only writes -> initialiser
    if nline <= 12 and "=" in body and not info["calls"]:
        if re.search(r"= 0x[0-9a-f]{8};|= -?\d+\.\d+;|= 0;", body):
            return ("init", f"init_{abs(hash(name)) & 0xffff:04x}",
                    "writes constants only")

    # 5. getter: reads a field, one statement
    if len(stmts) <= 2 and "return" in body and "+ 0x" in body:
        return ("getter", f"get_{abs(hash(name)) & 0xffff:04x}",
                "single field read")

    # 6. setter: writes two or more constants to fixed offsets
    if nline <= 10 and body.count("= ") >= 2 and not info["calls"]:
        return ("setter", f"set_{abs(hash(name)) & 0xffff:04x}",
                "writes several fixed fields")

    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--category")
    ap.add_argument("--emit")
    args = ap.parse_args()

    prof = json.load(open(PROFILE, encoding="utf-8"))
    named = load_named()
    lines = open(C_FILE, encoding="utf-8", errors="replace").read().splitlines()

    props = []
    skipped_lib = 0
    for name, info in prof.items():
        if not name.startswith("FUN_") or name in named:
            continue
        if not in_game_code(name):
            skipped_lib += 1
            continue
        body = body_of(lines, info["line"] - 1)
        r = propose(name, info, body, named)
        if r:
            props.append((name, info, *r))

    by_cat = collections.Counter(p[2] for p in props)
    remaining = sum(1 for n in prof
                    if n.startswith("FUN_") and n not in named)
    print(f"proposals: {len(props)}  (unnamed {remaining}, "
          f"{skipped_lib} skipped as library code)")
    for k, v in by_cat.most_common():
        print(f"  {k:<10}{v:>5}")

    show = [p for p in props if not args.category or p[2] == args.category]
    print(f"\n{'address':<14}{'kind':<10}{'proposed':<34}reason")
    print("-" * 92)
    for name, info, kind, newname, reason in show[:args.limit]:
        print(f"{name:<14}{kind:<10}{newname:<34}{reason}")

    if args.emit:
        with open(args.emit, "w", encoding="utf-8") as f:
            f.write("# 自动提案 —— 未经人工复核，勿直接使用\n")
            for name, info, kind, newname, reason in props:
                f.write(f"{name}  {newname}   [{kind}] {reason}\n")
        print(f"\nwrote {len(props)} proposals to {args.emit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
