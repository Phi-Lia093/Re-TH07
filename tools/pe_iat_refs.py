#!/usr/bin/env python3
"""Find code that calls an imported function, by its IAT address.

Because th07 imports only Direct3DCreate8 from d3d8.dll and talks to COM via
vtables, the only reliable anchor is the IAT slot: code that calls an import
does `call dword ptr [0xIAT]` (FF 15 imm32) or `mov reg, [0xIAT]`.

This reports every such site so the renderer's entry points can be located
from the top down, instead of pattern-guessing vtable slots.

Usage:
    python tools/pe_iat_refs.py 0x48d25c
    python tools/pe_iat_refs.py Direct3DCreate8
"""
from __future__ import annotations

import argparse
import struct
import sys

sys.path.insert(0, "tools")

from pe_imports import PE  # noqa: E402

EXE = "th07.exe"


def find_iat(name: str) -> int | None:
    pe = PE(EXE)
    for dll, funcs in pe.imports().items():
        for fname, iat in funcs:
            if fname.lower() == name.lower():
                return iat
    return None


def refs_to(iat: int) -> list[tuple[int, bytes]]:
    pe = PE(EXE)
    start = end = 0
    for n, _va, vs, ra, rs in pe.sections:
        if n == ".text":
            start, end = ra, ra + rs
            break
    enc = struct.pack("<I", iat)
    out = []
    s = start
    while True:
        j = pe.data.find(enc, s, end)
        if j < 0:
            break
        # show a little context; classify the opcode that precedes it
        ctx = pe.data[max(0, j - 2):j + 8]
        out.append((pe.va(j - 2), ctx))
        s = j + 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="IAT address (0x...) or imported function name")
    args = ap.parse_args()

    if args.target.lower().startswith("0x"):
        iat = int(args.target, 16)
        name = "?"
    else:
        iat = find_iat(args.target)
        name = args.target
        if iat is None:
            print(f"{name}: not found in the import table", file=sys.stderr)
            return 1

    print(f"{name}: IAT 0x{iat:08x}")
    sites = refs_to(iat)
    print(f"{len(sites)} reference(s) in .text")
    for va, ctx in sites:
        # FF 15 xx xx xx xx  = call dword ptr [imm32]
        if ctx[0] == 0xFF and ctx[1] == 0x15:
            kind = "call [IAT]"
        elif ctx[0] == 0xA1:
            kind = "mov eax,[IAT]"
        elif ctx[0] == 0x8B and (ctx[1] & 0x38) == 0x00:
            kind = "mov reg,[IAT]"
        else:
            kind = "?"
        print(f"  0x{va:08x}  {kind:<14} {ctx.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
