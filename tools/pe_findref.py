#!/usr/bin/env python3
"""Locate a string in th07.exe and find code that references its address.

Ghidra's C export inlines string data as `DAT_xxxxxxxx` labels, so searching
the text for the literal is fruitless.  This resolves strings through the PE
image and then reports every instruction that loads the address, which is how
we reach the code that consumes a format (e.g. the .sht loader).

Usage:
    python tools/pe_findref.py ply00a.sht
    python tools/pe_findref.py "player01.anm" --show-code 20
"""
from __future__ import annotations

import argparse
import struct
import sys

EXE = "th07.exe"


class PE:
    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            self.data = f.read()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        n = struct.unpack_from("<H", self.data, pe + 6)[0]
        opt = pe + 24
        self.base = struct.unpack_from("<I", self.data, opt + 28)[0]
        self.sections = []
        sec = opt + struct.unpack_from("<H", self.data, pe + 20)[0]
        for i in range(n):
            off = sec + i * 40
            name = self.data[off : off + 8].rstrip(b"\0").decode("latin1")
            vs, va, rs, ra = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((name, va, vs, ra, rs))

    def off_to_va(self, off: int) -> int | None:
        for _n, va, vs, ra, rs in self.sections:
            if ra <= off < ra + max(vs, rs):
                return self.base + va + (off - ra)
        return None

    def va_to_off(self, va: int) -> int | None:
        rva = va - self.base
        for _n, sva, vs, ra, rs in self.sections:
            if sva <= rva < sva + max(vs, rs):
                return ra + (rva - sva)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--show-code", type=int, default=12,
                    help="instructions of context around each reference")
    args = ap.parse_args()

    pe = PE(EXE)
    needle = args.text.encode("latin1")

    hits = []
    start = 0
    while True:
        i = pe.data.find(needle, start)
        if i < 0:
            break
        va = pe.off_to_va(i)
        if va is not None:
            hits.append((i, va))
        start = i + 1

    print(f"found {len(hits)} occurrence(s) of {args.text!r}")
    for off, va in hits:
        print(f"\n  file 0x{off:x}  VA 0x{va:08x}")
        # Search for push imm32 / mov reg, imm32 with this address in .text.
        enc_int = struct.pack("<I", va)
        refs = []
        s = 0
        text = [sec for sec in pe.sections if sec[0] == ".text"][0]
        _n, _va, _vs, ra, rs = text
        while True:
            j = pe.data.find(enc_int, ra, ra + rs)
            if j < 0:
                break
            refs.append(j)
            s = j + 1
            if len(refs) > 20:
                break
        print(f"  {len(refs)} immediate reference(s) in .text")
        for r in refs[:6]:
            rva = pe.off_to_va(r)
            print(f"    at file 0x{r:x} VA 0x{rva:08x}: "
                  f"{pe.data[r-2:r+8].hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
