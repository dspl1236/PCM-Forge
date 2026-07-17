# Ghidra post-script: decompile the KeyInput code region so the DSI subscribe/notify calls
# (which carry the updateId as a constant arg, reached via vtable indirection the decompiler follows)
# become readable. @runtime Jython
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory().getDefaultAddressSpace()
def A(x): return af.getAddress(x)
deci = DecompInterface(); deci.openProgram(currentProgram)
mon = ConsoleTaskMonitor()

# KeyInput PresCtrl / BitSausageInterpreter / send funcs cluster here (0x83aa000-0x83ac000)
lo, hi = A(0x083aa000), A(0x083ac000)
funcs = []
it = fm.getFunctions(lo, True)
while it.hasNext():
    f = it.next()
    if f.getEntryPoint().compareTo(hi) > 0: break
    funcs.append(f)
print("REGION functions: %d" % len(funcs))

n = 0
for f in funcs:
    try:
        r = deci.decompileFunction(f, 45, mon)
        c = r.getDecompiledFunction().getC() if (r and r.getDecompiledFunction()) else "(decomp failed)"
    except Exception as ex:
        c = "(exc %s)" % ex
    print("==== %s @ %s ====" % (f.getName(), f.getEntryPoint()))
    print(c)
    n += 1
    if n >= 40: break
print("==== DONE %d ====" % n)
