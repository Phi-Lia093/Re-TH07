#!/usr/bin/env python3
"""TH07 ECL container parser and validator.

Implements the container format documented in docs/01-ecl-format.md and
validates it against the real game data: for every sub, walking instructions by
their `size` field must land exactly on the next sub's start offset.

Usage:
    python ecl_dump.py ecldata1.ecl [...]
    python ecl_dump.py --summary ecldata*.ecl
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field

INSTR_HEADER = 12
TIMELINE_SLOTS = 16  # TH07 timeline_count_max
SENTINEL_TIME = 0xFFFFFFFF

# TH07 special case: id 90 has a fixed 64-byte layout (see thecl06.c:1451).
SPECIAL_SIZE = {(7, 90): 64}


class ECLError(RuntimeError):
    pass


@dataclass
class Instr:
    offset: int  # absolute offset in file
    time: int
    id: int
    size: int
    rank_mask: int
    param_mask: int
    data: bytes

    @property
    def is_sentinel(self) -> bool:
        return self.time == SENTINEL_TIME

    @property
    def rank(self) -> int:
        return self.rank_mask >> 8

    def params_raw(self) -> str:
        return self.data.hex(" ")


@dataclass
class Sub:
    index: int
    offset: int
    end: int
    instrs: list[Instr] = field(default_factory=list)
    trailing_gap: int = 0
    sentinel_at: int = -1


@dataclass
class ECL:
    path: str
    sub_count: int
    timeline_count: int
    offsets: tuple[int, ...]
    subs: list[Sub]
    size: int
    timeline_start: int = 0
    timeline_data: bytes = b""

    @property
    def instr_count(self) -> int:
        return sum(len(s.instrs) for s in self.subs)


def parse(path: str, version: int = 7, strict: bool = True) -> ECL:
    with open(path, "rb") as f:
        b = f.read()
    if len(b) < 4:
        raise ECLError(f"{path}: too small for an ECL header")

    sub_count, timeline_count = struct.unpack_from("<HH", b, 0)
    tmax = TIMELINE_SLOTS
    noff = tmax + sub_count + 1
    if 4 + 4 * noff > len(b):
        raise ECLError(
            f"{path}: offset table ({noff} entries) does not fit in {len(b)} bytes; "
            f"sub_count={sub_count} timeline_count={timeline_count}"
        )
    offsets = struct.unpack_from(f"<{noff}I", b, 4)

    def next_distinct(i: int) -> int:
        """End of sub i: the next offset strictly greater than offsets[i].

        For sub entries this is either the next sub's start or (for the last
        sub) the start of the timeline block -- never EOF, because the file
        tail belongs to the timeline section.
        """
        v = offsets[i]
        for j in range(i + 1, len(offsets)):
            if offsets[j] > v:
                return offsets[j]
        # Last sub: fall back to the timeline block's start.
        candidates = [o for o in offsets[:tmax] if o > v]
        return min(candidates) if candidates else len(b)

    subs: list[Sub] = []
    for s in range(sub_count):
        base = offsets[tmax + s]
        end = next_distinct(tmax + s)
        sub = Sub(index=s, offset=base, end=end)
        if not (0 <= base < end <= len(b)):
            raise ECLError(f"{path}: sub {s} has invalid range [{base:#x}, {end:#x})")

        p = base
        while p + INSTR_HEADER <= end:
            time, iid, size, rank_mask, param_mask = struct.unpack_from("<IHHHH", b, p)
            if time == SENTINEL_TIME or size == 0:
                break
            if size < INSTR_HEADER or p + size > end:
                raise ECLError(
                    f"{path}: sub {s} instr at {p:#x} (id={iid}) has bad size {size}"
                )
            expected = SPECIAL_SIZE.get((version, iid))
            if expected is not None and size != expected and strict:
                raise ECLError(
                    f"{path}: sub {s} instr at {p:#x}: id {iid} should be "
                    f"{expected} bytes, got {size}"
                )
            sub.instrs.append(
                Instr(
                    offset=p,
                    time=time,
                    id=iid,
                    size=size,
                    rank_mask=rank_mask,
                    param_mask=param_mask,
                    data=b[p + INSTR_HEADER : p + size],
                )
            )
            p += size
        sub.sentinel_at = p
        sub.trailing_gap = end - p
        subs.append(sub)

    # File layout is [header+offsets][subs][timelines].  The timeline block
    # starts at the first timeline slot offset and runs to EOF.
    timeline_start = min((o for o in offsets[:tmax] if o), default=len(b))
    return ECL(
        path=path,
        sub_count=sub_count,
        timeline_count=timeline_count,
        offsets=offsets,
        subs=subs,
        size=len(b),
        timeline_start=timeline_start,
        timeline_data=b[timeline_start:],
    )


def validate(path: str) -> tuple[bool, list[str]]:
    """Validate layout and sub boundaries.

    Checks:
      1. every sub's instruction walk lands exactly 12 bytes before its end
         (the sentinel) -- this holds even for the last sub;
      2. the first timeline slot begins exactly where the last sub's sentinel
         ends, i.e. the file is [table][subs][timelines] with no gap.
    """
    problems: list[str] = []
    try:
        ecl = parse(path)
    except ECLError as exc:
        return False, [str(exc)]

    for sub in ecl.subs:
        if sub.trailing_gap != INSTR_HEADER:
            problems.append(
                f"{path}: sub {sub.index} leaves {sub.trailing_gap} trailing bytes "
                f"(expected {INSTR_HEADER} for the sentinel)"
            )

    last = ecl.subs[-1]
    timeline_start = min((o for o in ecl.offsets[:TIMELINE_SLOTS] if o), default=None)
    if timeline_start is not None:
        want = last.sentinel_at + INSTR_HEADER
        if timeline_start != want:
            problems.append(
                f"{path}: timeline block starts at {timeline_start:#x}, expected "
                f"{want:#x} (right after the last sub's sentinel)"
            )
    return not problems, problems


def cmd_summary(paths: list[str]) -> int:
    ok_all = True
    print(f"{'file':<16} {'subs':>5} {'insts':>7} {'maxtime':>8} {'status':>8}")
    print("-" * 50)
    for path in paths:
        ok, problems = validate(path)
        ok_all &= ok
        ecl = parse(path)
        maxtime = max((i.time for s in ecl.subs for i in s.instrs), default=0)
        name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        print(
            f"{name:<16} {ecl.sub_count:>5} {ecl.instr_count:>7} {maxtime:>8} "
            f"{'PASS' if ok else 'FAIL':>8}"
        )
        for p in problems[:5]:
            print(f"   ! {p}")
    return 0 if ok_all else 1


def cmd_dump(paths: list[str], limit: int | None) -> int:
    for path in paths:
        ecl = parse(path)
        name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        print(f"=== {name}: subs={ecl.sub_count} timelines={ecl.timeline_count} "
              f"instrs={ecl.instr_count} ===")
        shown = 0
        for sub in ecl.subs:
            print(f"sub Sub{sub.index}()  @0x{sub.offset:x}  {len(sub.instrs)} instrs")
            for ins in sub.instrs:
                if limit is not None and shown >= limit:
                    return 0
                print(
                    f"  +{ins.time:<5} [{ins.rank:02x}] ins_{ins.id:<3} "
                    f"sz={ins.size:<3} pm=0x{ins.param_mask:04x} {ins.params_raw()}"
                )
                shown += 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--summary", action="store_true", help="one-line-per-file validation")
    ap.add_argument("--limit", type=int, default=None, help="max instructions to print")
    args = ap.parse_args(argv)
    if args.summary:
        return cmd_summary(args.paths)
    return cmd_dump(args.paths, args.limit)


if __name__ == "__main__":
    sys.exit(main())
