#!/usr/bin/env python3
"""Executable model of TH07 player logic, built from the disassembly.

Every rule here is traced to code in th07.exe and cross-checked against the
.sht data; see docs/08-player-runtime.md for the address of each claim.

Sources:
  FUN at ~0x440cf0  (death/respawn)      -> position reset, hitbox writes
  FUN at ~0x410xxx  (player update)      -> the 8-direction movement switch
  player + 0x23f0/0x23f4  speed multipliers (0.6 / 1.0)
  player + 0x930/0x934    position x, y
  player + 0x990/0x994    hitbox half-extents (x, y)
  player + 0x99c/0x9a0    graze half-extents
  player + 0x9cc/0x9d0    per-frame velocity
  DAT_00575948            pointer to the loaded SHT header

Key finding: the .sht constants are *half-extents after scaling*, so the
    hitbox radius is `hitbox / 2`.  Reimu's 1.65 becomes 0.825.

Usage:
    python tools/player_model.py            # verify constants + demo movement
    python tools/player_model.py --demo     # movement trace table
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import struct
import sys

sys.path.insert(0, "tools")

# ---------------------------------------------------------------- game frame
# The engine advances at a fixed 60 Hz; DAT_00575ac8 is the slow-motion
# factor applied as a multiplier on velocity (see player update).
FPS = 60

# Speed multipliers at player+0x23f0 / +0x23f4.  These are NOT the focus
# toggle: focus selects a different .sht speed field instead (the 8-way switch
# loads +0x28/+0x30 rather than +0x24/+0x2c).  The 0.6 value appears only
# during the stage-entry invincibility sequence and 1.0 restores normal play.
SPEED_MUL_NORMAL = 1.0      # 0x3f800000, restored after intro
SPEED_MUL_INTRO = 0.6       # 0x3f19999a, intro sequence only


class ShtHeader:
    """The 12 floats + level table at the head of a .sht file."""

    FIELDS = [
        "bombs", "unknown2", "hitbox", "graze_hitbox",
        "autocollected_item_speed", "item_hitbox", "cherry_loss_on_die",
        "point_of_collection", "hv_speed", "hv_focused_speed",
        "diagonal_speed", "diagonal_focused_speed",
    ]

    def __init__(self, path: str):
        with open(path, "rb") as f:
            b = f.read()
        self.path = path
        self.unknown1, self.level_count = struct.unpack_from("<HH", b, 0)
        vals = struct.unpack_from("<12f", b, 4)
        for name, v in zip(self.FIELDS, vals):
            setattr(self, name, v)

    # Byte offsets must match th07's reads of DAT_00575948 + N.
    @property
    def off_hitbox(self) -> float:
        return 0x0C

    def field_at(self, off: int) -> float:
        """Read a header field the way the engine does, by byte offset."""
        idx = (off - 4) // 4
        return getattr(self, self.FIELDS[idx])


class Player:
    """Player state with the fields the engine actually uses."""

    def __init__(self, sht: ShtHeader):
        self.sht = sht
        # Hitbox / graze half-extents: engine divides the .sht value by 2.
        self.hitbox_half = sht.hitbox / 2.0
        self.graze_half = sht.graze_hitbox / 2.0

        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        # Velocity multipliers (0x23f0/0x23f4); both 1.0 while unfocused.
        self.speed_mul_x = SPEED_MUL_NORMAL
        self.speed_mul_y = SPEED_MUL_NORMAL
        # Per-frame velocity (0x9cc/0x9d0).
        self.vx = 0.0
        self.vy = 0.0
        # Last input direction (-1, 0, 1) for animation selection.
        self.dir_x = 0.0
        self.dir_y = 0.0
        self.focused = False

    def set_focused(self, focused: bool) -> None:
        """Select the focused (slow) key state.

        Note: focus does *not* scale a multiplier -- the engine's 8-way switch
        simply loads a different .sht field (+0x28/+0x30 instead of
        +0x24/+0x2c).  The flag is recorded here and consumed by move().
        """
        self.focused = focused

    def move(self, dx: int, dy: int, slow_factor: float = 1.0) -> None:
        """One frame of movement from digital input (-1, 0 or 1 per axis).

        Mirrors the engine's 8-way switch:
          vertical only   -> hv / hv_focused speed on y
          horizontal only -> hv / hv_focused speed on x
          diagonal        -> diagonal / diagonal_focused on BOTH axes,
                             each already equal to speed / sqrt(2)
        The per-axis value is then scaled by the engine's slow-motion factor
        (DAT_00575ac8) and accumulated into position; the caller clamps.
        """
        s = self.sht
        focused = self.focused
        if dx and dy:
            spd = s.diagonal_focused_speed if focused else s.diagonal_speed
            sx, sy = spd, spd
        elif dx:
            sx = s.hv_focused_speed if focused else s.hv_speed
            sy = 0.0
        elif dy:
            sy = s.hv_focused_speed if focused else s.hv_speed
            sx = 0.0
        else:
            sx = sy = 0.0

        self.vx = sx * self.speed_mul_x * slow_factor
        self.vy = sy * self.speed_mul_y * slow_factor
        self.x += self.vx
        self.y += self.vy
        self.dir_x, self.dir_y = float(dx), float(dy)

    def clamp(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        """Engine clamps to [DAT_0062f874, +DAT_0062f87c] etc."""
        self.x = min(max(self.x, x_min), x_max)
        self.y = min(max(self.y, y_min), y_max)

    def hit(self, bx: float, by: float, br: float, mode: str = "hitbox") -> bool:
        """Circle-vs-box test used for enemy bullets.

        The engine treats the player as an axis-aligned box of half-extents
        hitbox_half; `graze` uses the larger graze_half box.
        """
        half = self.hitbox_half if mode == "hitbox" else self.graze_half
        return abs(bx - self.x) <= half + br and abs(by - self.y) <= half + br


def verify_against_sht(verbose: bool = False) -> int:
    """Check the derived model against every shipped .sht."""
    print(f"{'file':<13}{'hitbox':>8}{'half':>8}{'graze':>8}{'ghalf':>8}"
          f"{'hv':>6}{'hvf':>6}{'diag':>8}{'diag/hv':>9}")
    print("-" * 74)
    bad = 0
    for path in sorted(glob.glob("work/th07_dat/*.sht")):
        s = ShtHeader(path)
        p = Player(s)
        ratio = s.diagonal_speed / s.hv_speed
        expect = 1.0 / math.sqrt(2.0)
        ok = abs(ratio - expect) < 1e-5
        bad += 0 if ok else 1
        print(f"{os.path.basename(path):<13}{s.hitbox:>8.2f}"
              f"{p.hitbox_half:>8.3f}{s.graze_hitbox:>8.2f}"
              f"{p.graze_half:>8.3f}{s.hv_speed:>6.1f}"
              f"{s.hv_focused_speed:>6.2f}{s.diagonal_speed:>8.4f}"
              f"{ratio:>9.5f}{'' if ok else '  <-- diagonal != hv/sqrt2'}")
    print(f"\ndiagonal/hv should be 1/sqrt(2) = {1/math.sqrt(2):.5f} for all files")
    return bad


def demo() -> int:
    """Print a movement trace to make the numbers checkable by hand."""
    s = ShtHeader("work/th07_dat/ply00a.sht")       # Reimu type A
    p = Player(s)
    print(f"Reimu A: hitbox={s.hitbox} (half {p.hitbox_half}), "
          f"graze={s.graze_hitbox} (half {p.graze_half})")
    print(f"          hv={s.hv_speed}, focused={s.hv_focused_speed}, "
          f"diag={s.diagonal_speed:.4f}, diag_focused={s.diagonal_focused_speed:.4f}")

    for label, dx, dy, focused in (
        ("right, unfocused", 1, 0, False),
        ("up-right, unfocused", 1, 1, False),
        ("right, focused", 1, 0, True),
        ("up-right, focused", 1, 1, True),
        ("held still", 0, 0, False),
    ):
        p.x = p.y = 0.0
        p.set_focused(focused)
        p.move(dx, dy)
        dist = math.hypot(p.vx, p.vy)
        print(f"  {label:<22} v=({p.vx:+.4f},{p.vy:+.4f}) "
              f"|v|={dist:.4f}")

    p.set_focused(False)
    p.x = p.y = 0.0
    for f in range(1, 61):
        p.move(1, 0)
    print(f"\n1 second holding right: x={p.x:.2f} "
          f"(expect {s.hv_speed * FPS:.1f} px)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if args.demo:
        return demo()
    bad = verify_against_sht(args.verbose)
    print()
    demo()
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
