#!/usr/bin/env python3
"""Minimal, dependency-free reader for Touhou 07 (Perfect Cherry Blossom) th07.dat.

Archive format (PBG4), reverse-engineered from thtk/thtk/thdat06.c:
    u32 magic   'PBG4'
    u32 count   number of entries
    u32 offset  file offset of the LZSS-compressed entry table
    u32 size    decompressed size of the entry table
    ...followed by 'count' LZSS-compressed entries...

Entry table (decompressed) is a packed sequence of records:
    asciiz name
    u32    offset   (absolute file offset of the entry's compressed data)
    u32    size     (decompressed size)
    u32    extra    (unknown / checksum-ish)

Each entry's compressed data starts at 'offset' and runs to the next entry's
offset (the last entry runs to EOF).

LZSS parameters (thtk/thtk/thlzss.c):
    flag byte, bit 0 first. 1 => literal byte follows.
    0 => 2 bytes: 12-bit offset (1..0xFFF) + 4-bit length (3..18).
    No 18 length / 0xFFF offset "repeat last match" extension in th06+.

Usage:
    python pbg4.py list th07.dat
    python pbg4.py extract th07.dat ECL OUT.bin
    python pbg4.py extractall th07.dat OUTDIR
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

LZSS_DICTSIZE = 0x2000
LZSS_DICTSIZE_MASK = 0x1FFF
LZSS_MIN_MATCH = 3
LZSS_MAX_MATCH = 18


class PBGError(RuntimeError):
    pass


def lzss_decompress(data: bytes, size: int) -> bytes:
    """Decompress TH06/TH07-style LZSS.

    Bit-level MSB-first reads; 1 flag bit per token, then either an 8-bit
    literal or a 13-bit dictionary offset + 4-bit length (+3).  The 8 KB
    dictionary is zero-initialised and written from index 1.  Mirrors
    th_unlzss() in thtk/thtk/thlzss.c exactly.
    """
    out = bytearray()
    dic = bytearray(LZSS_DICTSIZE)
    head = 1
    bitbuf = 0
    bitcnt = 0
    pos = 0
    n = len(data)

    def need(bits: int) -> int:
        nonlocal bitbuf, bitcnt, pos
        while bitcnt < bits:
            if pos >= n:
                raise PBGError(f"LZSS stream truncated at output {len(out)}/{size}")
            bitbuf = (bitbuf << 8) | data[pos]
            pos += 1
            bitcnt += 8
        bitcnt -= bits
        return (bitbuf >> bitcnt) & ((1 << bits) - 1)

    while len(out) < size:
        if need(1):
            c = need(8)
            out.append(c)
            dic[head] = c
            head = (head + 1) & LZSS_DICTSIZE_MASK
        else:
            off = need(13)
            if off == 0:
                break
            length = need(4) + LZSS_MIN_MATCH
            idx = off
            for _ in range(length):
                c = dic[idx & LZSS_DICTSIZE_MASK]
                idx += 1
                out.append(c)
                dic[head] = c
                head = (head + 1) & LZSS_DICTSIZE_MASK
    return bytes(out[:size])


class Entry:
    __slots__ = ("index", "name", "offset", "size", "extra", "zsize")

    def __init__(self, index: int, name: str, offset: int, size: int, extra: int):
        self.index = index
        self.name = name
        self.offset = offset
        self.size = size
        self.extra = extra
        self.zsize = 0

    @property
    def ext(self) -> str:
        root, ext = os.path.splitext(self.name)
        return ext.lower().lstrip(".")

    def __repr__(self) -> str:
        return f"<Entry {self.name} off=0x{self.offset:x} size={self.size}>"


class PBG:
    def __init__(self, path: str):
        self.path = path
        self.filesize = os.path.getsize(path)
        self.entries: list[Entry] = []
        self._fh = open(path, "rb")
        self._read_header()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "PBG":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _read_header(self) -> None:
        fh = self._fh
        fh.seek(0)
        head = fh.read(16)
        if len(head) < 16:
            raise PBGError("file too small for a PBG header")
        magic = head[:4]
        if magic != b"PBG4":
            raise PBGError(f"unexpected magic {magic!r} (expected b'PBG4')")
        count, offset, size = struct.unpack_from("<III", head, 4)
        if offset >= self.filesize:
            raise PBGError(f"entry table offset 0x{offset:x} past EOF")
        fh.seek(offset)
        table = lzss_decompress(fh.read(self.filesize - offset), size)

        p = 0
        for i in range(count):
            nul = table.find(b"\0", p)
            if nul < 0:
                raise PBGError(f"entry {i}: unterminated name")
            name = table[p:nul].decode("cp932", errors="replace")
            p = nul + 1
            if p + 12 > len(table):
                raise PBGError(f"entry {i}: truncated header")
            eoff, esize, extra = struct.unpack_from("<III", table, p)
            p += 12
            self.entries.append(Entry(i, name, eoff, esize, extra))

        # zsize = distance to the next entry's offset; last runs to EOF.
        ordered = sorted(self.entries, key=lambda e: e.offset)
        for i, e in enumerate(ordered):
            nxt = ordered[i + 1].offset if i + 1 < len(ordered) else self.filesize
            e.zsize = nxt - e.offset

    def read(self, entry: Entry) -> bytes:
        self._fh.seek(entry.offset)
        zdata = self._fh.read(entry.zsize)
        if len(zdata) != entry.zsize:
            raise PBGError(f"{entry.name}: short read")
        return lzss_decompress(zdata, entry.size)

    def by_name(self, name: str) -> Entry:
        for e in self.entries:
            if e.name.lower() == name.lower():
                return e
        raise KeyError(name)


def cmd_list(args: argparse.Namespace) -> int:
    with PBG(args.archive) as pbg:
        print(f"{args.archive}: PBG4, {len(pbg.entries)} entries, {pbg.filesize} bytes")
        for e in sorted(pbg.entries, key=lambda e: e.name.lower()):
            print(f"  {e.name:<20} off=0x{e.offset:08x} zsize={e.zsize:>9} size={e.size:>9} extra=0x{e.extra:08x}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    with PBG(args.archive) as pbg:
        e = pbg.by_name(args.entry)
        data = pbg.read(e)
        with open(args.out, "wb") as f:
            f.write(data)
        print(f"extracted {e.name}: {e.size} bytes -> {args.out}")
    return 0


def cmd_extractall(args: argparse.Namespace) -> int:
    os.makedirs(args.outdir, exist_ok=True)
    count = 0
    with PBG(args.archive) as pbg:
        for e in pbg.entries:
            if not e.name:
                continue
            out = os.path.join(args.outdir, e.name)
            try:
                data = pbg.read(e)
            except PBGError as exc:
                print(f"  FAILED {e.name}: {exc}", file=sys.stderr)
                continue
            with open(out, "wb") as f:
                f.write(data)
            count += 1
    print(f"extracted {count} entries -> {args.outdir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="list entries")
    p.add_argument("archive")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("extract", help="extract one entry by name")
    p.add_argument("archive")
    p.add_argument("entry")
    p.add_argument("out")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("extractall", help="extract every entry")
    p.add_argument("archive")
    p.add_argument("outdir")
    p.set_defaults(func=cmd_extractall)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
