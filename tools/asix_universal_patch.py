#!/usr/bin/env python3
"""
asix_universal_patch.py  —  build a universal HN+ devn-asix driver.

Activates the dormant AX88772B init path in a *772B-capable* HN+ devn-asix.so
(io-net, SH4) so it recognizes AX88772B/772C adapters (USB 0b95:772b) and runs
Harman's own ax_enable_88772B setup (correct TX/medium-mode init + real MAC read).

It repurposes the obsolete AX88172 (0b95:1720) table row, so AX88772 / 772A and
the 88178 / Linksys-NetGear rebadge entries are all KEPT. Result:
    772 / 772A / 772B / 772C  (loses only the USB-1.1 88172)

INPUT must be a 772B-capable build (one that contains ax_enable_88772B, e.g.
extracted from MU9498 / 8R0906961FE or FB firmware). Older builds (772/772A only)
have no 772B code to activate — the script refuses them.

Usage:
    python asix_universal_patch.py <devn-asix.so> [-o devn-asix-universal.so]

No external deps. Right-to-repair / owner-diagnostics use.
"""
import sys, struct, argparse

CHIP_772B = 0x0088772b   # chip-type value ax_configuration checks -> ax_enable_88772B

def main(argv=None):
    ap = argparse.ArgumentParser(description="Activate universal 772B support in an HN+ devn-asix.so")
    ap.add_argument("input", help="772B-capable devn-asix.so (io-net SH4)")
    ap.add_argument("-o", "--output", default="devn-asix-universal.so")
    args = ap.parse_args(argv)

    b = bytearray(open(args.input, "rb").read())

    # sanity: must be a 772B-capable build
    if b[:7] != b"\x7fELF\x01\x01\x01":
        sys.exit("Not an ELF.")
    has_772b_code = (b.find(b"ax_enable_88772B") >= 0) or (b.find(struct.pack("<I", CHIP_772B)) >= 0)
    if not has_772b_code:
        sys.exit("Input has no AX88772B support (no ax_enable_88772B). Use a later build "
                 "(MU9498 / 8R0906961FE/FB). Nothing to activate.")

    # find the match table: contiguous 16-byte rows starting with VID 0x0b95.
    import re
    rows = [m.start() for m in re.finditer(b"\x95\x0b\x00\x00", b)]
    # the table is the run where rows are 16 bytes apart; locate the AX88172 row (DID 0x1720)
    tgt = None
    for o in rows:
        if struct.unpack_from("<H", b, o + 4)[0] == 0x1720 and \
           struct.unpack_from("<I", b, o + 8)[0] == 0x00088172:
            tgt = o
            break
    if tgt is None:
        sys.exit("Could not find the AX88172 (0b95:1720) table row to repurpose.")

    before = bytes(b[tgt:tgt + 16])
    struct.pack_into("<H", b, tgt + 4, 0x772b)        # DID  -> 0x772b
    struct.pack_into("<I", b, tgt + 8, CHIP_772B)     # chip-type -> 772B (routes to ax_enable_88772B)
    struct.pack_into("<I", b, tgt + 12, 0x000000b0)   # field -> 0xb0 (match 772 family)
    after = bytes(b[tgt:tgt + 16])

    open(args.output, "wb").write(b)
    print("AX88172 row @file 0x%X:" % tgt)
    print("  before: %s" % before.hex())
    print("  after : %s   (0b95:772b, chiptype 0x0088772b -> ax_enable_88772B)" % after.hex())
    print("Wrote %s (%d bytes). Supports 772 / 772A / 772B / 772C." % (args.output, len(b)))

if __name__ == "__main__":
    main()
