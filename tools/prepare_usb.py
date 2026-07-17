#!/usr/bin/env python3
"""
PCM-Forge: build the USB activation payload for a Porsche PCM 3.1.

Generates PagSWAct.002 (the feature-activation record set for YOUR VIN) plus a
Unix-LF copie_scr.sh autorun, ready to copy to a FAT32 USB root. This is the
host-side packager around the activation-code algorithm; the code math itself is
in ../generate_codes.py (published separately).

Usage:
    python prepare_usb.py <VIN> [feature ...]

    <VIN>       your 17-char vehicle VIN (required; not stored in this repo)
    feature     optional subset of: ENGINEERING BTH KOMP  (default: all three)

Example:
    python prepare_usb.py WP1ZZZ00ZZZ00000 ENGINEERING BTH

Then copy BOTH PagSWAct.002 and copie_scr.sh to the USB root and insert it into
the PCM after it has booted. For research/personal use on your own vehicle only.
"""
import struct, os, sys

# Activation RSA parameters (public: see ../generate_codes.py and research/ALGORITHM_CRACKED.md)
N, D = 0x69f39c927ef94985, 0x5483975015d0287b

# feature name -> (feature-hex, swID, subID)
ALL_FEATS = {
    "ENGINEERING": ("010b0000", 0x010b, 0),
    "BTH":         ("010a0000", 0x010a, 0),
    "KOMP":        ("01060000", 0x0106, 0),
}

def vin2num(vin):
    vl = vin.lower()
    r, w = 0, 10
    for p in [16, 15, 14, 13, 12, 11, 9, 7]:
        c = vl[p]
        b = int(c) if c.isdigit() else ord(c) % 10
        r = (r + b * w) & 0xFFFFFFFF
        w = (w * 10) & 0xFFFF
    return r

def gen(vin, fh):
    vh = f"{vin2num(vin):08x}"
    pt = int(''.join(fh[i] + vh[i] for i in range(8)), 16)
    return f"{pow(pt, D, N):016x}"

def main(argv):
    if not argv:
        sys.exit(__doc__)
    vin = argv[0].strip().upper()
    if len(vin) != 17:
        sys.exit(f"error: VIN must be 17 characters (got {len(vin)})")
    names = [a.upper() for a in argv[1:]] or list(ALL_FEATS)
    for n in names:
        if n not in ALL_FEATS:
            sys.exit(f"error: unknown feature '{n}' (choose from {', '.join(ALL_FEATS)})")

    here = os.path.dirname(os.path.abspath(__file__))
    print(f"\n  VIN: {vin}\n")
    data = bytearray()
    for name in names:
        fh, swid, subid = ALL_FEATS[name]
        code = gen(vin, fh)
        rec = bytearray(28)
        for i, c in enumerate(code[:16]):
            rec[i] = ord(c)
        struct.pack_into('<H', rec, 18, swid)
        struct.pack_into('<H', rec, 20, subid)
        rec[22] = 1
        struct.pack_into('<I', rec, 24, 1)
        data.extend(rec)
        print(f"  {name:<15s}: {code}")

    pagswact = os.path.join(here, "PagSWAct.002")
    with open(pagswact, 'wb') as f:
        f.write(data)
    print(f"\n  Written: PagSWAct.002 ({len(data)} bytes)")

    # copie_scr.sh autorun -- MUST be Unix LF (a CRLF shebang fails on QNX ksh)
    script = (
        "#!/bin/ksh\n"
        "# PCM-Forge - https://github.com/dspl1236/PCM-Forge\n"
        "for USBPATH in /fs/usb0 /fs/usb1 /fs/usb /media/usb0; do\n"
        '    [ -f "${USBPATH}/PagSWAct.002" ] && break\n'
        "done\n"
        '[ -f "${USBPATH}/PagSWAct.002" ] && cp "${USBPATH}/PagSWAct.002" /HBpersistence/PagSWAct.002\n'
        "touch /HBpersistence/DBGModeActive\n"
        "sync\n"
    )
    copie = os.path.join(here, "copie_scr.sh")
    with open(copie, 'wb') as f:
        f.write(script.encode('ascii'))
    print(f"  Created: copie_scr.sh ({len(script)} bytes, LF)")
    print(f"\n  Copy BOTH files to a FAT32 USB root, insert into the PCM.\n")

if __name__ == '__main__':
    main(sys.argv[1:])
