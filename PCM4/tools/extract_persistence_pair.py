#!/usr/bin/env python3
"""Extract the two adjacent dumb_persistence ELFs, assign reader/writer by
their internal strings, and dump distinctive strings for confirmation."""
import mmap, struct, re

APP = r"D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T\MMX2\app\50\default\app.img"
OUT = r"D:\MMI\PCM4\binaries"
REPORT = r"D:\MMI\PCM4\persistence_pair_report.txt"
CANDS = [0x1E2D4C00, 0x1E307400]

def parse(mm, s):
    hdr = mm[s:s+0x34]
    return dict(
        e_phoff=struct.unpack_from("<I", hdr, 0x1C)[0],
        e_shoff=struct.unpack_from("<I", hdr, 0x20)[0],
        e_phentsz=struct.unpack_from("<H", hdr, 0x2A)[0],
        e_phnum=struct.unpack_from("<H", hdr, 0x2C)[0],
        e_shentsz=struct.unpack_from("<H", hdr, 0x2E)[0],
        e_shnum=struct.unpack_from("<H", hdr, 0x30)[0],
        e_entry=struct.unpack_from("<I", hdr, 0x18)[0],
    )

def strs(body, minlen=5):
    return [m.decode("ascii","replace") for m in re.findall(rb"[\x20-\x7e]{%d,}" % minlen, body)]

lines = []
def log(s=""): lines.append(s)

f = open(APP, "rb"); mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
for off in CANDS:
    h = parse(mm, off)
    size = max(h["e_shoff"]+h["e_shnum"]*h["e_shentsz"],
               h["e_phoff"]+h["e_phnum"]*h["e_phentsz"])
    body = mm[off:off+size]
    has_reader = b"dumb_persistence_reader" in body
    has_writer = b"dumb_persistence_writer" in body
    name = ("dumb_persistence_reader" if has_reader and not has_writer
            else "dumb_persistence_writer" if has_writer and not has_reader
            else f"dumb_persistence_BOTH_{off:08X}")
    path = OUT + "\\" + name + ".elf"
    open(path, "wb").write(body)
    log(f"=== ELF@0x{off:08X} size={size:,} entry=0x{h['e_entry']:08X} ===")
    log(f"  reader_str={has_reader} writer_str={has_writer} -> {name}.elf")
    # distinctive strings: usage, options, persistence, eso paths
    S = strs(body)
    pick = [s for s in S if re.search(r"usage|Usage|option|invalid|partition|offset|"
            r"persist|/eso/|IPL|-P\b|reader|writer|len|VERSION|version|\bUTF", s)]
    seen = set(); uniq = []
    for s in pick:
        if s not in seen:
            seen.add(s); uniq.append(s)
    for s in uniq[:40]:
        log("    | " + s)
    log("")
mm.close(); f.close()
open(REPORT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
