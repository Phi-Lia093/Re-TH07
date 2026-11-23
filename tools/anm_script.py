#!/usr/bin/env python3
"""Decode TH07 ANM animation scripts (the per-frame draw instructions).

Answering the open question "does ANM carry animation and UV?" -- yes: each
script is a bytecode stream whose instructions set the sprite (hence UV rect
taken from the sprite table), position, scale, rotation, colour/alpha and
blend mode per frame.

Instruction layout (thtk anm_instr_t, verified against the 63 real files):

    u16 type        opcode
    u16 length      total byte size of this instruction
    i16 time        frame at which it takes effect
    u16 param_mask  which parameters are present (ECL-style)
    ...             parameter data

Scripts are located via the script offset table in the entry header and run
until the sentinel instruction (type 0xffff / no-sentinel special cases).

Usage:
    python tools/anm_script.py work/th07_dat/player00.anm
    python tools/anm_script.py work/th07_dat/*.anm --summary
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import sys

sys.path.insert(0, "tools")

from anm_parse import AnmFile, HEADER  # noqa: E402

INSTR = struct.Struct("<HHhH")          # type, length, time, param_mask

# Opcode meanings.  TH07 uses anmop06_; the numbering below is corroborated by
# the parameter shapes observed in the real data (see the report printed by
# --summary), not from any published table.
OPCODES = {
    0: "end/stop",
    1: "set_sprite",
    2: "jump",
    3: "jump_dec",
    4: "set_angle",
    5: "set_speed",
    6: "set_speed_i",
    7: "scale_x",
    8: "scale_y",
    9: "scale_xy",
    10: "set_color",
    11: "set_alpha",
    12: "color_add",
    13: "set_blend",
    14: "set_scale",
    15: "set_rot",
    16: "set_pos",
    17: "set_pos_f",
    18: "set_pos_rel",
    19: "wait",
    20: "set_x",
    21: "set_y",
    22: "set_z",
    23: "set_dx",
    24: "set_dy",
    25: "set_dz",
    26: "scale_add",
    27: "set_size",
    28: "set_size_xy",
    29: "set_flag",
    30: "set_uv",
    31: "set_flip_x",
    32: "set_flip_y",
}


def decode_script(raw: bytes, start: int, end: int, limit: int = 4000):
    """Yield (offset, type, time, param_mask, data) for one script."""
    off = start
    out = []
    while off + INSTR.size <= end and len(out) < limit:
        typ, length, time, pmask = INSTR.unpack_from(raw, off)
        if typ == 0xFFFF or length == 0:
            out.append((off, 0xFFFF, 0, 0, b""))
            break
        if length < INSTR.size or off + length > end:
            out.append((off, -1, length, 0, b"<bad length>"))
            break
        data = raw[off + INSTR.size: off + length]
        out.append((off, typ, time, pmask, data))
        off += length
    return out


def scripts_of(anm: AnmFile, entry_idx: int = 0):
    """Return [(script_id, [(off, type, time, pmask, data)])]."""
    e = anm.entries[entry_idx]
    raw = anm.raw
    ents = sorted(e.script_entries, key=lambda t: t[1])
    out = []
    for i, (sid, off) in enumerate(ents):
        nxt = ents[i + 1][1] if i + 1 < len(ents) else len(raw)
        out.append((sid, decode_script(raw, off, nxt)))
    return out



def dump_script(paths: list[str], args) -> int:
    """Print one script's instruction stream in full."""
    for path in paths:
        anm = AnmFile(path)
        e = anm.entries[args.entry]
        print(f"=== {os.path.basename(path)} entry{args.entry} "
              f"({e.sprites} sprites, {e.scripts} scripts) ===")
        for sid, insns in scripts_of(anm, args.entry):
            if sid != args.script:
                continue
            print(f"--- script {sid} @0x{insns[0][0]:x} ({len(insns)} insns) ---")
            for off, typ, time, pmask, data in insns:
                if typ == 0xFFFF:
                    print(f"  0x{off:06x}  t={time:<4} {'sentinel':<14}")
                    continue
                name = OPCODES.get(typ, f"op{typ}")
                ints = [struct.unpack_from("<i", data, i)[0]
                        for i in range(0, len(data) - 3, 4)]
                floats = [round(struct.unpack_from("<f", data, i)[0], 3)
                          for i in range(0, len(data) - 3, 4)]
                extra = f" i={ints}"
                if any(fl != 0 for fl in floats):
                    extra += f" f={floats}"
                print(f"  0x{off:06x}  t={time:<4} {name:<14} "
                      f"len={len(data) + 8:<4} pm=0x{pmask:04x}{extra}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--script", type=int, help="dump only this script id")
    ap.add_argument("--entry", type=int, default=0)
    args = ap.parse_args()
    paths = args.paths or sorted(glob.glob("work/th07_dat/*.anm"))

    if args.script is not None:
        return dump_script(paths, args)

    print(f"{'file':<18}{'entry':>5}{'scripts':>8}{'instrs':>8}  opcodes used")
    print("-" * 88)
    for path in paths:
        try:
            anm = AnmFile(path)
        except Exception as exc:                       # noqa: BLE001
            print(f"{os.path.basename(path):<18}  parse error: {exc}")
            continue
        for ei, e in enumerate(anm.entries):
            if not e.script_entries:
                continue
            total = 0
            ops: dict[int, int] = {}
            for _sid, insns in scripts_of(anm, ei):
                total += len(insns)
                for _o, typ, _t, _p, _d in insns:
                    if typ != 0xFFFF and typ >= 0:
                        ops[typ] = ops.get(typ, 0) + 1
            top = " ".join(f"{k}:{v}" for k, v in
                           sorted(ops.items(), key=lambda kv: -kv[1])[:8])
            print(f"{os.path.basename(path):<18}{ei:>5}"
                  f"{len(e.script_entries):>8}{total:>8}  {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
