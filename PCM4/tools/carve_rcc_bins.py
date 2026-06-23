#!/usr/bin/env python3
"""Carve ELF binaries (qconn, telnetd, pdebug, the 'on' cmd) from efs-system.efs.
efs-system stores file contents uncompressed, so ELFs are carvable by header."""
import struct, re, os

EFS = r"D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T\RCC\efs-system\31\default\efs-system.efs"
OUT = r"D:\MMI\PCM4\binaries"
data = open(EFS, "rb").read()
out=[]
def log(s=""): out.append(s)

def parse(s):
    if data[s:s+7] != b"\x7fELF\x01\x01\x01": return None
    try:
        e_machine=struct.unpack_from("<H",data,s+0x12)[0]
        e_phoff=struct.unpack_from("<I",data,s+0x1C)[0]
        e_shoff=struct.unpack_from("<I",data,s+0x20)[0]
        e_phentsz=struct.unpack_from("<H",data,s+0x2A)[0]
        e_phnum=struct.unpack_from("<H",data,s+0x2C)[0]
        e_shentsz=struct.unpack_from("<H",data,s+0x2E)[0]
        e_shnum=struct.unpack_from("<H",data,s+0x30)[0]
    except struct.error:
        return None
    size=max(e_shoff+e_shnum*e_shentsz, e_phoff+e_phnum*e_phentsz)
    return e_machine, size

# find all ELFs
elfs=[]; pos=0
while True:
    j=data.find(b"\x7fELF\x01\x01\x01", pos)
    if j==-1: break
    pos=j+4
    info=parse(j)
    if not info: continue
    mach,size=info
    if 0<size<8_000_000 and mach in (0x28,0xB7,0x2A):
        # nearest readable name token before header (within 64 bytes)
        pre=data[max(0,j-64):j]
        names=re.findall(rb"[a-zA-Z][a-zA-Z0-9_.\-]{2,30}", pre)
        nm=names[-1].decode() if names else "?"
        elfs.append((j,size,mach,nm))

log(f"efs-system.efs: {len(data):,} bytes; {len(elfs)} carvable ELF(s)")
for j,size,mach,nm in elfs:
    log(f"  ELF@0x{j:08X} size={size:>9,} mach=0x{mach:X} preName='{nm}'")
log("")

WANT = {"qconn","telnetd","pdebug","on","io-pkt","io-pkt-v6-hc","inetd"}
for j,size,mach,nm in elfs:
    base=nm.split(".")[0]
    if base in WANT or nm in WANT:
        body=data[j:j+size]
        # confirm with internal string
        path=os.path.join(OUT, f"rcc_{base}.elf")
        open(path,"wb").write(body)
        # quick identity strings
        has=[k for k in (b"qconn",b"telnet",b"pdebug",b"PDEBUG",b"io-pkt") if k in body]
        log(f"  carved {path} ({size:,}B) ids={[h.decode() for h in has]}")
log("")
log("note: also listing ELFs whose BODY contains qconn/telnet even if preName missed:")
for j,size,mach,nm in elfs:
    body=data[j:j+size]
    if b"qconn" in body or b"in.telnetd" in body:
        log(f"  ELF@0x{j:08X} size={size:,} contains qconn/telnetd markers (preName='{nm}')")

open(r"D:\MMI\PCM4\carve_rcc_report.txt","w",encoding="utf-8").write("\n".join(out))
try: print("\n".join(out))
except Exception: print("(report written to carve_rcc_report.txt)")
