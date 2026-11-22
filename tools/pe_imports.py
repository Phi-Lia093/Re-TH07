#!/usr/bin/env python3
"""Resolve th07.exe's d3d8.dll imports and find where the device is used.

The previous approach (guessing `FF 50 kk` = vtable dispatch) produced
nonsense: it reported zero SetRenderState/SetTexture calls while claiming 106
Release calls, because `FF 5x` also matches non-vtable register-indirect
calls.  The reliable route is the PE import table: it tells us exactly which
D3D8 entry points exist and their IAT slots, and code calling them appears as
`call [IAT_slot]`.

Two things matter for the remake:
  1. Direct3DCreate8 is called once; its return value is the IDirect3D8
     interface, and CreateDevice returns IDirect3DDevice8.
  2. The device vtable is then used with `call [reg + 4*slot]`, where slot
     numbering follows d3d8.h.  To map slots safely we anchor on the device
     pointer obtained from CreateDevice rather than on raw opcode patterns.

Usage:
    python tools/pe_imports.py d3d8.dll
    python tools/pe_imports.py            # list all imported DLLs
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
        self.n = struct.unpack_from("<H", self.data, pe + 6)[0]
        opt = pe + 24
        magic = struct.unpack_from("<H", self.data, opt)[0]
        self.base = struct.unpack_from("<I", self.data, opt + 28)[0]
        # data directories: PE32 has 96-byte optional header with 16 dirs at 96
        dd = opt + (96 if magic == 0x10B else 112)
        self.import_rva, self.import_size = struct.unpack_from("<II", self.data, dd + 8)
        self.sections = []
        sec = opt + struct.unpack_from("<H", self.data, pe + 20)[0]
        for i in range(self.n):
            off = sec + i * 40
            name = self.data[off:off + 8].rstrip(b"\0").decode("latin1")
            vs, va, rs, ra = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((name, va, vs, ra, rs))

    def rva_to_off(self, rva: int) -> int | None:
        for _n, va, vs, ra, rs in self.sections:
            if va <= rva < va + max(vs, rs):
                return ra + (rva - va)
        return None

    def cstr(self, rva: int) -> str:
        off = self.rva_to_off(rva)
        if off is None:
            return "?"
        end = self.data.find(b"\0", off)
        return self.data[off:end].decode("latin1", "replace")

    def va(self, file_off: int) -> int:
        """Convert a file offset to a virtual address."""
        for _n, va, vs, ra, rs in self.sections:
            if ra <= file_off < ra + max(vs, rs):
                return self.base + va + (file_off - ra)
        return 0

    def imports(self) -> dict[str, list[tuple[str, int]]]:
        """Map DLL -> [(function name, IAT VA)]."""
        out: dict[str, list[tuple[str, int]]] = {}
        off = self.rva_to_off(self.import_rva)
        if off is None:
            return out
        while True:
            ilt, _ts, _fwd, name_rva, iat = struct.unpack_from("<5I", self.data, off)
            if name_rva == 0:
                break
            dll = self.cstr(name_rva)
            funcs = []
            t = self.rva_to_off(ilt or iat)
            slot = 0
            while t is not None:
                ent = struct.unpack_from("<I", self.data, t + slot * 4)[0]
                if ent == 0:
                    break
                if ent & 0x80000000:
                    fname = f"ordinal_{ent & 0xFFFF}"
                else:
                    fname = self.cstr(ent + 2)
                funcs.append((fname, self.base + iat + slot * 4))
                slot += 1
            out[dll] = funcs
            off += 20
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dll", nargs="?", help="only show imports from this DLL")
    args = ap.parse_args()

    pe = PE(EXE)
    imps = pe.imports()
    print(f"imported DLLs: {len(imps)}")
    for dll, funcs in imps.items():
        if args.dll and args.dll.lower() not in dll.lower():
            continue
        print(f"\n=== {dll} ({len(funcs)} functions) ===")
        for name, iat in funcs:
            print(f"  0x{iat:08x}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
