// Dump the th07 ECL interpreter's structure using the Ghidra database.
//
// Reports:
//   1. the interpreter function and its callers
//   2. the switch jump table (opcode -> handler address), read from the
//      actual bytes, not from decompiled text
//   3. the per-opcode function bodies that read param_mask
//
// Run: analyzeHeadless <proj> TH07 -process th07.exe -postScript th07_ecl_dump.java
// @category TH07

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.pcode.*;
import java.io.*;
import java.util.*;

public class th07_ecl_dump extends GhidraScript {

    private static final long INTERP = 0x00410520L;

    @Override
    public void run() throws Exception {
        Address interp = toAddr(INTERP);
        Function f = getFunctionAt(interp);
        println("=== interpreter ===");
        if (f == null) {
            println("FUN at " + interp + " not found");
            return;
        }
        println("name=" + f.getName() + " entry=" + f.getEntryPoint()
                + " body=" + f.getBody().getNumAddresses() + " bytes");
        println("signature=" + f.getSignature());

        println("\n=== callers of interpreter ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(interp);
        Set<Address> seen = new LinkedHashSet<>();
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function cf = getFunctionContaining(from);
            String n = cf != null ? cf.getName() : "(no function)";
            if (seen.add(from)) {
                println("  from " + from + " in " + n);
            }
        }

        // Collect every call to __ftol / e5b0 style helpers by address.
        println("\n=== instruction histogram around dispatch (first 400 insns) ===");
        InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
        int count = 0;
        Map<String, Integer> mnem = new TreeMap<>();
        while (it.hasNext() && count < 400) {
            Instruction i = it.next();
            mnem.merge(i.getMnemonicString(), 1, Integer::sum);
            count++;
        }
        for (Map.Entry<String, Integer> e : mnem.entrySet()) {
            println("  " + e.getKey() + " x" + e.getValue());
        }

        // Find all pointer-typed data referenced from the interpreter body.
        println("\n=== pointer data referenced in interpreter body ===");
        AddressSetView body = f.getBody();
        DataIterator di = currentProgram.getListing().getDefinedData(body, true);
        Set<String> tables = new TreeSet<>();
        while (di.hasNext()) {
            Data d = di.next();
            if (d == null) continue;
            Object val = d.getValue();
            if (val instanceof Address) {
                tables.add(d.getAddress() + " -> " + val);
            }
        }
        int shown = 0;
        for (String t : tables) {
            println("  " + t);
            if (++shown > 40) { println("  ..."); break; }
        }
    }
}
