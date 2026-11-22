#!/usr/bin/env python3
"""Extract per-opcode semantics from the Ghidra C export of th07.exe.

The ECL interpreter is FUN_00410520 (docs/02-ecl-instructions.md).  Its
dispatch is:

    if (*(int *)(ctx + 0x6f0) != *ip) goto LAB_0041678f;   // not this frame
    if ((*(byte *)((int)ip + 9) & _DAT_00626284) == 0) goto caseD_7e;  // rank skip
    iVar14 = (short)ip[1] + -1;                            // opcode - 1
    switch (iVar14) { case 0: return -1; case 1: ... }

so **case N handles opcode N+1** and opcode 0 means "stop this sub".

This script chops the switch into one block per case and reports, for each
opcode, which parameters are read and how, plus the side-effect summary.
"""
from __future__ import annotations

import argparse
import re
import sys

INTERP_START = "undefined4 FUN_00410520(int param_1)"
SWITCH_ANCHOR = "switch(iVar14) {"

# The interpreter computes `iVar14 = (short)ip[1] - 1` where ip[1] is the
# opcode, then `switch (iVar14)`.  Therefore:
#   opcode 0        -> iVar14 == -1, no case matches, falls through to
#                      caseD_7e (skip) == "nop", matching the reference table.
#   opcode N (N>=1) -> case N-1
# The highest case is 0xa0 (160) and it has no `break`, so it falls through to
# caseD_7e as well; valid opcodes are 0..161.
CASE_TO_OPCODE = 1
MAX_CASE = 0xA0
CASE_RE = re.compile(r"^\s*case (0x[0-9a-fA-F]+|\d+):\s*$")
PARAM_RE = re.compile(r"\((long long|int)\s*\*\)\s*local_c\[(\d+)\]")
MASKVAL_RE = re.compile(r"\+ 10\)\s*&\s*(0x[0-9a-fA-F]+|\d+)\)")
GOTO_RE = re.compile(r"goto (switchD_0041073a_caseD_\w+|LAB_\w+);")
# `(*(byte *)(local_c + 3) & 1)` reads the low byte of slot 3.
BYTE_SLOT_RE = re.compile(r"\(\*\((?:byte|ushort|short|char) \*\)\(local_c \+ (\d+)\)")
# A case body that hands the instruction pointer to a helper, which then reads
# the slots itself as `*(T *)(instr + 0xNN)`.
DELEGATE_RE = re.compile(r"(FUN_[0-9a-f]{8})\s*\(\s*[^;]*?\b(?:param_1|local_c)\b")
HELPER_FIELD_RE = re.compile(r"\(\s*param_2\s*\+ (0x[0-9a-f]+|\d+)\s*\)")
# A case may alias the first parameter slot: `local_1c = local_c + 3;` after
# which `local_1c[k]` is slot 3+k.
SLOT_ALIAS_RE = re.compile(r"(local_[0-9a-f]+)\s*=\s*local_c \+ (\d+);")
HELPER_FLOAT_RE = re.compile(r"\bFUN_0040edf0\b")

# helper name -> sorted slot offsets (byte offsets into the instruction) it reads
HELPER_SLOTS: dict[str, list[int]] = {}
# helper name -> True if it reads any parameter through the float accessor
HELPER_FLOAT: dict[str, bool] = {}


def register_helpers(lines: list[str]) -> None:
    """Index every function that reads instruction slots through its 2nd arg.

    Slot offsets are reported as byte offsets (`0xc`, `0x14`, ...) so the
    caller can convert with slot = off // 4 - 1.
    """
    HELPER_SLOTS.clear()
    HELPER_FLOAT.clear()
    current: str | None = None
    body: list[str] = []

    def flush() -> None:
        if not current:
            return
        offs = sorted({int(m.group(1), 0) for line in body
                       for m in HELPER_FIELD_RE.finditer(line)})
        offs = [o for o in offs if o >= 0xC]
        if offs:
            HELPER_SLOTS[current] = offs
            HELPER_FLOAT[current] = any(HELPER_FLOAT_RE.search(l) for l in body)

    for line in lines:
        m = re.match(r"^[a-zA-Z_].*\b(FUN_[0-9a-f]{8})\(.*\)\s*$", line)
        if m:
            flush()
            current = m.group(1)
            body = []
            continue
        if current:
            body.append(line)
    flush()


def float_helper(name: str) -> bool:
    return HELPER_FLOAT.get(name, False)


def load(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def find_switch(lines: list[str]) -> tuple[int, int]:
    start = next(i for i, l in enumerate(lines) if INTERP_START in l)
    sw = next(i for i in range(start, len(lines)) if SWITCH_ANCHOR in lines[i])
    depth = 0
    end = None
    for i in range(sw, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if i > sw and depth <= 0:
            end = i
            break
    if end is None:
        raise RuntimeError("could not find end of interpreter switch")
    return sw, end


def split_cases(lines: list[str], sw: int, end: int) -> dict[int, list[str]]:
    """Map case index -> body lines, resolving C fallthrough groups.

    The decompiler emits grouped labels for opcodes that share one handler::

        case 0x3f:
        case 0x40:
        case 0x41:
          <shared body>
          break;

    Only the last label owns the body; the earlier ones fall through into it.
    Naively splitting on every `case` line therefore yields empty bodies for
    all but the last label, which is what hid opcodes 64-72.  Here, a label
    with no body of its own inherits the body of the next label.
    """
    own: dict[int, list[str]] = {}
    order: list[int] = []
    current: int | None = None
    for i in range(sw + 1, end):
        line = lines[i]
        m = CASE_RE.match(line)
        if m:
            current = int(m.group(1), 0)
            own[current] = []
            order.append(current)
            continue
        if current is not None:
            own[current].append(line)

    def is_empty(body: list[str]) -> bool:
        return not any(s.strip() for s in body)

    cases: dict[int, list[str]] = dict(own)
    for pos, idx in enumerate(order):
        if not is_empty(own[idx]):
            continue
        for nxt in order[pos + 1 :]:
            if not is_empty(own[nxt]):
                cases[idx] = own[nxt]
                break
    return cases


def shared_label_bodies(lines: list[str], end: int) -> dict[str, list[str]]:
    """Body of each shared switchD_... label, for goto targets."""
    bodies: dict[str, list[str]] = {}
    labels = [(i, l.strip()[:-1]) for i, l in enumerate(lines)
              if l.startswith("switchD_0041073a_caseD_") and l.rstrip().endswith(":")]
    for idx, (line_no, name) in enumerate(labels):
        stop = labels[idx + 1][0] if idx + 1 < len(labels) else len(lines)
        bodies[name] = lines[line_no + 1 : stop]
    return bodies


def param_reads(body: list[str]) -> list[tuple[int, str, str]]:
    """Recover (bit, kind, slot) for each parameter read in a case body.

    Three idioms appear in the export:

    1. masked read (the common case)::

         if ((*(ushort *)((int)local_c + 10) & MASK) == 0) {
           local_x = local_c[SLOT];            // immediate
         } else {
           local_x = FUN_0040e5b0();           // variable (int)
         }

    2. masked single-bit store, reading the low byte of the slot::

         *(byte *)(param_1 + 0x2e29) = ... | (*(byte *)(local_c + 3) & 1) << 1;

    3. whole-instruction delegation: the case just calls a helper that takes
       the instruction pointer and reads `instr + 0xc`, `instr + 0x14`, ...
       itself.  Offsets map back to slots as slot = offset/4 - 1, so +0xc is
       slot 3 and +0x14 is slot 5.

    MASK bit 0 is the first parameter, so the bit index is the parameter
    ordinal.  The float path passes the slot index to FUN_0040edf0 rather than
    leaving it implicit, so it is handled separately.
    """
    out: dict[int, tuple[str, str]] = {}
    for i, line in enumerate(body):
        m = MASKVAL_RE.search(line)
        if not m or "== 0" not in line:
            continue
        mask = int(m.group(1), 0)
        bit = (mask & -mask).bit_length() - 1
        # Collect just this if/else: its own block, up to the closing brace
        # that ends the else.  Stopping at the first 8 lines let the *next*
        # parameter's else-branch leak in and made every read look "var".
        seg: list[str] = []
        depth = 0
        started = False
        seen_else = False
        for line2 in body[i : i + 16]:
            seg.append(line2)
            depth += line2.count("{") - line2.count("}")
            if not started and "{" in line2:
                started = True
            if started and depth <= 0:
                if not seen_else:
                    # end of the `then` block; the `else` follows
                    seen_else = True
                    continue
                break
        joined = "\n".join(seg)
        # The else-branch is what distinguishes a variable read from an
        # immediate: `local_x = FUN_0040e5b0()` / `FUN_0040edf0(slot)`.
        else_part = joined.split("else", 1)[1] if "else" in joined else ""
        is_var = "FUN_0040e5b0()" in else_part or "FUN_0040edf0(" in else_part
        is_float = "FUN_0040edf0(" in else_part or re.search(r"\(float\)local_c\[", joined) is not None
        sm = re.search(r"local_c\[(\d+)\]", joined)
        slot = sm.group(1) if sm else "?"
        kind = ("var" if is_var else "imm") + (" f32" if is_float else " i32")
        out.setdefault(bit, (kind, f"slot{slot}"))
    # Idiom 2: single-bit store reading the low byte of a slot directly.
    for line in body:
        for sm in BYTE_SLOT_RE.finditer(line):
            slot = int(sm.group(1))
            bit = slot - 3
            if bit >= 0:
                out.setdefault(bit, ("imm i32 (byte)", f"slot{slot}"))

    # Idiom 3: the case delegates the whole instruction to a helper which reads
    # the slots itself (`instr + 0xc` is slot 3, `+0x14` is slot 5, ...).
    for line in body:
        for dm in DELEGATE_RE.finditer(line):
            helper = dm.group(1)
            for off in HELPER_SLOTS.get(helper, []):
                slot = off // 4 - 1
                bit = slot - 3
                if bit >= 0:
                    kind = "var f32" if float_helper(helper) else "var i32"
                    out.setdefault(bit, (kind, f"slot{slot}"))

    # Idiom 4: the case aliases the parameter base, then indexes it.
    #   local_1c = local_c + 3;   ... local_1c[5] ...   -> slot 8
    for line in body:
        am = SLOT_ALIAS_RE.search(line)
        if not am:
            continue
        alias, base = am.group(1), int(am.group(2))
        for line2 in body:
            for im in re.finditer(re.escape(alias) + r"\[(\d+)\]", line2):
                slot = base + int(im.group(1))
                bit = slot - 3
                if bit >= 0:
                    is_f = ("(float)" + alias) in line2 or ("FUN_0040edf0(" + alias) in line2
                    # The alias resolves the slot authoritatively, so override a
                    # previously guessed "slot?" from the masked-read scan.
                    out[bit] = ("var f32" if is_f else "var i32", f"slot{slot}")

    return [(b, out[b][0], out[b][1]) for b in sorted(out)]


def summarize(cases: dict[int, list[str]], labels: dict[str, list[str]],
              version_gate: str = "version 7") -> int:
    print(f"# opcode table extracted from FUN_00410520 ({version_gate})")
    print(f"# case index -> opcode = index + 1; {len(cases)} cases\n")
    print(f"{'op':>3}  {'nargs':>5}  {'arg kinds':<34} notes")
    print("-" * 100)
    for idx in sorted(cases):
        body = cases[idx]
        op = idx + 1
        reads = param_reads(body)
        kinds = ",".join(f"{k}" for _, k, _ in reads) if reads else "-"
        note = []
        for line in body:
            g = GOTO_RE.search(line)
            if g:
                tgt = g.group(1)
                if tgt in labels:
                    lb = labels[tgt]
                    lb_reads = param_reads(lb)
                    note.append(f"-> {tgt} (args {len(lb_reads)})")
                else:
                    note.append(f"-> {tgt}")
                break
        if any("return 0xffffffff" in l for l in body):
            note.append("STOP")
        print(f"{op:>3}  {len(reads):>5}  {kinds:<34} {' '.join(note)}")
        for bit, kind, slot in reads:
            print(f"        bit{bit}: {kind} {slot}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", nargs="?", default="th07.exe.c")
    ap.add_argument("--opcode", type=int, help="dump the full body of one opcode")
    args = ap.parse_args(argv)

    lines = load(args.export)
    register_helpers(lines)
    sw, end = find_switch(lines)
    cases = split_cases(lines, sw, end)
    labels = shared_label_bodies(lines, end)

    if args.opcode is not None:
        idx = args.opcode - 1
        if idx not in cases:
            print(f"opcode {args.opcode} (case {idx}) not found in switch", file=sys.stderr)
            return 1
        print(f"--- opcode {args.opcode} (case {idx}) ---")
        for l in cases[idx]:
            print(l)
        return 0

    return summarize(cases, labels)


if __name__ == "__main__":
    sys.exit(main())
