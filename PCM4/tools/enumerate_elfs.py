#!/usr/bin/env python3
"""
Enumerate every ELF32 in app.img, fingerprint each by interpreter + keyword
presence, and locate the real /eso/bin persistence tools (whose own filename
is NOT inside them - they must be found by internal strings).
Also scans for SoC / CPU identifier strings.
Output -> enumerate_elfs_report.txt
"""
import mmap, struct, re

APP = r"D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T\MMX2\app\50\default\app.img"
REPORT = r"D:\MMI\PCM4\enumerate_elfs_report.txt"

ELF_MAGIC = b"\x7fELF\x01\x01\x01"
EM = {0x28: "ARM", 0x2A: "SH", 0x03: "x86", 0x3E: "x86-64", 0xB7: "AArch64"}

# keywords to flag inside each ELF body
KW = [b"dumb_persistence", b"VIPCmd", b"persistence", b"IPL_CONFIG",
      b"IPL", b"FecManager", b"ComponentProtection", b"ldqnx", b"libc.so"]

# SoC / CPU identifier candidates (case-insensitive search over whole image)
SOC = [b"DRA7", b"DRA74", b"DRA75", b"OMAP", b"Jacinto", b"j6", b"tegra",
       b"imx6", b"i.MX", b"R-Car", b"R8A", b"Renesas", b"TI81", b"AM57",
       b"Cortex", b"armv7", b"ARMv7", b"sh4", b"SH-4", b"vybrid", b"Sitara"]

lines = []
def log(s=""): lines.append(s)

def parse(mm, s):
    hdr = mm[s:s+0x34]
    if len(hdr) < 0x34: return None
    return dict(
        e_type=struct.unpack_from("<H", hdr, 0x10)[0],
        e_machine=struct.unpack_from("<H", hdr, 0x12)[0],
        e_entry=struct.unpack_from("<I", hdr, 0x18)[0],
        e_phoff=struct.unpack_from("<I", hdr, 0x1C)[0],
        e_shoff=struct.unpack_from("<I", hdr, 0x20)[0],
        e_flags=struct.unpack_from("<I", hdr, 0x24)[0],
        e_phentsz=struct.unpack_from("<H", hdr, 0x2A)[0],
        e_phnum=struct.unpack_from("<H", hdr, 0x2C)[0],
        e_shentsz=struct.unpack_from("<H", hdr, 0x2E)[0],
        e_shnum=struct.unpack_from("<H", hdr, 0x30)[0],
    )

def interp(body):
    m = re.search(rb"/usr/lib/ld[\w.]+\.so\.\d|/lib/ld[\w.\-]+\.so\.\d", body)
    return m.group(0).decode("ascii","replace") if m else "-"

def main():
    f = open(APP, "rb")
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    n = mm.size()

    # 1) enumerate all ELFs
    elfs = []
    pos = 0
    while True:
        i = mm.find(ELF_MAGIC, pos)
        if i == -1: break
        h = parse(mm, i)
        pos = i + 4
        if not h: continue
        if h["e_machine"] not in EM: continue
        size = max(h["e_shoff"] + h["e_shnum"]*h["e_shentsz"],
                   h["e_phoff"] + h["e_phnum"]*h["e_phentsz"])
        if size <= 0 or size > 80_000_000: continue
        elfs.append((i, size, h))
    log(f"app.img = {n:,} bytes; {len(elfs)} ELF32 found")
    log("")

    # 2) fingerprint ELFs that contain any persistence/VIPCmd keyword
    log("=== ELFs containing target keywords (candidate binaries) ===")
    interesting = []
    for off, size, h in elfs:
        body = mm[off:off+size]
        present = [k.decode() for k in KW if k in body]
        if any(x in present for x in ("dumb_persistence", "VIPCmd", "persistence", "IPL_CONFIG")):
            mach = EM.get(h["e_machine"], hex(h["e_machine"]))
            itp = interp(body)
            interesting.append((off, size, mach, itp, present))
    for off, size, mach, itp, present in interesting:
        log(f"  ELF@0x{off:08X} size={size:>10,} {mach} interp={itp}")
        log(f"       kw: {', '.join(present)}")
    log("")
    log(f"total candidate ELFs: {len(interesting)}")
    log("")

    # 3) SoC / CPU identifier scan (whole image, case-insensitive, capped)
    log("=== SoC / CPU identifier hits (first 8 each) ===")
    low = None  # build a lowercase copy lazily only if needed is heavy; do per-needle bytes
    for needle in SOC:
        hits = []
        p = 0
        nlow = needle.lower()
        # case-insensitive: search both as-is and common cases cheaply via regex on chunks is heavy;
        # just do exact + lower + upper variants
        variants = {needle, needle.lower(), needle.upper(),
                    needle[:1].upper()+needle[1:].lower()}
        for v in variants:
            q = 0
            while True:
                j = mm.find(v, q)
                if j == -1: break
                hits.append((j, v))
                q = j + 1
                if len(hits) > 200: break
            if len(hits) > 200: break
        if hits:
            hits = sorted(set(hits))[:8]
            shown = []
            for j, v in hits:
                ctx = mm[max(0,j-8):j+len(v)+18]
                ctx = re.sub(rb"[^\x20-\x7e]", b".", ctx).decode("ascii","replace")
                shown.append(f"0x{j:08X}:'{ctx}'")
            log(f"  {needle.decode():10} ({len(hits)}+): " + " | ".join(shown[:4]))
    mm.close(); f.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log("ERROR: " + repr(e)); log(traceback.format_exc())
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))
