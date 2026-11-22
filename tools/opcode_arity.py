#!/usr/bin/env python3
"""Cross-check opcode arity between the Ghidra export and the real ECL data.

Two independent sources:
  A) ECL data: `size` of each instruction in the 8 ecldata files gives the
     exact parameter byte count (size - 12) for every mask combination that
     actually occurs in the game.
  B) Ghidra export: param_mask bits tell us which slots are present.

This script reports, per opcode, the observed sizes and mask bits so the two
can be reconciled.  It is the main sanity check when the decompiled C is
ambiguous about a "destination" argument (a slot written rather than read).
"""
from __future__ import annotations

import collections
import glob
import sys

sys.path.insert(0, "tools")

from ecl_dump import parse  # noqa: E402

INSTR_HEADER = 12


def main(pattern: str) -> int:
    sizes: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    masks: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    counts: collections.Counter = collections.Counter()

    for path in sorted(glob.glob(pattern)):
        ecl = parse(path)
        for sub in ecl.subs:
            for ins in sub.instrs:
                sizes[ins.id][ins.size] += 1
                masks[ins.id][ins.param_mask] += 1
                counts[ins.id] += 1

    print(f"{'op':>4} {'n':>6}  {'sizes(-12)':<22} masks")
    print("-" * 78)
    for op in sorted(sizes):
        szs = {s - INSTR_HEADER: c for s, c in sorted(sizes[op].items())}
        msk = ",".join(f"0x{m:x}" for m in sorted(masks[op]))
        print(f"{op:>4} {counts[op]:>6}  {str(szs):<22} {msk}")

    print(f"\nopcodes observed: {len(sizes)}  total instructions: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    pat = sys.argv[1] if len(sys.argv) > 1 else "work/th07_dat/*.ecl"
    sys.exit(main(pat))
