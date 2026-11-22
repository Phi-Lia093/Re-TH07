#!/usr/bin/env python3
"""Extract readable text (tables preserved) from a saved Touhou Wiki ECL page.

The saved page is MediaWiki HTML.  This turns it into plain text where table
cells are separated by ` | ` so the TH07 opcode tables stay legible.

Usage:
    python tools/ref_extract.py ref/<page>.htm > work/ref_ecl.txt
    python tools/ref_extract.py ref/<page>.htm --section "Th07" 
"""
from __future__ import annotations

import argparse
import html as htmllib
import re
import sys
from html.parser import HTMLParser


class Extractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "tr", "table", "pre"}
    SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip_depth = 0
        self.in_cell = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in ("td", "th"):
            self.out.append(" | ")
            self.in_cell = True
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in ("td", "th"):
            self.in_cell = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.out.append(data)

    def text(self) -> str:
        raw = "".join(self.out)
        raw = raw.replace("\r", "")
        lines = []
        for line in raw.split("\n"):
            # collapse runs of spaces but keep the table separators
            line = re.sub(r"[ \t]+", " ", line).strip()
            line = re.sub(r"^(\| )+", "", line)
            line = re.sub(r"(\s*\|\s*)+$", "", line)
            if line and line != "|":
                lines.append(line)
        # drop consecutive duplicates (wiki nav noise)
        dedup = []
        for line in lines:
            if not dedup or dedup[-1] != line:
                dedup.append(line)
        return "\n".join(dedup)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--section", help="only print from a heading match onward")
    ap.add_argument("--until", help="stop at this heading match")
    args = ap.parse_args()

    with open(args.page, "rb") as f:
        raw = f.read()
    ex = Extractor()
    ex.feed(raw.decode("utf-8", "replace"))
    text = ex.text()

    if args.section:
        idx = text.lower().find(args.section.lower())
        if idx >= 0:
            text = text[idx:]
    if args.until:
        idx = text.lower().find(args.until.lower())
        if idx > 0:
            text = text[:idx]
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
