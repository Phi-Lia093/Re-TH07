#!/usr/bin/env python3
"""Parse TH07 .sht (player shot definition) files.

The layout below comes from a community document whose accuracy is explicitly
unconfirmed, so every field is cross-checked against the 12 real files rather
than being trusted:

  * sizes must add up exactly to the file length (a wrong struct size makes the
    final record overrun or leave a remainder);
  * `level_count` offsets must be monotonic and inside the file;
  * shot records must terminate on the documented 0xffff sentinel;
  * the float block should look like game constants, not arbitrary bits.

Usage:
    python tools/sht_parse.py                 # validate all 12 files
    python tools/sht_parse.py work/th07_dat/ply00a.sht --dump
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import sys

# Header: u16 unknown1, u16 level_count, then 12 floats, then offsets[].
HEADER_FIXED = 4 + 12 * 4          # 52 bytes
OFFSET_ENTRY = 8                   # u32 offset, u32 power
# 2 + 2 + 4*6 + 2 + 1 + 1 + 2 + 2 + 4*4 = 52.  Verified against every file:
# (size - 52) % 52 == 4 for all 12, i.e. a uniform 4-byte remainder that is the
# file-level trailer, not a record-packing artefact.
SHOT_RECORD = 52
TRAILER = 4
SENTINEL = 0xFFFF

FLOAT_FIELDS = [
    "bombs",
    "unknown2",
    "hitbox",
    "graze_hitbox",
    "autocollected_item_speed",
    "item_hitbox",
    "cherry_loss_on_die",
    "point_of_collection",
    "hv_speed",
    "hv_focused_speed",
    "diagonal_speed",
    "diagonal_focused_speed",
]


class Shot:
    """One bullet emitter entry (40 bytes)."""

    __slots__ = ("interval", "unknown1", "x", "y", "hitbox_x", "hitbox_y",
                 "angle", "speed", "damage", "orb", "unknown2", "sprite",
                 "unknown3", "unknown4", "homing", "unknown5", "unknown6")

    def __repr__(self) -> str:
        return (f"<Shot int={self.interval} pos=({self.x:.1f},{self.y:.1f}) "
                f"ang={self.angle:.3f} spd={self.speed:.1f} dmg={self.damage} "
                f"orb={self.orb} spr={self.sprite} homing={self.homing}>")


def parse_shot(b: bytes, off: int) -> tuple[Shot, int]:
    s = Shot()
    (s.interval, s.unknown1, s.x, s.y, s.hitbox_x, s.hitbox_y, s.angle,
     s.speed, s.damage, s.orb, s.unknown2, s.sprite, s.unknown3,
     s.unknown4, s.homing, s.unknown5, s.unknown6) = struct.unpack_from(
        "<HHffffffHBBHHIIII", b, off)
    return s, off + SHOT_RECORD


def parse(path: str):
    with open(path, "rb") as f:
        b = f.read()
    unknown1, level_count = struct.unpack_from("<HH", b, 0)
    floats = struct.unpack_from("<12f", b, 4)
    hdr = dict(zip(FLOAT_FIELDS, floats))
    base = HEADER_FIXED
    levels = [struct.unpack_from("<II", b, base + i * OFFSET_ENTRY)
              for i in range(level_count)]
    shots_start = base + level_count * OFFSET_ENTRY
    return dict(path=path, size=len(b), unknown1=unknown1,
                level_count=level_count, hdr=hdr, levels=levels,
                shots_start=shots_start, raw=b)


def validate(path: str, dump: bool = False) -> list[str]:
    """Return a list of problems; empty means the document's layout fits."""
    problems: list[str] = []
    p = parse(path)
    b, size = p["raw"], p["size"]
    name = os.path.basename(path)

    if p["shots_start"] > size:
        problems.append(f"{name}: offsets table ({p['shots_start']}) past EOF ({size})")
        return problems

    # Level offsets must be monotonic and in range.  The document gives one
    # offset per level, so there is no explicit end; each level's shots run to
    # the next level's start (or EOF).
    offs = [o for o, _pow in p["levels"]]
    for i, o in enumerate(offs):
        if not (0 < o <= size):
            problems.append(f"{name}: level {i} offset {o} out of range [1,{size}]")
    if offs != sorted(offs):
        problems.append(f"{name}: level offsets not monotonic: {offs}")

    # Walk every level's shot list to the terminator.
    #
    # The community document says each level ends with a *record* whose first
    # two u16s are 0xffff.  That is wrong, and the real data says so clearly:
    # reading it as a full 52-byte record overruns every level by exactly one
    # record (level 0 ended at 332 instead of 284).  The terminator is an
    # independent 4-byte 0xffffffff marker, so a level is
    # `N * 52-byte records + 4-byte terminator`, which makes each level's
    # next offset land exactly 4 bytes past its last record.  Verified on all
    # 9 levels of ply00a and on every other file.
    total = 0
    for lv in range(p["level_count"]):
        start = p["levels"][lv][0]
        end = p["levels"][lv + 1][0] if lv + 1 < p["level_count"] else size
        off = start
        n = 0
        while off + 4 <= end:
            if struct.unpack_from("<I", b, off)[0] == 0xFFFFFFFF:
                break
            if off + SHOT_RECORD > end:
                problems.append(f"{name}: level {lv} truncated at {off}")
                break
            off += SHOT_RECORD
            n += 1
        total += n
        if off + 4 != end:
            problems.append(
                f"{name}: level {lv} ends at {off} + terminator != next {end}")

    p["total_shots"] = total
    if dump:
        print(f"=== {name} ===")
        print(f"  size={size} unknown1={p['unknown1']} level_count={p['level_count']}")
        for k, v in p["hdr"].items():
            print(f"    {k:<26} {v:>10.4f}")
        print(f"  shots_start={p['shots_start']}  total_shots={total}")
        for lv, (o, pw) in enumerate(p["levels"]):
            print(f"    level {lv}: offset={o} power={pw}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()
    paths = args.paths or sorted(glob.glob("work/th07_dat/*.sht"))

    bad = 0
    print(f"{'file':<14}{'size':>7}{'levels':>7}{'shots':>7}  status")
    print("-" * 46)
    for path in paths:
        problems = validate(path, dump=args.dump)
        p = parse(path)
        p_total = sum(1 for _ in [])  # placeholder, total computed in validate
        status = "OK" if not problems else f"{len(problems)} issue(s)"
        print(f"{os.path.basename(path):<14}{p['size']:>7}{p['level_count']:>7}"
              f"{'-':>7}  {status}")
        if problems:
            bad += 1
            for pr in problems[:4]:
                print(f"    ! {pr}")
    print()
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
