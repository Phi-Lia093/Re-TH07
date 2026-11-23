# Re-TH07

Original game data and working files for the Touhou 7 (Perfect Cherry Blossom)
reverse-engineering effort.

**The analysis itself has moved.** The documentation, symbol tables, and format
tools now live in the remake repository, which is where the work continues:

    D:\OpenSTG\th07-remake\docs\      reverse-engineering documents
    D:\OpenSTG\th07-remake\tools\     format readers / parsers
    D:\OpenSTG\th07-remake\ghidra\    recovered symbol tables

## What is left in this repository

| Item | Purpose |
|------|---------|
| `th07.exe` | The original game binary (not committed) |
| `th07.dat`, `thbgm.dat` | Original data archives (not committed) |
| `th07.exe.c` | Ghidra decompilation output, 87k lines (not committed) |
| `work/th07_dat/` | Extracted game data (not committed) |
| `work/shots/` | Screenshots used to verify layout |
| `work/func_profile.json` | Per-function profile used during analysis |

Everything binary here is copyrighted and gitignored. This directory exists so
the conversion tools have source data to read; it is not the project.

## Where to go

Start at `D:\OpenSTG\README.md`, then `D:\OpenSTG\th07-remake\docs\INDEX.md`.
