#!/usr/bin/env python3
"""Read static pointer tables out of th07.exe and map VA -> file offset.

Used to recover tables that Ghidra leaves as opaque data, notably:
  PTR_FUN_0049f158  (0x0049f158)  - ECL "hardcoded function" dispatch table
  PTR_FUN_0049f3ec  (0x0049f3ec)  - per-instance interpolation/easing functions

Usage:
    python tools/pe_tables.py                 # dump both tables
    python tools/pe_tables.py 0x49f3ec 16     # dump N entries from a VA
"""
from __future__ import annotations

import struct
import sys

EXE = "th07.exe"


class PE:
    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            self.data = f.read()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        self.n_sections = struct.unpack_from("<H", self.data, pe + 6)[0]
        opt = pe + 24
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        self.sections = []
        sec = opt + struct.unpack_from("<H", self.data, pe + 20)[0]
        for i in range(self.n_sections):
            off = sec + i * 40
            name = self.data[off : off + 8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((name, vaddr, vsize, raddr, rsize))

    def va_to_off(self, va: int) -> int:
        rva = va - self.image_base
        for name, vaddr, vsize, raddr, rsize in self.sections:
            size = max(vsize, rsize)
            if vaddr <= rva < vaddr + size:
                return raddr + (rva - vaddr)
        raise ValueError(f"VA 0x{va:08x} not in any section")

    def u32(self, va: int) -> int:
        return struct.unpack_from("<I", self.data, self.va_to_off(va))[0]

    def ptrs(self, va: int, count: int) -> list[int]:
        return [self.u32(va + 4 * i) for i in range(count)]


def main() -> int:
    pe = PE(EXE)
    print(f"image base 0x{pe.image_base:08x}, {len(pe.sections)} sections")
    for name, vaddr, vsize, raddr, rsize in pe.sections:
        print(f"  {name:<8} VA 0x{pe.image_base + vaddr:08x} vsize 0x{vsize:x} "
              f"rawoff 0x{raddr:x} rawsize 0x{rsize:x}")

    if len(sys.argv) >= 3:
        va = int(sys.argv[1], 0)
        n = int(sys.argv[2], 0)
        print(f"\ntable @0x{va:08x}, {n} entries")
        for i, p in enumerate(pe.ptrs(va, n)):
            print(f"  [{i:>3}] 0x{p:08x}")
        return 0

    for label, va, n in (
        ("PTR_FUN_0049f158 (hardcoded funcs)", 0x0049F158, 64),
        ("PTR_FUN_0049f3ec (interpolation)", 0x0049F3EC, 32),
    ):
        print(f"\n=== {label} ===")
        for i, p in enumerate(pe.ptrs(va, n)):
            # stop when the table stops pointing into the code section
            try:
                pe.va_to_off(p)
                valid = p != 0
            except ValueError:
                valid = False
            print(f"  [{i:>3}] 0x{p:08x}{'' if valid else '   (not a valid VA)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
