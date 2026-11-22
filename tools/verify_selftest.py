#!/usr/bin/env python3
"""Self-test: prove the verifier actually catches defects.

A verifier that reports "no anomalies" is worthless unless it is shown to fail
on corrupted input.  This mutates real ECL data in ways that must be detected
and asserts the verifier flags each one.

Usage:
    python tools/verify_selftest.py
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
from contextlib import redirect_stdout

sys.path.insert(0, "tools")

import verify_ecl  # noqa: E402
from ecl_dump import parse  # noqa: E402

ECL = "work/th07_dat/ecldata1.ecl"
SIG = "tools/ecl_signatures.json"


class Args:
    def __init__(self, datadir):
        self.datadir = datadir
        self.sig = SIG
        self.verbose = False
        self.budget = 200_000
        self.start_sub = 0


def run_on(path: str):
    """Run the verifier over a single .ecl file and return the anomalies."""
    sig = {int(k): v for k, v in json.load(open(SIG, encoding="utf-8")).items()}
    ecl = parse(path)
    st = verify_ecl.Stats()
    verify_ecl.verify_stage(ecl, sig, st, Args(os.path.dirname(path) or "."))
    return st.anomalies


def check(name: str, anomalies, expect_kind: str | None) -> bool:
    kinds = {a.kind for a in anomalies}
    if expect_kind is None:
        ok = not anomalies
        detail = "clean" if ok else f"unexpected {sorted(kinds)}"
    else:
        ok = expect_kind in kinds
        detail = f"got {sorted(kinds) or 'nothing'}"
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")
    return ok


def mutate(src: bytes, out_dir: str, name: str, fn) -> str:
    data = bytearray(src)
    fn(data)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def main() -> int:
    src = open(ECL, "rb").read()
    out_dir = "work/selftest"
    results = []

    print("baseline (unmodified data):")
    results.append(check("clean file must report nothing",
                         run_on(ECL), None))

    ecl = parse(ECL)
    sub = ecl.subs[1]
    first = sub.instrs[0]

    def set_bad_opcode(buf: bytearray) -> None:
        # Turn a known-good instruction into opcode 0xFF (never dispatched).
        struct.pack_into("<H", buf, first.offset + 4, 0xFF)

    def set_bad_size(buf: bytearray) -> None:
        # Shrink `size` so parameter count no longer matches the signature.
        struct.pack_into("<H", buf, first.offset + 6, first.size - 4)

    def set_bad_call(buf: bytearray) -> None:
        # Point a `call` at a sub that does not exist.  Sub1 has no call, so
        # locate any call in the whole file instead of assuming one exists in a
        # particular sub.
        for s in ecl.subs:
            for ins in s.instrs:
                if ins.id == 41:
                    struct.pack_into("<I", buf, ins.offset + 12, 9999)
                    return
        raise SystemExit("no call instruction in file; cannot test")

    print("\ninjected defects (each must be detected):")
    p = mutate(src, out_dir, "bad_opcode.ecl", set_bad_opcode)
    results.append(check("unknown opcode 0xFF", run_on(p), "unknown-opcode"))

    p = mutate(src, out_dir, "bad_size.ecl", set_bad_size)
    results.append(check("instruction size vs signature", run_on(p), "size-mismatch"))

    p = mutate(src, out_dir, "bad_call.ecl", set_bad_call)
    results.append(check("call target out of range", run_on(p), "bad-call-target"))

    # Corrupt a jump offset so ip lands in the middle of an instruction.
    def set_bad_jump(buf: bytearray) -> None:
        for ins in ecl.subs[1].instrs:
            if ins.id == 2:
                cp = struct.unpack_from("<i", ins.data, 4)[0]
                struct.pack_into("<i", buf, ins.offset + 16, cp + 2)
                return

    p = mutate(src, out_dir, "bad_jump.ecl", set_bad_jump)
    results.append(check("misaligned jump target", run_on(p), "bad-ip"))

    print(f"\n{sum(results)}/{len(results)} self-tests passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
