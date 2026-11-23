#!/usr/bin/env python3
"""Check and de-duplicate the TH07 symbol tables.

Symbols accumulate across several module files as the reverse engineering
progresses, and the same address can get recorded twice (e.g. a helper first
noted while reading gfx and again while reading the ANM interpreter).  Ghidra
tolerates re-applying a name, but duplicates make the totals wrong and let the
two copies drift apart.

This tool reports duplicates and, with --fix, keeps the FIRST definition in
file-sorted order, removing later ones.  It also validates that every line is
well formed.

Usage:
    python tools/symbol_check.py            # report only
    python tools/symbol_check.py --fix      # remove duplicates
"""
from __future__ import annotations

import argparse
import glob
import re
import sys

SYM_DIR = "ghidra/symbols"
LINE_RE = re.compile(r"^((?:FUN|DAT|LAB)_[0-9a-f]{8})\s+([A-Za-z_]\w*)(?:\s+(.*))?$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(f"{SYM_DIR}/[0-9]*.txt"))
    seen: dict[str, tuple[str, str]] = {}      # addr -> (file, name)
    dup_addr: list[tuple[str, str, str]] = []
    bad: list[tuple[str, str]] = []
    total = 0

    for path in files:
        for n, raw in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = LINE_RE.match(line)
            if not m:
                bad.append((path, raw))
                continue
            total += 1
            addr, name = m.group(1), m.group(2)
            if addr in seen:
                prev_file, prev_name = seen[addr]
                if prev_name != name:
                    dup_addr.append((addr, prev_name, name))
                continue
            seen[addr] = (path, name)

    print(f"files            : {len(files)}")
    print(f"symbol lines     : {total}")
    print(f"unique addresses : {len(seen)}")
    print(f"duplicate lines  : {total - len(seen)}")
    if bad:
        print(f"\nmalformed lines: {len(bad)}")
        for p, l in bad[:10]:
            print(f"  {p}: {l[:60]}")
    if dup_addr:
        print("\nCONFLICTING names for the same address:")
        for addr, a, b in dup_addr:
            print(f"  {addr}: {a} vs {b}")
        print("  -> resolve by hand; --fix keeps the first")

    if args.fix:
        removed = 0
        for path in files:
            out = []
            for raw in open(path, encoding="utf-8").read().splitlines():
                s = raw.strip()
                m = LINE_RE.match(s) if s and not s.startswith("#") else None
                if m:
                    key = m.group(1)
                    if seen.get(key, (None, None))[0] != path:
                        removed += 1       # defined in an earlier file
                        continue
                out.append(raw)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out).rstrip("\n") + "\n")
        print(f"\nremoved {removed} duplicate line(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
