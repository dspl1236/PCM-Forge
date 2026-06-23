#!/usr/bin/env python3
"""QNX Compressed-EFS (F3S) extractor — pure Python port of jtang613/qnx_dumpers
efsdump.c, adapted for LITTLE-ENDIAN dumps (ARM RCC; efsdump assumes big-endian).
Includes a pure-Python UCL NRV2B decompressor (cmptype 1) + LZO (cmptype 0).
Extracts efs-system.efs -> rcc_efs/  and reports the FEC files.
"""
import struct, os, sys
from lzo1x import decompress_stream as lzo_decompress

EFS = r"D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T\RCC\efs-system\31\default\efs-system.efs"
OUT = r"D:\MMI\PCM4\rcc_efs"
EFS_BOOTINFO_OFFSET = 40
NULL_LOGI = 0xFFFF
CMAGIC = b"iwlyfmbp"

d = open(EFS, "rb").read()
log = []
def lg(s=""): log.append(s)

# ---------- UCL NRV2B (8-bit) decompressor ----------
def ucl_nrv2b_8(src):
    out = bytearray()
    ip = 0; bb = 0; last_m_off = 1
    n = len(src)
    def getbit():
        nonlocal bb, ip
        if bb & 0x7f:
            bb <<= 1
        else:
            bb = (src[ip] << 1) | 1; ip += 1
        return (bb >> 8) & 1
    while True:
        while getbit():
            out.append(src[ip]); ip += 1
        m_off = 1
        while True:
            m_off = m_off*2 + getbit()
            if getbit(): break
        if m_off == 2:
            m_off = last_m_off
        else:
            if ip >= n: break
            m_off = (m_off - 3)*256 + src[ip]; ip += 1
            if m_off == 0xFFFFFFFF:
                break
            m_off += 1
            last_m_off = m_off
        m_len = getbit()
        m_len = m_len*2 + getbit()
        if m_len == 0:
            m_len = 1
            while True:
                m_len = m_len*2 + getbit()
                if getbit(): break
            m_len += 2
        if m_off > 0xd00:
            m_len += 1
        pos = len(out) - m_off
        if pos < 0: break
        out.append(out[pos]); pos += 1          # *op++ = *m_pos++
        while True:                              # do {...} while (--m_len > 0)
            out.append(out[pos]); pos += 1
            m_len -= 1
            if m_len <= 0: break
    return out

# ---------- EFS structures (little-endian, no swap) ----------
def u16(o): return struct.unpack_from("<H", d, o)[0]
def u32(o): return struct.unpack_from("<I", d, o)[0]

# boot info: find QSSL_F3S
sig_off = d.find(b"QSSL_F3S")
boot_off = sig_off - 4
unit_total = u16(boot_off + 14)
align_pow2 = u16(boot_off + 18)
root_logi  = u16(boot_off + 20)
root_idx   = u16(boot_off + 22)
lg(f"boot_info@0x{boot_off:X}: unit_total={unit_total} align_pow2={align_pow2} root=(logi={root_logi},idx={root_idx})")

# LITTLE-ENDIAN ARM EFS, calibrated against qconn ground truth:
#   efs_offset = 0; units fill the file; head[i] at unit_end - 32*(i+1)
#   exttype = (status byte+1) & 3   (FILE=3, DIR=2, SYS=1, XIP=0)
#   data_offset = phys*unit_size + (hi*0x10000 + lo) << align_pow2
ALIGN = 1 << align_pow2
unit_size = len(d) // unit_total
lg(f"unit_size=0x{unit_size:X}  ({unit_total} units, file=0x{len(d):X})  align={ALIGN:#x}")

HEAD_SZ = 32
def parse_head(phys, index):
    unit_end = (phys + 1) * unit_size
    o = unit_end - HEAD_SZ * (index + 1)
    if o < phys * unit_size + 64: return None
    if d[o:o+2] == b"\xff\xff": return None         # erased -> end of head array
    return dict(off=o, exttype=d[o + 1] & 3,
                hi=d[o + 19], lo=u16(o + 20), size=u16(o + 22),
                next=(u16(o + 24), u16(o + 26)))

def count_heads(phys):
    heads = []
    i = 0
    while i < 4000:
        h = parse_head(phys, i)
        if h is None: break
        heads.append(h); i += 1
    return heads

# per-physical-unit head lists; image is logical-order (logi = phys+1)
units = [count_heads(p) for p in range(unit_total)]
def phys_of(logi): return logi - 1

def data_offset(logi, hi, lo):
    return phys_of(logi)*unit_size + ((hi*0x10000 + lo) << align_pow2)

def read_dirent(logi, index):
    """A DIR head's text points to a dirent_s; return (name, mode, first)."""
    phys = phys_of(logi)
    heads = units[phys]
    if index >= len(heads): return None
    h = heads[index]
    if h["exttype"] != 2: return None      # EXTTYPE_DIR
    base = data_offset(logi, h["hi"], h["lo"])
    struct_size = u16(base)
    namelen = d[base + 3]
    first = (u16(base+4), u16(base+6))
    name_aligned = (namelen + 3) & ~3
    name = d[base+8:base+8+namelen].split(b"\x00")[0].decode("latin1")
    stat_off = base + 8 + name_aligned
    mode = u16(stat_off + 2)
    return dict(name=name, mode=mode, first=first)

def collect_file_data(logi, index):
    """Follow EXTTYPE_FILE extent chain, return concatenated raw bytes."""
    data = bytearray()
    cur = (logi, index)
    seen = set()
    while cur[0] not in (0, NULL_LOGI):
        if cur in seen: break
        seen.add(cur)
        phys = phys_of(cur[0]); heads = units[phys]
        if cur[1] >= len(heads): break
        h = heads[cur[1]]
        if h["exttype"] != 3: break        # EXTTYPE_FILE
        off = data_offset(cur[0], h["hi"], h["lo"])
        data += d[off:off + h["size"]]
        cur = h["next"]
    return bytes(data)

def decompress_efs(blob, path):
    if blob[:8] != CMAGIC:
        return blob
    usize, blksize, cmptype, flags = struct.unpack_from("<IHBB", blob, 8)
    out = bytearray()
    p = 16
    while len(out) < usize and p + 8 <= len(blob):
        prev, nxt, pusize, busize = struct.unpack_from("<HHHH", blob, p)
        if nxt == 0: break
        in_len = nxt - 8
        cdata = blob[p+8:p+8+in_len]
        if cmptype == 1:
            o = ucl_nrv2b_8(cdata)
        else:
            o, _, _ = lzo_decompress(cdata, 0)
        out += o[:busize] if busize else o
        p += nxt
    return bytes(out[:usize])

# ---------- walk ----------
os.makedirs(OUT, exist_ok=True)
stats = {"files":0, "dirs":0, "bytes":0, "compressed":0}
fec_files = []

def safe_join(path):
    parts = [x for x in path.replace("\\","/").split("/") if x not in ("","."," ","..")]
    return os.path.join(OUT, *parts) if parts else OUT

def walk(dirent, path, depth=0):
    if depth > 64: return
    first = dirent["first"]
    cur = first
    seen = set()
    while cur[0] not in (0, NULL_LOGI):
        if cur in seen: break
        seen.add(cur)
        phys = phys_of(cur[0]); heads = units[phys]
        if cur[1] >= len(heads): break
        h = heads[cur[1]]
        if h["exttype"] == 2:               # a child entry (dirent)
            child = read_dirent(cur[0], cur[1])
            if child and child["name"] not in (".","..","/",""):
                if (child["mode"] & 0xf000) == 0x4000:   # dir
                    sub = path + "/" + child["name"]
                    os.makedirs(safe_join(sub), exist_ok=True)
                    stats["dirs"] += 1
                    walk(child, sub, depth+1)
                elif (child["mode"] & 0xf000) == 0x8000: # file
                    blob = collect_file_data(child["first"][0], child["first"][1])
                    comp = blob[:8] == CMAGIC
                    data = decompress_efs(blob, child["name"]) if comp else blob
                    fp = safe_join(path + "/" + child["name"])
                    os.makedirs(os.path.dirname(fp), exist_ok=True)
                    open(fp, "wb").write(data)
                    stats["files"] += 1; stats["bytes"] += len(data)
                    if comp: stats["compressed"] += 1
                    nm = (path + "/" + child["name"]).lower()
                    if "fec" in nm or "fsc" in nm or "swap" in nm:
                        fec_files.append((path + "/" + child["name"], len(data), comp))
        cur = h["next"]

root = read_dirent(root_logi, root_idx)
lg(f"root dirent: {root}")
if root:
    walk(root, "")
lg(f"extracted: {stats}")
lg("")
lg("FEC/FSC/SWaP-related files:")
for nm, sz, c in fec_files:
    lg(f"  {nm}  ({sz} bytes){' [was compressed]' if c else ''}")

open(r"D:\MMI\PCM4\efs_extract_report.txt","w",encoding="utf-8").write("\n".join(log))
try: print("\n".join(log))
except Exception: print("written to efs_extract_report.txt")
