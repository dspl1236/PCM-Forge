#!/usr/bin/env python3
"""Full decompress of ifs-root.ifs imagefs (BE16 length-prefixed LZO1X blocks),
then walk the QNX image directory and extract every file. Reports the boot
script + inetd.conf (the qconn autostart answer)."""
import struct, os
from lzo1x import decompress_stream

P = r"D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T\RCC\ifs-root\31\default\ifs-root.ifs"
OUTDIR = r"D:\MMI\PCM4\rcc_rootfs"
IMGBIN = r"D:\MMI\PCM4\rcc_ifs-root_imagefs.bin"
data = open(P, "rb").read()
rep=[]
def log(s=""): rep.append(s)

IMG = 0x22110
IMAGEFS_SIZE = 0xE86908
STORED_END = 0x8 + 0x65DC08

# ---- decompress all blocks ----
imagefs = bytearray()
pos = IMG
nblk = 0
while pos + 2 <= len(data) and len(imagefs) < IMAGEFS_SIZE:
    clen = (data[pos] << 8) | data[pos+1]   # BE16
    if clen == 0:
        break
    seg = data[pos+2:pos+2+clen]
    o, ip, reason = decompress_stream(seg, 0)
    imagefs += o
    nblk += 1
    pos += 2 + clen
    if reason.startswith("error"):
        log(f"block {nblk} @0x{pos:X} decode {reason} (out so far {len(imagefs)})")
        break
log(f"decompressed {nblk} blocks -> {len(imagefs):,} bytes (expected {IMAGEFS_SIZE:,})")
open(IMGBIN, "wb").write(imagefs)
log(f"saved imagefs -> {IMGBIN}")
log("")

o = imagefs
sig = bytes(o[0:7])
image_size = struct.unpack_from("<I", o, 0x08)[0]
dir_offset = struct.unpack_from("<I", o, 0x10)[0]
log(f"image sig={sig!r} image_size=0x{image_size:X} dir_offset=0x{dir_offset:X}")

# ---- walk directory & extract ----
def safe(path):
    path = path.replace("\\", "/").lstrip("/")
    parts = [p for p in path.split("/") if p not in ("", ".", "..")]
    return os.path.join(OUTDIR, *parts) if parts else None

p = dir_offset
files=0; dirs=0; links=0; nf=0
extracted=[]
while p + 0x20 < len(o):
    size = struct.unpack_from("<H", o, p)[0]
    if size == 0 or size > 0x1000:
        break
    mode = struct.unpack_from("<I", o, p+8)[0]
    ft = mode & 0xF000
    try:
        if ft == 0x8000:  # file
            foff = struct.unpack_from("<I", o, p+0x18)[0]
            fsz  = struct.unpack_from("<I", o, p+0x1C)[0]
            name = bytes(o[p+0x20:p+size]).split(b"\x00")[0].decode("ascii","replace")
            files += 1
            dest = safe(name)
            if dest and foff+fsz <= len(o):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                open(dest, "wb").write(o[foff:foff+fsz])
                extracted.append((name, fsz))
        elif ft == 0x4000:
            dirs += 1
        elif ft == 0xA000:
            links += 1
    except Exception as e:
        log(f"entry @0x{p:X} err {e!r}")
    p += size
    nf += 1

log(f"walked {nf} entries: {files} files, {dirs} dirs, {links} links; extracted {len(extracted)}")
log("")

# ---- the key answers ----
def cat(relpath, limit=2600):
    dest = safe(relpath)
    if dest and os.path.exists(dest):
        b = open(dest,"rb").read()
        txt = "".join(chr(c) if 9<=c<127 else "." for c in b[:limit])
        return txt
    return "(not found)"

log("="*60)
log("proc/boot/.script  (QNX boot init — qconn/io-pkt autostart):")
log("="*60)
log(cat("proc/boot/.script"))
log("")
log("="*60)
log("etc/inetd.conf  (r-services):")
log("="*60)
log(cat("etc/inetd.conf"))

open(r"D:\MMI\PCM4\ifs_extract_report.txt","w",encoding="utf-8").write("\n".join(rep))
try: print("\n".join(rep))
except Exception: print("written to ifs_extract_report.txt")
