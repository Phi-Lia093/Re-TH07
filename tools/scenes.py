#!/usr/bin/env python3
"""Enumerate TH07's scenes and the render resources each one loads.

Two independent anchors are combined:

1. The scene state machine.  The engine keeps `cur` and `next` scene ids at
   +0x154 / +0x158 of the top-level object and prints
   `"scene %d -> %d"` on every change (th07.exe.c around line 26341).  The
   switch that follows maps each scene id to its enter/leave handlers.

2. Resource loads.  Every ANM is loaded through
       FUN_0044df90(slot, "data/xxx.anm", flags)
   so the function that performs the load tells us which screen owns that art.

Usage:
    python tools/scenes.py            # scene table + resources
"""
from __future__ import annotations

import collections
import glob
import os
import re
import sys

sys.path.insert(0, "tools")

C_FILE = "th07.exe.c"

LOAD_RE = re.compile(r'FUN_0044df90\(\s*(0x[0-9a-f]+|\d+)\s*,\s*"([^"]+)"')
FUNC_RE = re.compile(r"^[a-zA-Z_][\w \*]*\s+(FUN_[0-9a-f]{8})\(.*\)\s*$")

# Scene ids observed in the transition switch, with the handler that runs when
# the scene becomes active.  Handlers that create state (operator_new / loads)
# are the "enter" side; FUN_0042f45d is the shared teardown that nearly every
# scene calls first.
SCENE_HANDLERS = {
    0: "(idle / none)",
    1: "FUN_0042f45d + enter",
    2: "FUN_0042f3c5",
    3: "FUN_0042f45d + FUN_0042f3c5",
    4: "(transition only)",
    5: "FUN_0044a302 / FUN_0045c5d0",
    6: "FUN_0044a302 + FUN_00443da0",
    7: "FUN_0045c5d0 + FUN_00443da0",
    8: "FUN_0043b4db",
    9: "FUN_0041e820",
    10: "FUN_00443da0 + FUN_0042f3c5",
    11: "FUN_0042f45d + FUN_0042f3c5",
    12: "FUN_0042f45d + FUN_0042f3c5",
}


def resource_table() -> dict[str, list[tuple[int, str]]]:
    """Map owning function -> [(slot, path)]."""
    out: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    current = "(global)"
    with open(C_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = FUNC_RE.match(line)
            if m:
                current = m.group(1)
                continue
            for lm in LOAD_RE.finditer(line):
                slot = int(lm.group(1), 0)
                out[current].append((slot, lm.group(2)))
    return out


def main() -> int:
    res = resource_table()
    print("=== ANM 资源加载：槽位 → 文件（按所属函数归组） ===\n")
    for func in sorted(res, key=lambda k: str(res[k])):
        print(f"{func}:")
        for slot, path in sorted(res[func]):
            print(f"    slot 0x{slot:02x} ({slot:>2})  {path}")
        print()

    print("=== 场景状态机 ===\n")
    print("引擎在 +0x154(当前) / +0x158(目标) 保存场景号，切换时打印")
    print('  "scene %d -> %d"\n')
    print(f"{'id':>3}  handler")
    print("-" * 50)
    for sid in sorted(SCENE_HANDLERS):
        print(f"{sid:>3}  {SCENE_HANDLERS[sid]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
