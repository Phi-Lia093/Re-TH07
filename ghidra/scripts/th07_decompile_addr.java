// Decompile a specific address range of th07.exe from the Ghidra project.
//
// The C export only contains functions Ghidra recognised as such; addresses
// inside un-created regions (e.g. 0x44110d, which writes player struct fields)
// never appear there.  This script creates/disassembles the function at a
// given address and prints the decompiled C.
//
// Usage:
//   analyzeHeadless <proj> TH07 -process th07.exe -noanalysis \
//       -scriptPath ghidra/scripts -postScript th07_decompile_addr.java 0x441000 0x441200
// @category TH07

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;

public class th07_decompile_addr extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: th07_decompile_addr <startVA> <endVA>");
            return;
        }
        Address start = toAddr(Long.decode(args[0]));
        Address end = toAddr(Long.decode(args[1]));

        Function f = getFunctionContaining(start);
        if (f == null) {
            println("no function at " + start + "; trying to create one");
            disassemble(start);
            f = createFunction(start, null);
        }
        if (f == null) {
            println("could not create a function at " + start);
            return;
        }
        println("function " + f.getName() + " " + f.getEntryPoint()
                + " body=" + f.getBody().getNumAddresses());

        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        DecompileResults res = dec.decompileFunction(f, 60, monitor);
        if (!res.decompileCompleted()) {
            println("decompile failed: " + res.getErrorMessage());
            return;
        }
        println(res.getDecompiledFunction().getC());
    }
}
