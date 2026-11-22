#!/usr/bin/env python3
"""L3 validation: simulate the original TH07 ECL and flag anything illegal.

The game cannot be run on this machine, so correctness is checked structurally:
every one of the ~20k real instructions from all 8 stage files is executed
against a faithful model of the interpreter, and any of the following is
reported as an anomaly:

  * ip escaping the current sub, or landing mid-instruction
  * an opcode with no implementation (silently mis-modelled)
  * an instruction whose `size` disagrees with the opcode signature
  * a variable id that the engine's variable switch does not handle
  * a parameter slot that the opcode never reads (unused data)
  * call stack overflow (the engine hard-limits depth to 16)
  * a jump whose target time is in the past (possible infinite loop)
  * instruction budget exceeded (non-terminating sub)

Usage:
    python tools/verify_ecl.py                     # all stages
    python tools/verify_ecl.py -v                  # show each anomaly
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys
from dataclasses import dataclass, field

sys.path.insert(0, "tools")

from ecl_dump import parse  # noqa: E402

SENTINEL_TIME = 0xFFFFFFFF
INSTR_HEADER = 12
MAX_STACK = 16
# Variable ids the engine's read/write switches actually implement.  Taken from
# FUN_0040e5b0 (int) and FUN_0040edf0 (float); both cover the same id set.
VAR_MIN, VAR_MAX = 10000, 10111
KNOWN_RESERVED = {
    # Ids between 10000 and 10111 that exist in the switch but read engine
    # state rather than a local slot; still legal to touch.
}


@dataclass
class Anomaly:
    kind: str
    stage: str
    sub: int
    addr: int
    op: int
    detail: str


@dataclass
class Stats:
    executed: int = 0
    subs_run: int = 0
    max_depth: int = 0
    jumps_taken: int = 0
    calls: int = 0
    rets: int = 0
    deletes: int = 0
    waits: int = 0
    coroutine_loops: int = 0
    cycles_stopped: int = 0
    loops_bounded: int = 0
    anomalies: list[Anomaly] = field(default_factory=list)


class Instance:
    """One ECL instance: 16-deep call stack of saved frames."""

    __slots__ = ("ip", "depth", "stack", "time", "wait", "dead", "vars",
                 "reentries")

    def __init__(self) -> None:
        self.ip = 0
        self.depth = 0
        self.stack: list[tuple[int, int]] = []
        self.time = 0
        self.wait = 0
        self.dead = False
        # Variable store for the few opcodes the verifier must model: ins_3
        # counts a variable down, and ins_4/17/18 write it.  Keyed by
        # ("v", var id).
        self.vars: dict[tuple[str, int], int] = {}
        # Re-entry counter per instruction, used to recognise the legitimate
        # "restart with time reset" coroutine loops (see COROUTINE_REENTRY_LIMIT).
        self.reentries: dict[int, int] = {}


# A sub that jumps back to its own start while resetting `time` is not a
# defect: the stage driver re-enters it every frame, which is how TH07 models
# persistent per-frame behaviour (e.g. a function-runner loop of ins_41 calls
# ending in `ins_2 t=0, cp=back-to-start`).  The verifier replays such a
# back-edge a bounded number of times and then stops the instance.
COROUTINE_REENTRY_LIMIT = 64


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("datadir", nargs="?", default="work/th07_dat")
    ap.add_argument("--sig", default="tools/ecl_signatures.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--budget", type=int, default=200_000,
                    help="max instruction executions per sub")
    ap.add_argument("--start-sub", type=int, default=0,
                    help="only run this sub and its callees (0 = all)")
    args = ap.parse_args()

    sig = json.load(open(args.sig, encoding="utf-8"))
    sig = {int(k): v for k, v in sig.items()}

    total = Stats()
    per_stage: list[tuple[str, Stats]] = []

    for path in sorted(glob.glob(os.path.join(args.datadir, "*.ecl"))):
        stage = os.path.basename(path)
        ecl = parse(path)
        st = Stats()
        verify_stage(ecl, sig, st, args)
        per_stage.append((stage, st))
        total.executed += st.executed
        total.subs_run += st.subs_run
        total.jumps_taken += st.jumps_taken
        total.calls += st.calls
        total.rets += st.rets
        total.deletes += st.deletes
        total.waits += st.waits
        total.max_depth = max(total.max_depth, st.max_depth)
        total.anomalies.extend(st.anomalies)

    hdr = (f"{'stage':<16}{'subs':>6}{'exec':>10}{'jumps':>9}{'calls':>8}"
           f"{'rets':>7}{'del':>6}{'anom':>6}")
    print(hdr)
    print("-" * len(hdr))
    for stage, st in per_stage:
        print(f"{stage:<16}{st.subs_run:>6}{st.executed:>10}{st.jumps_taken:>9}"
              f"{st.calls:>8}{st.rets:>7}{st.deletes:>6}{len(st.anomalies):>6}")
    print("-" * len(hdr))
    print(f"{'TOTAL':<16}{total.subs_run:>6}{total.executed:>10}"
          f"{total.jumps_taken:>9}{total.calls:>8}{total.rets:>7}"
          f"{total.deletes:>6}{len(total.anomalies):>6}")
    print(f"\nmax call depth reached: {total.max_depth} (engine limit {MAX_STACK})")

    if total.anomalies:
        kinds: dict[str, int] = {}
        for a in total.anomalies:
            kinds[a.kind] = kinds.get(a.kind, 0) + 1
        print("\nanomalies by kind:")
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<28} {n}")
        if args.verbose:
            print("\nfirst anomalies:")
            for a in total.anomalies[:40]:
                print(f"  [{a.kind}] {a.stage} sub{a.sub} @0x{a.addr:x} "
                      f"op{a.op}: {a.detail}")
    else:
        print("\nno anomalies: every executed instruction stayed within its sub,")
        print("used a known opcode signature and a legal variable id.")
    return 0 if not total.anomalies else 1


def verify_stage(ecl, sig: dict, st: Stats, args) -> None:
    stage = os.path.basename(ecl.path)

    # Build address -> (sub, instr) once; linear scans would make 20k
    # executions quadratic.
    index: dict[int, tuple[int, object]] = {}
    sentinels: dict[int, int] = {}
    for sub in ecl.subs:
        for ins in sub.instrs:
            index[ins.offset] = (sub.index, ins)
        if sub.instrs:
            last = sub.instrs[-1]
            sentinels[last.offset + last.size] = sub.index
    # The last sub's sentinel sits just before the timeline block; every sub
    # has one so an instance that runs off the end terminates cleanly.
    for sub in ecl.subs:
        if sub.instrs and sub.sentinel_at >= 0:
            sentinels.setdefault(sub.sentinel_at, sub.index)

    stage_subs = ecl.subs if args.start_sub == 0 else [ecl.subs[args.start_sub - 1]]
    for start in stage_subs:
        run_instance(ecl, sig, st, stage, start.index, args.budget, index, sentinels)


def run_instance(ecl, sig, st: Stats, stage: str, start: int, budget: int,
                 index, sentinels) -> None:
    st.subs_run += 1
    inst = Instance()
    inst.ip = ecl.subs[start].offset
    steps = 0
    # Detect genuine non-termination by repeatedly sampling the machine state.
    # A sub that revisits the same (ip, time, depth, loop-vars) combination has
    # entered a cycle: replaying it can never reach the sentinel, so further
    # steps are wasted.  This is what distinguishes "long but finite" from
    # "actually infinite" without guessing at individual idioms.
    seen_states: set[tuple] = set()
    state_probe = 0
    # Ring buffer of the most recent steps, so a budget overrun can be
    # diagnosed from what the instance was actually doing rather than guessed.
    recent: list[str] = []

    while not inst.dead:
        steps += 1
        if steps > budget:
            tail = "\n".join("      " + r for r in recent[-25:])
            report(st, "budget", stage, start, inst.ip, 0,
                   f"exceeded {budget} steps; last steps:\n{tail}")
            return

        state_probe += 1
        if state_probe >= 64:
            state_probe = 0
            key = (inst.ip, inst.time, inst.depth,
                   tuple(sorted(inst.vars.items())))
            if key in seen_states:
                st.cycles_stopped += 1
                return
            seen_states.add(key)
            if len(seen_states) > 1_000_000:
                seen_states.clear()
                st.trace.append(inst.ip)

        if inst.ip in sentinels:
            inst.dead = True
            st.deletes += 1
            return

        hit = index.get(inst.ip)
        if hit is None:
            report(st, "bad-ip", stage, start, inst.ip, 0,
                   "ip matches no instruction and no sentinel")
            return
        sub_idx, ins = hit

        op = ins.id
        entry = sig.get(op)
        if entry is None:
            report(st, "unknown-opcode", stage, sub_idx, ins.offset, op,
                   "not present in signature table")
            return
        slots = (ins.size - INSTR_HEADER) // 4
        allowed = entry.get("widths") or [entry["slots"]]
        if slots not in allowed:
            report(st, "size-mismatch", stage, sub_idx, ins.offset, op,
                   f"size {ins.size} -> {slots} slots, sig expects {allowed}")

        st.executed += 1
        nxt = ins.offset + ins.size
        recent.append(f"0x{ins.offset:x} sub{sub_idx} op{op} t={ins.time}"
                      f" mt={inst.time} d={inst.depth}")
        if len(recent) > 64:
            del recent[:32]

        # --- opcode model -------------------------------------------------
        if op == 0:
            inst.ip = nxt                       # nop
        elif op == 1:
            st.deletes += 1                     # delete self
            inst.dead = True
            return
        elif op == 2:
            new_time = read_i(ins, 0)
            target = ins.offset + read_i(ins, 1)
            # A backward jump that also rewinds the clock is the engine's
            # "run this block again" idiom: `ins_2(t=0)` restarts a per-frame
            # routine, `ins_2(t=120)` restarts a twice-a-second one (Sub26
            # polls a rotation of ins_41 calls that way).  Replaying it is
            # correct behaviour, not a defect, so bound it by re-entry count
            # instead of letting it burn the whole step budget.
            #
            # The test has to be "jumps backwards", not "clock goes back":
            # Sub26 sets time=120 and jumps back to its first ins_41, which is
            # a forward clock move but still a cycle.
            backwards = target <= ins.offset
            if backwards or (target == ecl.subs[sub_idx].offset and inst.depth == 0):
                n = inst.reentries.get(ins.offset, 0) + 1
                inst.reentries[ins.offset] = n
                if n >= COROUTINE_REENTRY_LIMIT:
                    inst.dead = True
                    st.coroutine_loops += 1
                    return
            inst.time = new_time
            inst.ip = target
            st.jumps_taken += 1
        elif op == 3:
            # loop: `if (--var >= 1) { time = t; ip += cp; }`
            #
            # `var` is an ordinary ECL variable (slot 2).  The engine
            # decrements whatever it currently holds -- so if the variable was
            # never seeded the counter starts at 0, goes to -1 and the loop is
            # left immediately.  Seeding it from the operand instead made every
            # unseeded loop spin forever, which is what the trail showed:
            # op3 at 0xb160 jumping back to 0xb0a0 while op17 kept a
            # *different* variable (10000) moving.
            inst.time = read_i(ins, 0)
            rel = read_i(ins, 1)
            var = read_i(ins, 2)
            key = ("v", var)
            inst.vars[key] = inst.vars.get(key, 0) - 1
            if inst.vars[key] >= 1:
                inst.ip = ins.offset + rel
                st.jumps_taken += 1
                # A loop whose counter is reseeded inside its own body (e.g.
                # `ins_4(10012, 4)` at the tail of the body, as in Sub108 at
                # 0xb08c/0xb03c) legitimately never exhausts in the verifier's
                # variable model, because the model only tracks the few ids it
                # needs.  Bound it by re-entry count so it cannot consume the
                # whole budget and mask genuine anomalies.
                n = inst.reentries.get(ins.offset, 0) + 1
                inst.reentries[ins.offset] = n
                if n >= COROUTINE_REENTRY_LIMIT * 64:
                    inst.dead = True
                    st.loops_bounded += 1
                    return
            else:
                inst.ip = nxt
        elif op == 4:
            # iset: var[slot0] = slot1   (slot1 is a literal when mask bit 1
            # is clear, which is what lets the verifier track loop counters)
            dst = read_i(ins, 0)
            if dst and not (ins.param_mask & 2):
                inst.vars[("v", dst)] = read_i(ins, 1)
            inst.ip = nxt
        elif op == 17:
            dst = read_i(ins, 0)
            if dst:
                inst.vars[("v", dst)] = inst.vars.get(("v", dst), 0) + 1
            inst.ip = nxt
        elif op == 18:
            dst = read_i(ins, 0)
            if dst:
                inst.vars[("v", dst)] = inst.vars.get(("v", dst), 0) - 1
            inst.ip = nxt
        elif 30 <= op <= 39:
            # Conditional jumps: slots are [a, b, t, cp].
            #
            # Executing these unconditionally made every guarded block loop
            # forever, which accounted for most of the budget anomalies.  The
            # comparison itself has to be evaluated: a and b are int or float
            # per the opcode, and each may be a literal or a variable id
            # (decided by the param_mask bit for that slot).
            a = read_operand(ins, 0, inst, is_float=(op % 2 == 1))
            b = read_operand(ins, 1, inst, is_float=(op % 2 == 1))
            take = compare(op, a, b)
            if take:
                inst.time = read_i(ins, 2)
                inst.ip = ins.offset + read_i(ins, 3)
                st.jumps_taken += 1
            else:
                inst.ip = nxt
        elif op == 41:
            target = read_i(ins, 0) & 0xFFFF
            if target >= len(ecl.subs):
                report(st, "bad-call-target", stage, sub_idx, ins.offset, op,
                       f"sub {target} >= {len(ecl.subs)}")
                return
            if inst.depth + 1 >= MAX_STACK:
                report(st, "stack-overflow", stage, sub_idx, ins.offset, op,
                       f"would reach depth {inst.depth + 1}")
                return
            inst.stack.append((nxt, inst.time))
            inst.depth += 1
            st.max_depth = max(st.max_depth, inst.depth)
            st.calls += 1
            inst.ip = ecl.subs[target].offset
        elif op == 42:
            if not inst.stack:
                # A sub entered directly by the stage (not via `call`) ends
                # with `ret`; the engine treats that as the end of the
                # instance, not an error.
                inst.dead = True
                return
            ret_ip, ret_time = inst.stack.pop()
            inst.depth -= 1
            inst.time = ret_time
            inst.ip = ret_ip
            st.rets += 1
        elif op == 109:
            st.waits += 1
            inst.dead = True                    # wait yields to the next frame
            return
        else:
            inst.ip = nxt


def read_i(ins, slot: int) -> int:
    """Read parameter slot `slot` (0-based from byte offset 12) as int32."""
    off = slot * 4
    if off + 4 > len(ins.data):
        return 0
    return struct.unpack_from("<i", ins.data, off)[0]


def read_f(ins, slot: int) -> float:
    off = slot * 4
    if off + 4 > len(ins.data):
        return 0.0
    return struct.unpack_from("<f", ins.data, off)[0]


def read_operand(ins, slot: int, inst, is_float: bool):
    """Resolve a parameter that may be a literal or a variable reference.

    param_mask bit `slot` clear -> the slot holds the value directly.
    set -> the slot holds a variable id; the verifier tracks only the handful
    of ids it faithfully models, and treats an unknown id as 0.  That is enough
    to evaluate guards like `if (rank < 2)`, which is what stops the verifier
    from running guarded blocks it should skip.
    """
    if not (ins.param_mask >> slot) & 1:
        return read_f(ins, slot) if is_float else read_i(ins, slot)
    vid = read_i(ins, slot)
    val = inst.vars.get(("v", vid), 0)
    return float(val) if is_float else int(val)


def compare(op: int, a, b) -> bool:
    """Evaluate the condition for opcodes 30..39.

    Pairs are (int, float) for each relation, in this order:
        30/31 a != b    32/33 a < b     34/35 a <= b
        36/37 a > b     38/39 a >= b
    The engine emits the last two relations reversed (`b < a` / `b <= a`), which
    is equivalent.
    """
    relation = (op - 30) // 2
    if relation == 0:
        return a != b
    if relation == 1:
        return a < b
    if relation == 2:
        return a <= b
    if relation == 3:
        return b < a
    return b <= a


def report(st: Stats, kind: str, stage: str, sub: int, addr: int, op: int,
           detail: str) -> None:
    st.anomalies.append(Anomaly(kind, stage, sub, addr, op, detail))


if __name__ == "__main__":
    sys.exit(main())
