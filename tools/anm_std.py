#!/usr/bin/env python3
"""TH07 ANM opcode formats and TH07 .std container structure.

Two facts this module encodes, both verified against the shipped data:

1. ANM parameters.  thtk's `formats_v2` (used for TH07, version 2) gives the
   parameter format per opcode.  Critically the `S` field is **4 bytes**, not
   the 2 bytes its name suggests: with S=2, 21 of 39 observed opcodes disagree
   with the measured instruction length; with S=4 all 39 match exactly.

2. .std layout.  A stage definition is

       u16 unknown, u16 count, u32 offsetA, u32 offsetB
       [region A]  fixed 16-byte records until 0xffffffff
       [region B]  a second block (structure not fully decoded)

   Region A records are `u16 tag, u16 pad, f32 f0, f32 f1, f32 f2`.  In
   stage1 the f1 values step down by exactly 256 (6600, 6344, 6088, ...) with
   f0 pinned at -192, which is the signature of object placement along the
   stage.

Usage:
    python tools/anm_std.py formats        # opcode format/size table
    python tools/anm_std.py std            # dump every stage .std
"""
from __future__ import annotations

import glob
import struct
import sys

# thtk thanm.c formats_v2 -- TH07 uses version 2.
FORMATS_V2 = {
    0: "", 1: "", 2: "", 3: "n", 4: "ot", 5: "Sot", 6: "fff", 7: "ff",
    8: "S", 9: "S", 10: "", 11: "", 12: "fff", 13: "fff", 14: "ff",
    15: "SS", 16: "S", 17: "fffS", 18: "fffS", 19: "fffS", 20: "", 21: "S",
    22: "", 23: "", 24: "S", 25: "S", 26: "f", 27: "f", 28: "S", 29: "ffS",
    30: "S", 31: "S", 32: "SSfff", 33: "SSS", 34: "SSS", 35: "SSfff",
    36: "SSff", 37: "SS", 38: "ff", 39: "SS", 40: "ff", 41: "SS", 42: "ff",
    43: "SS", 44: "ff", 45: "SS", 46: "ff", 47: "SS", 48: "ff", 49: "SSS",
    50: "fff", 51: "SSS", 52: "fff", 53: "SSS", 54: "fff", 55: "SSS",
    56: "fff", 57: "SSS", 58: "fff",
}

# Byte width of each format character in ANM (S is 4, unlike ECL's int16).
FIELD_SIZE = {"n": 4, "f": 4, "S": 4, "o": 4, "t": 4}

STD_HEADER = struct.Struct("<HHII")
STD_RECORD = struct.Struct("<HHfff")
STD_TERMINATOR = b"\xff\xff\xff\xff"


def fmt_size(fmt: str) -> int:
    return sum(FIELD_SIZE[c] for c in fmt)


def check_formats(measured: dict[int, int]) -> int:
    """Compare predicted instruction payload sizes against measured ones."""
    bad = 0
    print(f"{'op':>4} {'fmt':<8} {'pred':>5} {'meas':>5}  result")
    print("-" * 40)
    for op, meas in sorted(measured.items()):
        fmt = FORMATS_V2.get(op)
        if fmt is None:
            print(f"{op:>4} {'?':<8} {'-':>5} {meas:>5}  no format")
            bad += 1
            continue
        pred = fmt_size(fmt)
        ok = pred == meas
        bad += 0 if ok else 1
        print(f"{op:>4} {fmt:<8} {pred:>5} {meas:>5}  "
              f"{'OK' if ok else 'MISMATCH'}")
    print(f"\n{bad} mismatch(es)")
    return bad


def measured_sizes() -> dict[int, int]:
    """Payload sizes observed across all 63 ANM files."""
    import os
    sys.path.insert(0, "tools")
    from anm_parse import AnmFile
    from anm_script import scripts_of

    sizes: dict[int, dict[int, int]] = {}
    for path in sorted(glob.glob("work/th07_dat/*.anm")):
        anm = AnmFile(path)
        for ei in range(len(anm.entries)):
            for _sid, insns in scripts_of(anm, ei):
                for _o, typ, _t, _p, data in insns:
                    if typ == 0xFFFF or typ < 0:
                        continue
                    sizes.setdefault(typ, {})
                    sizes[typ][len(data)] = sizes[typ].get(len(data), 0) + 1
    out = {}
    for op, lens in sizes.items():
        if len(lens) > 1:
            print(f"  note: op{op} has variable payload lengths {sorted(lens)}",
                  file=sys.stderr)
        out[op] = max(lens)     # widest observed
    return out


class StdFile:
    """A TH07 .std stage definition."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            self.raw = f.read()
        self.path = path
        (self.unknown, self.count,
         self.off_a, self.off_b) = STD_HEADER.unpack_from(self.raw, 0)
        self.region_a = self.raw[self.off_a:self.off_b]
        self.region_b = self.raw[self.off_b:]
        self.records = self._parse_a()

    def _parse_a(self) -> list[tuple[int, float, float, float]]:
        out = []
        off = 0
        while off + STD_RECORD.size <= len(self.region_a):
            if self.region_a[off:off + 4] == STD_TERMINATOR:
                break
            tag, _pad, f0, f1, f2 = STD_RECORD.unpack_from(self.region_a, off)
            out.append((tag, f0, f1, f2))
            off += STD_RECORD.size
        return out

    def bounds(self):
        """Infer the stage extent from the placement records."""
        if not self.records:
            return None
        f1 = [r[2] for r in self.records]
        f0 = [r[1] for r in self.records]
        return (min(f0), max(f0), min(f1), max(f1))


def dump_std() -> int:
    print(f"{'file':<14}{'u':>10}{'offA':>7}{'offB':>7}{'recs':>6}"
          f"{'B':>7}  f0 range          f1 range")
    print("-" * 92)
    for path in sorted(glob.glob("work/th07_dat/*.std")):
        s = StdFile(path)
        b = s.bounds()
        name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        rng0 = f"{b[0]:.0f}..{b[1]:.0f}" if b else "-"
        rng1 = f"{b[2]:.0f}..{b[3]:.0f}" if b else "-"
        print(f"{name:<14}{s.unknown:>4},{s.count:<5}{s.off_a:>7}{s.off_b:>7}"
              f"{len(s.records):>6}{len(s.region_b):>7}  {rng0:<17} {rng1}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "formats"
    if cmd == "formats":
        return 1 if check_formats(measured_sizes()) else 0
    if cmd == "std":
        return dump_std()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
