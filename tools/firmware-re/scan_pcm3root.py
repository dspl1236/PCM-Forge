#!/usr/bin/env python3
# ============================================================================
# scan_pcm3root.py -- find the universal BT/FM-boot signature in a PCM3Root
# binary and report the exact patch verdict, mirroring bt_fix.c's on-car
# algorithm offline. Pure Python, no dependencies, cross-platform.
#
# The AUX/BT "defaults to FM on startup" bug is one instruction that stores the
# FM source-index (1) into the BT source descriptor. It carries a unique 6-byte
# signature (byte-identical across every region/model/facelift build that has
# the bug); the byte to flip is the 0x01 at signature+2 -> 0x07 (A2DP).
#
#   PATCH            one match, index byte 0x01 (FM)  -> bt_fix flips it to 0x07
#   ALREADY-PATCHED  one match, index byte 0x07 (A2DP)
#   NO-OP (safe)     zero matches (e.g. v1.00, which predates the fallback code)
#   ABORT            >1 match or an unexpected byte -> bt_fix refuses to write
#
# Usage:  python scan_pcm3root.py <PCM3Root> [<PCM3Root> ...]
#   (extract PCM3Root from a firmware IFS first with carve_pcm3root.py)
# ============================================================================
import struct, sys

SIG = bytes.fromhex('051e01e1151e')   # mov.l r?,@(5,Rn); mov #1,r1; mov.l r1,@(5,Rn)
IMM = 2                                # the FM/A2DP index byte inside the signature

def off_to_vaddr(d):
    """Map a file offset to its ELF virtual address via the PT_LOAD segments."""
    e_phoff = struct.unpack_from('<I', d, 0x1c)[0]
    ents, num = struct.unpack_from('<HH', d, 0x2a)
    segs = []
    for i in range(num):
        o = e_phoff + i * ents
        if o + 20 > len(d):
            break
        t, p_off, p_vaddr, p_paddr, p_filesz = struct.unpack_from('<IIIII', d, o)
        if t == 1:  # PT_LOAD
            segs.append((p_off, p_vaddr, p_filesz))
    return lambda off: next((pv + (off - po) for po, pv, fs in segs if po <= off < po + fs), None)

def scan(path):
    d = open(path, 'rb').read()
    hits, i = [], 0
    while True:
        j = d.find(SIG, i)
        if j < 0:
            break
        hits.append(j)
        i = j + 1
    if len(hits) == 0:
        return ('NO-OP (0 matches, safe)', None, None)
    if len(hits) > 1:
        return ('ABORT (>1 match)', None, None)
    off = hits[0] + IMM
    cur = d[off]
    try:
        va = off_to_vaddr(d)(off)
    except Exception:
        va = None
    if cur == 0x01:
        return ('PATCH (flip 01->07)', va, cur)
    if cur == 0x07:
        return ('ALREADY-PATCHED (07)', va, cur)
    return ('ABORT (byte=0x%02x)' % cur, va, cur)

def main(argv):
    if not argv:
        sys.exit('usage: python scan_pcm3root.py <PCM3Root> [<PCM3Root> ...]')
    import os
    print('%-38s %-22s %-12s %s' % ('binary', 'verdict', 'FM-map addr', 'byte'))
    print('-' * 82)
    for p in argv:
        verdict, va, cur = scan(p)
        print('%-38s %-22s %-12s %s' % (
            os.path.basename(p), verdict,
            hex(va) if va else '-', hex(cur) if cur is not None else '-'))

if __name__ == '__main__':
    main(sys.argv[1:])
