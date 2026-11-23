// Apply a symbol/comment mapping back into the Ghidra database.
//
// This is the write-back half of the "read all 90k lines" workflow: analysis
// notes are kept in a versioned text file (ghidra/symbols/*.txt), and this
// script pushes them into the project so the decompiler emits real names on
// the next export.
//
// File format (one entry per line, `#` starts a comment):
//     FUN_00410520  ecl_run_interpreter     interpreter main loop
//     DAT_00575954  g_d3d8                   IDirect3D8*
//     LAB_00411f00  ecl_cond_jump
// The third column is optional and becomes the function's comment.
//
// Usage:
//   analyzeHeadless <proj> TH07 -process th07.exe -noanalysis \
//     -scriptPath ghidra/scripts -postScript th07_apply_symbols.java symbols.txt
// @category TH07

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class th07_apply_symbols extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: th07_apply_symbols <symbols.txt>");
            return;
        }
        File f = new File(args[0]);
        if (!f.isAbsolute()) {
            f = new File(currentProgram.getExecutablePath()).getParentFile() == null
                ? f : new File(System.getProperty("user.dir"), args[0]);
        }
        if (!f.exists()) {
            println("ERROR: " + f.getAbsolutePath() + " not found");
            return;
        }
        SymbolTable st = currentProgram.getSymbolTable();
        Listing listing = currentProgram.getListing();
        int renamed = 0, commented = 0, skipped = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                // split into at most 3 fields: addr, name, comment
                String[] parts = line.split("\\s+", 3);
                if (parts.length < 2) {
                    skipped++;
                    continue;
                }
                // The address column may be written as FUN_xxxxxxxx / DAT_xxxxxxxx
                // (how the decompiler names things) rather than a bare number,
                // so extract the hex part rather than relying on toAddr's own
                // symbol lookup -- that returns null for names it has not
                // seen, which silently skipped whole files.
                String addrText = parts[0];
                int us = addrText.indexOf('_');
                if (us > 0 && addrText.matches("^[A-Z]+_[0-9a-fA-F]{8}$")) {
                    addrText = addrText.substring(us + 1);
                }
                Address addr;
                try {
                    addr = toAddr(Long.parseLong(addrText, 16));
                } catch (Exception e) {
                    println("SKIP unparsable address: " + parts[0]);
                    skipped++;
                    continue;
                }
                if (addr == null || !addr.isMemoryAddress()) {
                    println("SKIP non-memory address: " + parts[0]);
                    skipped++;
                    continue;
                }
                String newName = parts[1];
                String comment = parts.length > 2 ? parts[2] : null;

                String kind = parts[0].startsWith("FUN") ? "FUN" : "DATA";
                if (kind.equals("FUN")) {
                    Function fn = getFunctionAt(addr);
                    if (fn == null) {
                        fn = createFunction(addr, null);
                    }
                    if (fn != null) {
                        fn.setName(newName, SourceType.USER_DEFINED);
                        renamed++;
                        if (comment != null) {
                            fn.setComment(comment);
                            commented++;
                        }
                    } else {
                        skipped++;
                    }
                } else {
                    try {
                        st.createLabel(addr, newName, SourceType.USER_DEFINED);
                        renamed++;
                    } catch (Exception e) {
                        skipped++;
                        continue;
                    }
                    if (comment != null) {
                        listing.setComment(addr, CodeUnit.EOL_COMMENT, comment);
                        commented++;
                    }
                }
            }
        }
        println("APPLY renamed=" + renamed + " commented=" + commented
                + " skipped=" + skipped);
    }
}
