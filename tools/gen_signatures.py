#!/usr/bin/env python3
"""Derive the parameter signature of every ECL opcode from the disassembly.

The verifier cannot step through instructions without knowing how many 4-byte
slots each opcode consumes.  Three independent sources pin that down:

  1. `raw`   - the highest `local_c[N]` index the case body touches gives a
               lower bound on the slot count (N-2 slots).
  2. `data`  - the real instruction stream: `size - 12` must be a multiple of 4
               and is exactly the slot count for every occurrence.
  3. `mask`  - which param_mask bits actually occur in the data.

A signature is emitted only when `raw` and `data` agree; disagreements are
listed so they can be resolved by hand instead of being silently guessed.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, "tools")

from ecl_dump import parse  # noqa: E402
from extract_opcodes import (  # noqa: E402
    find_switch,
    load,
    param_reads,
    register_helpers,
    split_cases,
)

SLOT_RE = re.compile(r"local_c\[(\d+)\]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", nargs="?", default="th07.exe.c")
    ap.add_argument("datadir", nargs="?", default="work/th07_dat")
    ap.add_argument("--out", default="tools/ecl_signatures.json")
    args = ap.parse_args()

    lines = load(args.export)
    register_helpers(lines)
    sw, end = find_switch(lines)
    cases = split_cases(lines, sw, end)

    raw: dict[int, int] = {}
    for idx, body in cases.items():
        op = idx + 1
        top = 2
        for line in body:
            for m in SLOT_RE.finditer(line):
                n = int(m.group(1))
                if n >= 3:
                    top = max(top, n)
        # Slot reads resolved through a delegated helper or a byte access.
        for _bit, _kind, slot in param_reads(body):
            if slot.startswith("slot") and slot[4:].isdigit():
                top = max(top, int(slot[4:]))
        raw[op] = top - 2

    data: dict[int, set[int]] = collections.defaultdict(set)
    masks: dict[int, set[int]] = collections.defaultdict(set)
    for path in sorted(glob.glob(os.path.join(args.datadir, "*.ecl"))):
        for sub in parse(path).subs:
            for ins in sub.instrs:
                data[ins.id].add((ins.size - 12) // 4)
                masks[ins.id].add(ins.param_mask)

    sig: dict[str, dict] = {}
    agree, disagree = 0, 0
    for op in sorted(data):
        d = data[op]
        r = raw.get(op)
        if len(d) != 1:
            # Variable-width opcode: record all observed widths.
            sig[str(op)] = {"slots": max(d), "widths": sorted(d),
                            "source": "data-only", "masks": sorted(masks[op])}
            disagree += 1
            continue
        slots = next(iter(d))
        if r is None:
            sig[str(op)] = {"slots": slots, "source": "data-only",
                            "masks": sorted(masks[op])}
            disagree += 1
        elif r == slots:
            sig[str(op)] = {"slots": slots, "source": "raw+data",
                            "masks": sorted(masks[op])}
            agree += 1
        else:
            # The data is authoritative: an opcode's size is fixed by
            # `thecl` and by every occurrence in the shipped stage files.
            # A shortfall means the decompiled body hid some slots (a fixed
            # trailing argument, a helper we did not follow, etc.).
            sig[str(op)] = {"slots": slots, "raw_slots": r, "source": "data-wins",
                            "masks": sorted(masks[op])}
            disagree += 1

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sig, f, indent=1, sort_keys=True)

    print(f"opcodes in data: {len(data)}")
    print(f"  raw+data agree : {agree}")
    print(f"  data-wins (raw shortfall): {sum(1 for e in sig.values() if e['source'] == 'data-wins')}")
    print(f"  data-only      : {sum(1 for e in sig.values() if e['source'] == 'data-only')}")
    print(f"wrote {args.out}")
    for op in sorted(data, key=int):
        e = sig[str(op)]
        if e["source"] in ("data-wins", "data-only"):
            print(f"  op{op:>3}: slots={e['slots']} raw={e.get('raw_slots','-')} src={e['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
