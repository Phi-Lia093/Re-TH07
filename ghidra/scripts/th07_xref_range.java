// Find code that references a data address, following the th07 idiom where
// strings sit in a table and code loads them via `lea` on a table base.
//
// Prints every function containing an instruction that references any address
// in [start, start+len), plus the surrounding decompilation of the best hit.
//
// Usage: -postScript th07_xref_range.java 0x496b00 0x200
// @category TH07

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class th07_xref_range extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        long start = Long.decode(args[0]);
        long len = Long.decode(args[1]);
        AddressSet range = new AddressSet(toAddr(start), toAddr(start + len));

        ReferenceIterator it =
            currentProgram.getReferenceManager().getReferenceIterator(range.getMinAddress());
        int shown = 0;
        java.util.Set<Function> fns = new java.util.LinkedHashSet<>();
        while (it.hasNext() && shown < 400) {
            Reference r = it.next();
            if (!range.contains(r.getToAddress())) {
                continue;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            if (f != null) {
                fns.add(f);
            }
            shown++;
        }
        println("references into range: " + shown + ", functions: " + fns.size());
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        int n = 0;
        for (Function f : fns) {
            println("\n=== " + f.getName() + " @ " + f.getEntryPoint()
                    + " size=" + f.getBody().getNumAddresses());
            DecompileResults res = dec.decompileFunction(f, 45, monitor);
            if (res.decompileCompleted()) {
                String c = res.getDecompiledFunction().getC();
                if (c.length() > 6000) {
                    c = c.substring(0, 6000) + "\n... [truncated]";
                }
                println(c);
            }
            if (++n >= 3) {
                break;
            }
        }
    }
}
