#!/usr/bin/env python3
"""Parse TH07 .anm files and export their THTX atlas as PNG.

Layout from thtk's thanm (anm_header06_t / sprite_t / anm_offset_t), verified
against all 63 real files:

  AnmEntry (64-byte header):
      u32 sprites, scripts, rt_textureslot, w, h, format,
          colorkey, nameoffset, x, y, version, memorypriority, thtxoffset
      u16 hasdata, lowresscale
      u32 nextoffset, zero3
  then:  u32 sprite_offsets[sprites]         (absolute file offsets)
         {i32 id; u32 offset} scripts[scripts]
  sprites live at their own offsets:  {u32 id; f32 x,y,w,h}
  THTX block at header+thtxoffset:
      "THTX", u16 version, u16 format, u16 width, u16 height, 4 unknown,
      then width*height*bpp bytes of pixels

Entries are chained by `nextoffset`.

Corrections found while validating (see docs/07-rendering-anm.md):
  * the header is 64 bytes (13 u32 + 2 u16 + 2 u32), not 60;
  * THTX dimensions are u16, not u32 -- reading u32 gives absurd sizes;
  * the atlas is the in-file THTX block; nameoffset is only a leftover path
    to the original PNG.

Usage:
    python tools/anm_parse.py                        # validate all .anm
    python tools/anm_parse.py f.anm --png out.png    # export atlas
    python tools/anm_parse.py f.anm --list           # list sprites
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

HEADER = struct.Struct("<13I2H2I")          # 64 bytes
SPRITE = struct.Struct("<I4f")              # 20 bytes
SCRIPT = struct.Struct("<iI")               # 8 bytes
THTX = struct.Struct("<4sHHHH")             # magic, ver, fmt, w, h (u16 dims!)
THTX_HEADER = 16                            # + 4 unknown bytes

FORMATS = {
    1: ("BGRA8888", 4),
    3: ("RGB565", 2),
    5: ("ARGB4444", 2),
    7: ("GRAY8", 1),
}


class AnmError(RuntimeError):
    pass


class AnmEntry:
    """One animation entry: header + sprite table + script table + THTX atlas."""

    def __init__(self, raw: bytes, base: int, path: str):
        self.path = path
        self.base = base
        b = raw
        if base + HEADER.size > len(b):
            raise AnmError(f"{path}: truncated header at {base}")
        (self.sprites, self.scripts, self.rt_textureslot, self.w, self.h,
         self.format, self.colorkey, self.nameoffset, self.x, self.y,
         self.version, self.memorypriority, self.thtxoffset,
         self.hasdata, self.lowresscale, self.nextoffset,
         self.zero3) = HEADER.unpack_from(b, base)

        tab = base + HEADER.size
        if self.sprites and tab + self.sprites * 4 > len(b):
            raise AnmError(f"{path}: sprite offset table past EOF at {base}")
        self.sprite_offsets = struct.unpack_from(
            f"<{self.sprites}I", b, tab) if self.sprites else ()
        script_base = tab + self.sprites * 4
        self.script_entries = []
        for i in range(self.scripts):
            if script_base + i * 8 + 8 > len(b):
                break
            self.script_entries.append(SCRIPT.unpack_from(b, script_base + i * 8))

        self.sprite_list = []
        for off in self.sprite_offsets:
            # The first entry's offsets are absolute; entries reached through
            # `nextoffset` store offsets relative to their own header.  For the
            # first entry base == 0, so adding base is correct in both cases
            # and was the reason entry 1+ produced absurd sprite rects.
            abs_off = base + off
            if abs_off + SPRITE.size > len(b):
                raise AnmError(f"{path}: sprite offset {off} (+{base}) past EOF")
            sid, sx, sy, sw, sh = SPRITE.unpack_from(b, abs_off)
            self.sprite_list.append(dict(id=sid, x=sx, y=sy, w=sw, h=sh,
                                         offset=abs_off))

        # THTX block: 16-byte header with *u16* dimensions, then raw pixels.
        t = base + self.thtxoffset
        self.thtx_ok = False
        self.tw = self.th = self.thtx_format = 0
        if 0 <= t and t + THTX_HEADER <= len(b):
            magic, _ver, fmt, tw, th = THTX.unpack_from(b, t)
            if magic == b"THTX":
                self.thtx_ok = True
                self.thtx_format, self.tw, self.th = fmt, tw, th

    @property
    def fmt_name(self) -> str:
        return FORMATS.get(self.format, (f"unknown{self.format}", 0))[0]

    @property
    def bpp(self) -> int:
        return FORMATS.get(self.thtx_format or self.format, ("?", 0))[1]

    def pixel_bytes(self) -> int:
        return self.tw * self.th * self.bpp

    def decode(self, raw: bytes):
        """Decode the THTX atlas into a PIL image."""
        if Image is None:
            return None
        if not self.thtx_ok:
            raise AnmError(f"{self.path}: no THTX block")
        start = self.base + self.thtxoffset + THTX_HEADER
        b = raw[start:start + self.pixel_bytes()]
        if len(b) != self.pixel_bytes():
            raise AnmError(f"{self.path}: truncated texture "
                           f"({len(b)}/{self.pixel_bytes()})")
        w, h = self.tw, self.th
        fmt = self.thtx_format
        img = Image.new("RGBA", (w, h))
        px = img.load()
        if fmt == 5:                    # ARGB4444
            for i in range(w * h):
                v = b[i * 2] | (b[i * 2 + 1] << 8)
                px[i % w, i // w] = (
                    ((v >> 8) & 0xF) * 17,      # R
                    ((v >> 4) & 0xF) * 17,      # G
                    (v & 0xF) * 17,             # B
                    ((v >> 12) & 0xF) * 17)     # A
        elif fmt == 3:                  # RGB565
            for i in range(w * h):
                v = b[i * 2] | (b[i * 2 + 1] << 8)
                px[i % w, i // w] = (
                    ((v >> 11) & 0x1F) * 255 // 31,
                    ((v >> 5) & 0x3F) * 255 // 63,
                    (v & 0x1F) * 255 // 31,
                    255)
        elif fmt == 1:                  # BGRA8888
            for i in range(w * h):
                bb, gg, rr, aa = b[i * 4:i * 4 + 4]
                px[i % w, i // w] = (rr, gg, bb, aa)
        elif fmt == 7:                  # GRAY8
            for i in range(w * h):
                g = b[i]
                px[i % w, i // w] = (g, g, g, 255)
        else:
            raise AnmError(f"{self.path}: unsupported THTX format {fmt}")
        return img


class AnmFile:
    """An .anm file, possibly holding several chained entries."""

    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            self.raw = f.read()
        self.entries: list[AnmEntry] = []
        off = 0
        seen: set[int] = set()
        while off not in seen and off + HEADER.size <= len(self.raw):
            seen.add(off)
            try:
                e = AnmEntry(self.raw, off, path)
            except AnmError:
                break
            self.entries.append(e)
            if e.nextoffset == 0:
                break
            off = e.nextoffset

    @property
    def main(self) -> AnmEntry:
        return self.entries[0]


def validate(path: str) -> list[str]:
    """Structural checks on every entry of the file."""
    problems: list[str] = []
    name = os.path.basename(path)
    try:
        anm = AnmFile(path)
    except AnmError as exc:
        return [str(exc)]
    if not anm.entries:
        return [f"{name}: no parsable entries"]

    for i, e in enumerate(anm.entries):
        tag = f"{name}[{i}]"
        if e.version != 2:
            problems.append(f"{tag}: version {e.version}, expected 2 for TH07")
        if not e.thtx_ok:
            problems.append(f"{tag}: no THTX block at offset {e.thtxoffset}")
            continue
        need = e.pixel_bytes()
        have = len(anm.raw) - (e.base + e.thtxoffset + THTX_HEADER)
        if need > have:
            problems.append(f"{tag}: THTX {e.tw}x{e.th} needs {need}B, "
                            f"only {have}B available")
        # Sprite rectangles must sit inside the decoded atlas.
        for s in e.sprite_list:
            if (s["x"] < 0 or s["y"] < 0 or s["x"] + s["w"] > e.tw
                    or s["y"] + s["h"] > e.th):
                problems.append(
                    f"{tag}: sprite {s['id']} rect "
                    f"({s['x']:.0f},{s['y']:.0f},{s['w']:.0f}x{s['h']:.0f}) "
                    f"outside atlas {e.tw}x{e.th}")
                break
        ids = [s["id"] for s in e.sprite_list]
        if len(set(ids)) != len(ids):
            problems.append(f"{tag}: duplicate sprite ids")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--png", help="export the first entry's atlas")
    ap.add_argument("--entry", type=int, default=0, help="which entry to export")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.png:
        if not args.paths:
            print("--png needs a file", file=sys.stderr)
            return 1
        anm = AnmFile(args.paths[0])
        e = anm.entries[args.entry]
        img = e.decode(anm.raw)
        if img is None:
            print("Pillow not available", file=sys.stderr)
            return 1
        img.save(args.png)
        print(f"{args.paths[0]}[{args.entry}]: {e.tw}x{e.th} "
              f"{FORMATS.get(e.thtx_format, ('?',))[0]}, "
              f"{e.sprites} sprites -> {args.png}")
        return 0

    paths = args.paths or sorted(glob.glob("work/th07_dat/*.anm"))
    bad = 0
    fmts: dict[str, int] = {}
    print(f"{'file':<18}{'ent':>4}{'sprites':>8}{'scripts':>8}"
          f"{'atlas':>12}{'thtx':>10}  status")
    print("-" * 74)
    for path in paths:
        problems = validate(path)
        try:
            anm = AnmFile(path)
        except AnmError:
            print(f"{os.path.basename(path):<18}  PARSE FAIL")
            bad += 1
            continue
        e = anm.main
        fname = FORMATS.get(e.thtx_format, (f"fmt{e.thtx_format}",))[0]
        fmts[fname] = fmts.get(fname, 0) + 1
        status = "OK" if not problems else f"{len(problems)} issue(s)"
        print(f"{os.path.basename(path):<18}{len(anm.entries):>4}"
              f"{e.sprites:>8}{e.scripts:>8}"
              f"{f'{e.w}x{e.h}':>12}{fname:>10}  {status}")
        if problems:
            bad += 1
            for p in problems[:3]:
                print(f"    ! {p}")
        if args.list:
            for s in e.sprite_list[:40]:
                print(f"      sprite {s['id']:>4}: "
                      f"({s['x']:.0f},{s['y']:.0f}) {s['w']:.0f}x{s['h']:.0f}")
    print(f"\nTHTX formats: {fmts}")
    print(f"{len(paths) - bad}/{len(paths)} files validated")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
