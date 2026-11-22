#!/usr/bin/env python3
"""Per-opcode parameter layout report (L2 evidence for docs/02).

For every opcode that occurs in the real ECL data, print side by side:
  - the parameter bytes actually present (`size - 12` from th07.dat)
  - the param_mask values that occur
  - the masked parameter reads found in the decompiled case body
    (bit -> immediate/variable, int/float, slot)

This is a *report*, not a pass/fail test: each opcode has its own argument
layout, and the decompiled body does not always expose the destination slot
through the same mask idiom.  The report is what a human (or a later automated
pass) reconciles into the final instruction table.
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, "tools")

from ecl_dump import parse  # noqa: E402
from extract_opcodes import find_switch, load, param_reads, split_cases  # noqa: E402

INSTR_HEADER = 12


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", nargs="?", default="th07.exe.c")
    ap.add_argument("datadir", nargs="?", default="work/th07_dat")
    args = ap.parse_args()

    lines = load(args.export)
    sw, end = find_switch(lines)
    cases = split_cases(lines, sw, end)

    bytes_seen: dict[int, set[int]] = collections.defaultdict(set)
    masks: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in sorted(glob.glob(os.path.join(args.datadir, "*.ecl"))):
        for sub in parse(path).subs:
            for ins in sub.instrs:
                bytes_seen[ins.id].add(ins.size - INSTR_HEADER)
                masks[ins.id][ins.param_mask] += 1

    print(f"{'op':>4}  {'bytes':<12} {'masks':<24} masked reads (bit: kind slot)")
    print("-" * 96)
    for op in sorted(bytes_seen):
        idx = op - 1
        reads = param_reads(cases[idx]) if idx in cases else []
        rtxt = ", ".join(f"b{b}:{k.split()[0]}{'f' if 'f32' in k else 'i'}@{s[4:]}"
                         for b, k, s in reads) or "-"
        msk = ",".join(f"{m:#x}" for m in sorted(masks[op]))
        print(f"{op:>4}  {str(sorted(bytes_seen[op])):<12} {msk:<24} {rtxt}")
    print(f"\nopcodes seen in data: {len(bytes_seen)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
