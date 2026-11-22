#!/usr/bin/env python3
"""Bulk-classify every ECL opcode from the Ghidra export into a readable model.

For each `case N` (= opcode N+1) the decompiled body is reduced to:

  * param reads      - (mask bit, int/float, slot)
  * the compare      - e.g. "a != b", "a < b", "a >= b"
  * the action       - conditionally writes through *piVar10 / *pfVar11, or
                       calls a game function, or jumps
  * the write expr   - the exact RHS expression of the effect line

This turns 160 case bodies into a table a human can audit, which is the only
realistic way to cover everything without a runnable build.
"""
from __future__ import annotations

import argparse
import re
import sys

sys.path.insert(0, "tools")

from extract_opcodes import (  # noqa: E402
    find_switch,
    load,
    param_reads,
    split_cases,
)

# `if (A < B) goto LAB;`, `if (A >= B) ...` etc.  Operands are usually locals
# that were filled from `local_c[N]` or read_var(), so the raw names are kept
# and resolved back to slots by the caller.
CMP_RE = re.compile(r"if\s*\((.{1,60}?)\s*(!=|==|<=|>=|<|>)\s*(.{1,40}?)\)\s*(?:goto|return|)")
WRITE_RE = re.compile(r"\*\s*(?:piVar\w*|pfVar\w*|puVar\w*)\s*=\s*(.+);")
CALL_RE = re.compile(r"\b(FUN_[0-9a-f]{8}|\(\*\(code \*\)[^)]*\))\s*\(")
SLOT_RE = re.compile(r"local_c\[(\d+)\]")
LOCAL_RE = re.compile(r"\b(local_[0-9a-f]+)\b")


def slot_map(body: list[str]) -> dict[str, int]:
    """Map a local variable to the instruction slot it was loaded from."""
    out: dict[str, int] = {}
    for i, line in enumerate(body):
        m = re.search(r"(local_[0-9a-f]+)\s*=\s*(?:\([^)]*\))?\s*local_c\[(\d+)\]", line)
        if m:
            out[m.group(1)] = int(m.group(2))
            continue
        m = re.search(r"(local_[0-9a-f]+)\s*=\s*(?:\(float\))?\s*\(?(?:float|int)?\)?\s*FUN_0040e[5d]", line)
        if m:
            j = i
            while j < len(body) and "local_c[" not in body[j]:
                j += 1
            if j < len(body):
                s = SLOT_RE.search(body[j])
                if s:
                    out.setdefault(m.group(1), int(s.group(1)))
    return out


def resolve(expr: str, slots: dict[str, int]) -> str:
    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name in slots:
            return f"p{slots[name] - 2}"  # param ordinal (slot3 == p1)
        return name

    expr = LOCAL_RE.sub(sub, expr)
    return expr.strip()


def analyze(body: list[str], slots: dict[str, int]) -> dict:
    reads = param_reads(body)
    cmps = []
    for line in body:
        # Only real branch tests: a comparison over local_* operands.  Mask
        # tests look like `if ((*(ushort *)((int)local_c + 10) & 2) == 0)`, so
        # drop anything mentioning local_c or the cast plumbing.
        if "local_c" in line or "ushort" in line or "ushort" in line:
            continue
        m = CMP_RE.search(line)
        if m:
            left, op, right = m.group(1), m.group(2), m.group(3)
            if not (LOCAL_RE.search(left) or LOCAL_RE.search(right)):
                continue
            if any(k in left + right for k in ("0x270f", "0x2710")):
                continue
            cmps.append(f"{resolve(left, slots)} {op} {resolve(right, slots)}")
    writes = [resolve(m.group(1), slots) for m in (WRITE_RE.search(l) for l in body) if m]
    calls = []
    for line in body:
        for m in CALL_RE.finditer(line):
            fn = m.group(1)
            if fn.startswith("FUN_"):
                calls.append(fn)
            else:
                calls.append("indirect")
    jumps = [l.strip() for l in body if "goto switchD" in l or "goto LAB_" in l]
    return {"reads": reads, "cmps": cmps, "writes": writes, "calls": calls, "jumps": jumps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", nargs="?", default="th07.exe.c")
    ap.add_argument("--from", dest="lo", type=int, default=1)
    ap.add_argument("--to", dest="hi", type=int, default=161)
    args = ap.parse_args()

    lines = load(args.export)
    sw, end = find_switch(lines)
    cases = split_cases(lines, sw, end)

    for op in range(args.lo, args.hi + 1):
        idx = op - 1
        if idx not in cases:
            print(f"op{op:>3}: (no case)")
            continue
        body = cases[idx]
        slots = slot_map(body)
        a = analyze(body, slots)
        np = len(a["reads"])
        flags = "".join(("f" if "f32" in kind else "i") for _b, kind, _s in a["reads"])
        parts = [f"op{op:>3}", f"n={np}", flags.strip()]
        if a["cmps"]:
            parts.append("IF " + " / ".join(a["cmps"][:2]))
        if a["writes"]:
            parts.append("= " + a["writes"][0][:60])
        if a["calls"]:
            parts.append("call " + ",".join(dict.fromkeys(a["calls"]))[:70])
        if a["jumps"]:
            parts.append(a["jumps"][0][:50])
        print(" | ".join(p for p in parts if p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
