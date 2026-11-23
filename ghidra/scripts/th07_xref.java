// Find every call site of a function, and cross-reference draw primitives.
//
// TH07's renderer funnels all sprite drawing through DrawPrimitiveUP on
// DAT_00575958.  The goal here is to walk from a UI-related function back to
// the code that issues those draws, so each interface's layout constants
// (positions, sizes) can be read off.
//
// Two modes:
//   xref <addr>        list callers of a function address
//   drawcallers        list functions that contain a DrawPrimitiveUP dispatch
//
// @category TH07

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class th07_xref extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: th07_xref <xref|drawcallers> [addr]");
            return;
        }
        if (args[0].equals("xref")) {
            Address target = toAddr(Long.decode(args[1]));
            println("callers of " + target);
            ReferenceIterator it =
                currentProgram.getReferenceManager().getReferencesTo(target);
            int n = 0;
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                println("  " + r.getFromAddress() + " in "
                        + (f != null ? f.getName() : "(none)")
                        + " type=" + r.getReferenceType());
                if (++n > 60) break;
            }
            println("total " + n);
            return;
        }
        // drawcallers: find functions that dispatch through a vtable slot.
        println("functions containing indirect vtable calls:");
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int shown = 0;
        while (fit.hasNext() && shown < 40) {
            Function f = fit.next();
            int calls = 0;
            InstructionIterator iit =
                currentProgram.getListing().getInstructions(f.getBody(), true);
            while (iit.hasNext()) {
                Instruction i = iit.next();
                String s = i.toString();
                if (s.contains("call dword ptr [") && s.contains("*4")) {
                    calls++;
                }
            }
            if (calls > 0) {
                println("  " + f.getName() + " @ " + f.getEntryPoint()
                        + "  vtable calls=" + calls);
                shown++;
            }
        }
    }
}
