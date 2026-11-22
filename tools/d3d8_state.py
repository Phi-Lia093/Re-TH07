#!/usr/bin/env python3
"""Recover TH07's D3D8 device-state vocabulary from call arguments.

Reading vtable slots against d3d8.h gave contradictions: the call
`(device + 0xfc)(0, 4, 2)` was labelled GetVertexShaderConstant, yet its
arguments are unmistakably `SetTextureStageState(stage=0, D3DTSS_MAGFILTER=4,
D3DTEXF_LINEAR=2)`, and the very next line sets MINFILTER to POINT.

The resolution: the decompiler's offsets and the header's slot order disagree
by a constant shift in this build, so slot numbers cannot be trusted.  What
*can* be trusted is the argument shape, because D3D constants are fixed:

    (stage, D3DTSS_*, value)          -> SetTextureStageState
    (D3DRS_*, value)                  -> SetRenderState
    (stage, texture)                  -> SetTexture
    (D3DTS_*, matrix*)                -> SetTransform
    (count, rects, flags)             -> Clear

This script classifies every device call by decoding its arguments against
those constant tables, which yields the real render-state vocabulary the
remake must reproduce -- without depending on vtable numbering at all.

Usage:
    python tools/d3d8_state.py            # full classification
    python tools/d3d8_state.py --summary  # just the distinct states
"""
from __future__ import annotations

import argparse
import collections
import re
import sys

C_FILE = "th07.exe.c"

# D3DTEXTURESTAGESTATETYPE
D3DTSS = {
    1: "COLOROP", 2: "COLORARG1", 3: "COLORARG2", 4: "ALPHAOP",
    5: "ALPHAARG1", 6: "ALPHAARG2", 7: "BUMPENVMAT00",
    8: "TEXCOORDINDEX", 11: "ADDRESSU", 12: "ADDRESSV",
    13: "BORDERCOLOR",
    16: "MAGFILTER", 17: "MINFILTER", 18: "MIPFILTER",
    19: "MIPMAPLODBIAS", 20: "MAXMIPLEVEL", 21: "MAXANISOTROPY",
    24: "COLORKEY", 25: "TEXCOORDINDEX",
}

# D3DTEXTUREOP / D3DTEXTUREFILTERTYPE / D3DTEXTUREADDRESS share value space
D3DTOP = {
    1: "DISABLE", 2: "SELECTARG1", 3: "SELECTARG2", 4: "MODULATE",
    5: "MODULATE2X", 6: "MODULATE4X", 7: "ADD", 8: "ADDSIGNED",
    9: "ADDSIGNED2X", 10: "SUBTRACT", 11: "ADDSMOOTH",
    12: "BLENDDIFFUSEALPHA", 13: "BLENDTEXTUREALPHA",
    14: "BLENDFACTORALPHA", 15: "BLENDTEXTUREALPHAPM",
    16: "BLENDCURRENTALPHA", 17: "PREMODULATE", 18: "MODULATEALPHA_ADDCOLOR",
    19: "MODULATECOLOR_ADDALPHA", 20: "MODULATEINVALPHA_ADDCOLOR",
    21: "MODULATEINVCOLOR_ADDALPHA", 22: "BUMPENVMAP", 23: "BUMPENVMAPLUMINANCE",
    24: "DOTPRODUCT3", 25: "MULTIPLYADD", 26: "LERP",
}

D3DTEXF = {1: "POINT", 2: "LINEAR", 3: "ANISOTROPIC", 4: "PYRAMIDALQUAD",
           5: "GAUSSIANQUAD", 6: "CONVOLUTIONMONO"}

D3DTADDRESS = {1: "WRAP", 2: "MIRROR", 3: "CLAMP", 4: "BORDER", 5: "MIRRORONCE"}

D3DTSS_COLOROP_KEYS = (1, 4)      # D3DTSS_COLOROP, D3DTSS_ALPHAOP

# D3DRENDERSTATETYPE
D3DRS = {
    0: "ZENABLE", 1: "FILLMODE", 2: "SHADEMODE", 3: "ZWRITEENABLE",
    4: "ALPHATESTENABLE", 5: "LASTPIXEL", 6: "SRCBLEND", 7: "DESTBLEND",
    8: "CULLMODE", 9: "ZFUNC", 10: "ALPHAREF", 11: "ALPHAFUNC",
    12: "DITHERENABLE", 13: "ALPHABLENDENABLE", 14: "FOGENABLE",
    15: "SPECULARENABLE", 16: "FOGCOLOR", 17: "FOGTABLEMODE",
    18: "FOGSTART", 19: "FOGEND", 20: "FOGDENSITY",
    22: "EDGEANTIALIAS", 23: "CULLCCW", 24: "COLORKEYENABLE",
    25: "COLORKEY", 26: "TEXTUREFACTOR", 27: "LIGHTING", 28: "AMBIENT",
    137: "CLIPPING", 138: "LIGHTING", 139: "AMBIENT",
    147: "STENCILENABLE", 148: "STENCILFAIL", 149: "STENCILZFAIL",
    150: "STENCILPASS", 151: "STENCILFUNC",
}

D3DBLEND = {1: "ZERO", 2: "ONE", 3: "SRCCOLOR", 4: "INVSRCCOLOR",
            5: "SRCALPHA", 6: "INVSRCALPHA", 7: "DESTALPHA",
            8: "INVDESTALPHA", 9: "DESTCOLOR", 10: "INVDESTCOLOR",
            11: "SRCALPHASAT", 12: "BOTHSRCALPHA", 13: "BOTHINVSRCALPHA"}

D3DTS = {256: "VIEW", 2: "PROJECTION", 3: "WORLD", 1: "TEXTURE0"}

CALL_RE = re.compile(
    r"\(\*\*\(code \*\*\)\(\*?DAT_00575958 \+ (0x[0-9a-f]+)\)\)"
    r"\(DAT_00575958(?:,([^;]*))?\);")

TOKEN_RE = re.compile(r"0x[0-9a-fA-F]+|&\w+|\w+|\d+\.\d+|\d+")


def decode_args(argstr: str | None):
    if not argstr:
        return []
    out = []
    for tok in TOKEN_RE.findall(argstr):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"0x[0-9a-fA-F]+", tok):
            out.append(int(tok, 16))
        elif re.fullmatch(r"\d+", tok):
            out.append(int(tok))
        else:
            out.append(tok)
    return out


def classify(off: int, args: list) -> tuple[str, str]:
    """Guess the device method from its arguments."""
    a = args
    if len(a) == 3 and a[0] == 0 and isinstance(a[1], int) and a[1] in D3DTSS:
        t, v = a[1], a[2]
        name = D3DTSS[t]
        if t in D3DTSS_COLOROP_KEYS and isinstance(v, int):
            return "SetTextureStageState", f"D3DTSS_{name} = D3DTOP_{D3DTOP.get(v, v)}"
        if name in ("MAGFILTER", "MINFILTER", "MIPFILTER") and isinstance(v, int):
            return "SetTextureStageState", f"D3DTSS_{name} = D3DTEXF_{D3DTEXF.get(v, v)}"
        if name in ("ADDRESSU", "ADDRESSV") and isinstance(v, int):
            return "SetTextureStageState", f"D3DTSS_{name} = D3DTADDRESS_{D3DTADDRESS.get(v, v)}"
        if name == "COLORKEY":
            return "SetTextureStageState", f"D3DTSS_COLORKEY = 0x{v:x}" if isinstance(v, int) else f"D3DTSS_COLORKEY = {v}"
        return "SetTextureStageState", f"D3DTSS_{name} = {v}"
    if len(a) == 2 and isinstance(a[0], int) and a[0] in D3DRS:
        s, v = a[0], a[1]
        name = D3DRS[s]
        if name in ("SRCBLEND", "DESTBLEND") and isinstance(v, int):
            return "SetRenderState", f"D3DRS_{name} = D3DBLEND_{D3DBLEND.get(v, v)}"
        if name in ("ZENABLE", "ALPHABLENDENABLE", "ALPHATESTENABLE",
                    "ZWRITEENABLE", "LIGHTING", "COLORKEYENABLE") and isinstance(v, int):
            return "SetRenderState", f"D3DRS_{name} = {'TRUE' if v else 'FALSE'}"
        if name == "ZFUNC" and isinstance(v, int):
            cmp = {1: "NEVER", 2: "LESS", 3: "EQUAL", 4: "LESSEQUAL",
                   5: "GREATER", 6: "NOTEQUAL", 7: "GREATEREQUAL", 8: "ALWAYS"}
            return "SetRenderState", f"D3DRS_ZFUNC = D3DCMP_{cmp.get(v, v)}"
        return "SetRenderState", f"D3DRS_{name} = {v}"
    if len(a) == 2 and isinstance(a[0], int) and a[0] in D3DTS:
        return "SetTransform", f"D3DTS_{D3DTS[a[0]]}"
    if len(a) == 2 and a[0] == 0:
        return "SetTexture", f"stage 0 <- {a[1]}"
    if len(a) >= 1 and off == 0x3c:
        return "Present", f"{len(a)} args"
    if len(a) == 1:
        return "state-block/other", f"{a[0]}"
    return "unknown", f"{a}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    with open(C_FILE, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    seen: collections.Counter = collections.Counter()
    per_off: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    rows = []
    for m in CALL_RE.finditer(text):
        off = int(m.group(1), 16)
        a = decode_args(m.group(2))
        meth, desc = classify(off, a)
        per_off[off][(meth, desc)] += 1
        if meth in ("SetTextureStageState", "SetRenderState", "SetTransform",
                    "SetTexture"):
            seen[(meth, desc)] += 1
        rows.append((off, meth, desc))

    print(f"device calls parsed: {len(rows)}")
    print(f"\n{'offset':>7}  {'method':<22} calls  example")
    print("-" * 78)
    for off, cnt in sorted(per_off.items()):
        top = cnt.most_common(1)[0]
        print(f"0x{off:04x}  {top[0][0]:<22} {sum(cnt.values()):>5}  {top[0][1][:38]}")

    print(f"\n=== distinct render states TH07 sets ({len(seen)}) ===")
    for (meth, desc), c in sorted(seen.items()):
        print(f"  {meth:<22} {desc:<46} x{c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
