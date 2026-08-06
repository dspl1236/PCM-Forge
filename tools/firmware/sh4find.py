#!/usr/bin/env python3
"""Find the SecurityAccess seed/key handler in PCM3Root (SH4, QNX).

The binary is stripped of section headers, so there is no symbol table to look
things up in. What it does have is trace strings -- `processDiagnosisUnlockRequest`,
`HBDiagnosisState = 0x%08X (with SecurityAccess)` -- and on SH4 a string is
reached through a PC-relative literal pool: the 4-byte address of the string sits
in a constant pool a few instructions from the code that uses it.

So: locate the string, compute its virtual address, then search the whole image
for that address as a 32-bit little-endian word. Every hit is a literal pool
entry, and the code referencing it is immediately around it. That gives us
entry points without any whole-program analysis.

    python sh4find.py                 list strings and their xrefs
    python sh4find.py --dis 0x1234    disassemble around an address
"""
import argparse
import io
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
BIN = r"D:\PCM\ifs1_rootfs\mnt\ifs1\HBproject\PCM3Root"
# --bin overrides; PCM3Reload (ifs2) is the other target -- it holds the KWP
# stack, where PCM3Root holds the HMI and DSI side.
for _i, _a in enumerate(sys.argv):
    if _a == "--bin" and _i + 1 < len(sys.argv):
        BIN = sys.argv[_i + 1]

TARGETS = [
    b"processDiagnosisUnlockRequest",
    b"HBDiagnosisState = 0x%08X (with SecurityAccess)",
    b"HBDiagnosisState = 0x%08X",
    b"requestGetHBDiagnosisState()",
    b"processHBDiagnosisStateStatus",
    b"HBDiagnosisState not initialized!",
]

data = open(BIN, "rb").read()


def elf_segments(d):
    """(offset, vaddr, filesz) for each PT_LOAD. No section headers here."""
    assert d[:4] == b"\x7fELF"
    e_phoff = struct.unpack_from("<I", d, 0x1C)[0]
    e_phentsize = struct.unpack_from("<H", d, 0x2A)[0]
    e_phnum = struct.unpack_from("<H", d, 0x2C)[0]
    out = []
    for i in range(e_phnum):
        b = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, _, p_filesz, p_memsz, p_flags, _ = \
            struct.unpack_from("<8I", d, b)
        if p_type == 1:                       # PT_LOAD
            out.append((p_offset, p_vaddr, p_filesz, p_flags))
    return out


SEGS = elf_segments(data)


def off_to_va(off):
    for o, v, sz, _ in SEGS:
        if o <= off < o + sz:
            return v + (off - o)
    return None


def va_to_off(va):
    for o, v, sz, _ in SEGS:
        if v <= va < v + sz:
            return o + (va - v)
    return None


def find_all(hay, needle):
    i, out = hay.find(needle), []
    while i != -1:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


def pc_relative_map():
    """target address -> [instruction addresses that load it]

    SH4 reaches constants through PC-relative loads:
        mov.l @(disp,PC),Rn   1101 nnnn dddddddd   -> (PC & ~3) + 4 + disp*4
        mov.w @(disp,PC),Rn   1001 nnnn dddddddd   ->  PC       + 4 + disp*2
    Scanning every 2-byte slot in the executable segment and decoding just
    these two forms gives a complete cross-reference without needing to know
    where functions begin -- which matters here because the pools are
    interleaved with code and linear disassembly keeps dying on them.
    """
    from collections import defaultdict
    out = defaultdict(list)
    for o, v, sz, fl in SEGS:
        if not (fl & 1):                       # executable only
            continue
        for i in range(0, sz - 1, 2):
            w = data[o + i] | (data[o + i + 1] << 8)
            top = w >> 12
            if top not in (0x9, 0xD):
                continue
            pc = v + i
            d = w & 0xFF
            t = ((pc & ~3) + 4 + d * 4) if top == 0xD else (pc + 4 + d * 2)
            out[t].append(pc)
    return out


def disasm(va, before=0x60, after=0xC0):
    from capstone import Cs, CS_ARCH_SH, CS_MODE_LITTLE_ENDIAN
    try:
        from capstone import CS_MODE_SH4A
        mode = CS_MODE_SH4A | CS_MODE_LITTLE_ENDIAN
    except ImportError:
        from capstone import CS_MODE_SH4
        mode = CS_MODE_SH4 | CS_MODE_LITTLE_ENDIAN
    md = Cs(CS_ARCH_SH, mode)
    md.detail = False
    start = (va - before) & ~1
    off = va_to_off(start)
    if off is None:
        print("   (address %08X not in a loaded segment)" % start)
        return
    code = data[off:off + before + after]
    for ins in md.disasm(code, start):
        mark = "  <<<" if ins.address == va else ""
        print("   %08X  %-8s %-28s%s"
              % (ins.address, ins.mnemonic, ins.op_str, mark))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", help="target ELF (default: PCM3Root)")
    ap.add_argument("--dis", help="disassemble around this hex address")
    ap.add_argument("--pool", help="dump a literal pool around this address, "
                                   "annotating what each word points at")
    ap.add_argument("--words", type=int, default=24)
    ap.add_argument("--before", type=lambda x: int(x, 0), default=0x60)
    ap.add_argument("--after", type=lambda x: int(x, 0), default=0xC0)
    a = ap.parse_args()

    if a.dis:
        disasm(int(a.dis, 0), a.before, a.after)
        return 0

    if a.pool:
        centre = int(a.pool, 0) & ~3
        start = centre - (a.words // 2) * 4
        for i in range(a.words):
            va = start + i * 4
            off = va_to_off(va)
            if off is None:
                continue
            w = struct.unpack_from("<I", data, off)[0]
            note = ""
            t = va_to_off(w)
            if t is not None:
                # printable run at the target means it is a string
                s = data[t:t + 48]
                cut = s.split(b"\x00")[0]
                if len(cut) >= 3 and all(32 <= c < 127 for c in cut):
                    note = 'str "%s"' % cut.decode("ascii", "replace")[:40]
                else:
                    for o, v, sz, fl in SEGS:
                        if fl & 1 and v <= w < v + sz:
                            note = "-> code/data %08X" % w
                            break
            elif w < 0x10000:
                note = "int %d" % w
            print("   %08X : %08X   %s%s"
                  % (va, w, note, "   <<<" if va == centre else ""))
        return 0

    print("building PC-relative xref map ...")
    pcmap = pc_relative_map()
    print("   %d distinct constant slots referenced\n" % len(pcmap))

    print("PT_LOAD segments:")
    for o, v, sz, fl in SEGS:
        print("   off %08X  vaddr %08X  size %08X  flags %s"
              % (o, v, sz, "".join(c for c, b in zip("xwr", (1, 2, 4)) if fl & b)))
    print()

    for t in TARGETS:
        offs = find_all(data, t)
        label = t.decode("ascii", "replace")
        if not offs:
            print("%-52s NOT FOUND" % label[:52])
            continue
        for off in offs:
            va = off_to_va(off)
            print("%-52s off=%08X va=%s" % (label[:52], off,
                                            "%08X" % va if va else "?"))
            if va is None:
                continue
            # literal pool entries holding this address
            xrefs = find_all(data, struct.pack("<I", va))
            shown = 0
            for x in xrefs:
                xva = off_to_va(x)
                if xva is None:
                    continue
                loaders = pcmap.get(xva, [])
                print("      literal @ %08X  loaded by: %s"
                      % (xva, " ".join("%08X" % l for l in loaders[:6])
                         or "(nothing -- may be a vtable or data table)"))
                shown += 1
                if shown >= 8:
                    print("      ... %d more" % (len(xrefs) - shown))
                    break
            if not shown:
                print("      (no literal-pool reference found)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
