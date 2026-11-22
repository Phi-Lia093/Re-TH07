#!/usr/bin/env python3
"""Extract, for every ECL opcode, the concrete side effect on the instance.

For each `case N` (= opcode N+1) list:
  - parameters (mask bit, int/float)
  - every store into a context field: `*(float *)(param_1 + 0xNNN) = ...`
  - every call to a game/engine function

Context field offsets are the canonical way to name an opcode's effect, e.g.
writing `+0x2b0c` is "set position X" and `+0x2e28` is "set movement mode".
This is the table the remade engine must implement.
"""
from __future__ import annotations

import argparse
import re
import sys

sys.path.insert(0, "tools")

from extract_opcodes import find_switch, load, param_reads, split_cases  # noqa: E402

STORE_RE = re.compile(r"\*\((?:\w+ )?\*\)\(param_1 \+ (0x[0-9a-f]+)\)\s*=\s*(.{0,50})")
FIELD_RE = re.compile(r"\(param_1 \+ (0x[0-9a-f]+)\)")
CALL_RE = re.compile(r"\b(FUN_[0-9a-f]{8})\s*\(")

# Human names for context fields seen in the interpreter.
FIELDS = {
    "0x6e4": "ip",
    "0x6f0": "instr_time",
    "0x6fc": "var10000",
    "0x70c": "var10004",
    "0x72c": "var10012",
    "0x744": "funcwide_int0",
    "0x754": "funcwide_float0",
    "0x8f0": "flag_8f0",
    "0x8f4": "flag_8f4",
    "0x2a7c": "stack_depth",
    "0x2b08": "wait",
    "0x2b0c": "pos_x",
    "0x2b10": "pos_y",
    "0x2b14": "pos_z",
    "0x2b18": "vel_x",
    "0x2b1c": "vel_y",
    "0x2b20": "vel_z",
    "0x2b54": "angle",
    "0x2b58": "angle_speed",
    "0x2b5c": "angle_53",
    "0x2b60": "angle_54",
    "0x2b64": "speed",
    "0x2b68": "speed_2",
    "0x2b6c": "dist_origin",
    "0x2b74": "offset_x",
    "0x2b78": "offset_y",
    "0x2b7c": "offset_z",
    "0x2b80": "target_off_x",
    "0x2b84": "target_off_y",
    "0x2b88": "target_off_z",
    "0x2b8c": "origin_x",
    "0x2b90": "origin_y",
    "0x2b94": "origin_z",
    "0x2ba8": "accel_min",
    "0x2bac": "accel_max",
    "0x2bb2": "shots_min",
    "0x2bb6": "shots_max",
    "0x2bb8": "life",
    "0x2bc0": "field_2bc0",
    "0x2bc4": "timer_2bc4",
    "0x2bc8": "counter_2bc8",
    "0x2bcc": "time_2bcc",
    "0x2d8c": "player_array",
    "0x2e10": "field_2e10",
    "0x2e17": "flag_2e17",
    "0x2e28": "move_mode",
    "0x2e29": "flags_2e29",
    "0x2e2a": "flags_2e2a",
    "0x2e2b": "flags_2e2b",
    "0x2e4c": "field_2e4c",
    "0x2ebc": "field_2ebc",
    "0x2ec0": "field_2ec0",
    "0x2ec4": "field_2ec4",
    "0x2ec8": "field_2ec8",
    "0x2ecc": "field_2ecc",
    "0x2edc": "field_2edc",
    "0x2ee4": "timer_2ee4",
    "0x2f58": "timer_end_2f58",
    "0x2f5c": "timer_2f5c",
}

# Engine functions that dominate the opcode surface.
CALLS = {
    "FUN_0040e5b0": "read_var_i",
    "FUN_0040edf0": "read_var_f",
    "FUN_0040ec00": "addr_var_i",
    "FUN_0040f3c0": "addr_var_f",
    "FUN_004203b0": "",
    "FUN_00424d20": "spawn_bullets",
    "FUN_00424e00": "spawn_laser",
    "FUN_0041f430": "spawn_child_ecl",
    "FUN_00423090": "spawn_effect?",
    "FUN_0044ea20": "anm_ctl",
    "FUN_0041c1c0": "effect_create",
    "FUN_0041c400": "effect_create_f",
    "FUN_004326f0": "spawn_item",
    "FUN_00424740": "",
    "FUN_0042f5a2": "add_score",
    "FUN_00455170": "",
    "FUN_00424c00": "",
    "FUN_00439401": "frame_skip",
    "FUN_00431900": "rnd01",
    "FUN_00431930": "norm_angle",
    "FUN_004318d0": "rng32",
    "FUN_00442370": "atan2_to",
    "FUN_0048bb40": "fsin",
    "FUN_0048bbf0": "fcos",
    "FUN_0048bcaa": "fpatan",
    "FUN_0048b8a0": "ftol",
    "FUN_0040f6b0": "",
    "FUN_0040f8f0": "",
    "FUN_0041f670": "",
    "FUN_0044c930": "",
    "FUN_0045e4f0": "log",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", nargs="?", default="th07.exe.c")
    ap.add_argument("--from", dest="lo", type=int, default=1)
    ap.add_argument("--to", dest="hi", type=int, default=161)
    args = ap.parse_args()

    lines = load(args.export)
    sw, end = find_switch(lines)
    cases = split_cases(lines, sw, end)

    for op in range(args.lo, args.hi + 1):
        idx = op - 1
        if idx not in cases:
            print(f"{op:>3}  (no case)")
            continue
        body = cases[idx]
        reads = param_reads(body)
        fields = []
        for line in body:
            m = STORE_RE.search(line)
            if m:
                off = m.group(1).lower()
                if off == "0x2e28":
                    fields.append("move_mode(set)")
                else:
                    fields.append(FIELDS.get(off, off))
        calls = [CALLS.get(c, c) for c in dict.fromkeys(CALL_RE.findall("\n".join(body)))]
        calls = [c for c in calls if c]
        ptypes = "".join(("f" if "f32" in t else "i") for _b, t, _s in reads)
        print(f"{op:>3}  [{ptypes:<8}] -> {','.join(dict.fromkeys(fields)) or '-':<40} {','.join(calls)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
