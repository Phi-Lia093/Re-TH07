#!/usr/bin/env python3
"""Analyse th07's D3D8 renderer entry points.

TH07 imports a single D3D8 symbol (Direct3DCreate8) and drives the device
through COM vtables.  Rather than guessing at `FF 50 kk` patterns (which
matched 539 unrelated register-indirect calls and reported zero
SetRenderState calls, i.e. nonsense), this pins the renderer down structurally:

  1. locate the Direct3DCreate8 thunk,
  2. find its callers -> the renderer's init function,
  3. in that function, the CreateDevice call receives a D3DPRESENT_PARAMETERS
     whose fields fix the back buffer size, format and swap behaviour,
  4. report the present parameters so the remake can mirror the exact
     projection/backbuffer setup.

Usage:
    python tools/d3d8_renderer.py
"""
from __future__ import annotations

import struct
import sys

sys.path.insert(0, "tools")

from pe_imports import PE  # noqa: E402

EXE = "th07.exe"

# D3DFORMAT values seen in TH07-era code.
D3DFMT = {
    0: "UNKNOWN", 21: "A8R8G8B8", 22: "X8R8G8B8", 23: "R8G8B8",
    24: "X1R5G5B5", 25: "A1R5G5B5", 26: "R5G6B5", 28: "A4R4G4B4",
    32: "X4R4G4B4", 33: "A8B8G8R8", 41: "D16", 75: "D24S8", 80: "D32",
}

# D3DSWAPEFFECT
D3DSWAPEFFECT = {0: "DISCARD", 1: "COPY", 2: "FLIP", 3: "COPY_VSYNC"}


def find_thunk(pe: PE, iat: int) -> int | None:
    """FF 25 xx xx xx xx -> jmp dword ptr [iat]."""
    enc = struct.pack("<I", iat)
    for name, _va, vs, ra, rs in pe.sections:
        if name != ".text":
            continue
        s = ra
        end = ra + rs
        while True:
            j = pe.data.find(b"\xff\x25" + enc, s, end)
            if j < 0:
                break
            return pe.va(j)
    return None


def code_va_refs(pe: PE, target_va: int) -> list[tuple[int, bytes]]:
    """Find `call rel32` / `call [mem]` that target the thunk."""
    out = []
    for name, _va, vs, ra, rs in pe.sections:
        if name != ".text":
            continue
        s = ra
        end = ra + rs
        while True:
            j = pe.data.find(b"\xe8", s, end)   # call rel32
            if j < 0:
                break
            rel = struct.unpack_from("<i", pe.data, j + 1)[0]
            here = pe.va(j)
            if here and here + 5 + rel == target_va:
                out.append((here, pe.data[j:j + 5]))
            s = j + 1
        # also `FF 15 imm32` (call [mem]) with the address being a pointer to thunk
    return out


def scan_present_params(pe: PE) -> None:
    """Report D3DPRESENT_PARAMETERS-shaped constants pushed near D3D init."""
    print("\nD3DFORMAT / SWAPEFFECT constants present in .text:")
    found = {"fmt": {}, "swap": {}}
    for name, _va, vs, ra, rs in pe.sections:
        if name != ".text":
            continue
        i = ra
        end = ra + rs
        while i < end - 5:
            if pe.data[i] == 0x68:              # push imm32
                v = struct.unpack_from("<I", pe.data, i + 1)[0]
                if v in D3DFMT:
                    found["fmt"][v] = found["fmt"].get(v, 0) + 1
                elif v in D3DSWAPEFFECT:
                    found["swap"][v] = found["swap"].get(v, 0) + 1
                i += 5
                continue
            i += 1
    for v, c in sorted(found["fmt"].items()):
        print(f"  push {v:>3} = D3DFMT_{D3DFMT[v]:<10} x{c}")
    for v, c in sorted(found["swap"].items()):
        print(f"  push {v:>3} = D3DSWAPEFFECT_{D3DSWAPEFFECT[v]:<10} x{c}")


def main() -> int:
    pe = PE(EXE)
    iat = None
    for dll, funcs in pe.imports().items():
        for fname, a in funcs:
            if fname == "Direct3DCreate8":
                iat = a
    if iat is None:
        print("Direct3DCreate8 not imported", file=sys.stderr)
        return 1

    print(f"Direct3DCreate8 IAT: 0x{iat:08x}")
    thunk = find_thunk(pe, iat)
    print(f"thunk: 0x{thunk:08x}" if thunk else "thunk: not found")

    if thunk:
        callers = code_va_refs(pe, thunk)
        print(f"callers of the thunk: {len(callers)}")
        for va, raw in callers:
            print(f"  0x{va:08x}  {raw.hex(' ')}")

    scan_present_params(pe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
