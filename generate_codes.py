#!/usr/bin/env python3
"""
PCM-Forge: Porsche PCM 3.1 Activation Code Generator
https://github.com/dspl1236/PCM-Forge

Usage:
  python generate_codes.py <VIN>
  python generate_codes.py <VIN> <USB_PATH>
"""
import struct, sys, os

N = 0x69f39c927ef94985
E = 0x4c1c5eeaf397c0b3
D = 0x5483975015d0287b

FEATURES = [
    ("ENGINEERING", "010b0000", 0x010b, 0x0000, "Engineering & diagnostic menu"),
    ("BTH",         "010a0000", 0x010a, 0x0000, "Bluetooth telephony"),
    ("KOMP",        "01060000", 0x0106, 0x0000, "Component activation"),
]

def vin_to_number(vin):
    vl = vin.lower()
    positions = [7, 9, 11, 12, 13, 14, 15, 16]
    result, weight = 0, 10
    for pos in reversed(positions):
        c = vl[pos]
        b = int(c) if c.isdigit() else (ord(c) % 10 if c.islower() else 0)
        result = (result + b * weight) & 0xFFFFFFFF
        weight = (weight * 10) & 0xFFFF
    return result

def interleave(a, b):
    return ''.join(a[i] + b[i] for i in range(8))

def generate_code(vin, feat_hex):
    vh = f"{vin_to_number(vin):08x}"
    pt = int(interleave(feat_hex, vh), 16)
    return f"{pow(pt, D, N):016x}"

def verify_code(vin, code_hex, feat_hex):
    pt = pow(int(code_hex, 16), E, N)
    pt_hex = f"{pt:016x}"
    af = ''.join(pt_hex[i] for i in range(0, 16, 2))
    av = ''.join(pt_hex[i] for i in range(1, 16, 2))
    return af == feat_hex and av == f"{vin_to_number(vin):08x}"

def build_pagswact(vin, features):
    data = bytearray()
    for name, feat_hex, swid, subid, desc in features:
        code = generate_code(vin, feat_hex)
        rec = bytearray(28)
        for i, c in enumerate(code[:16]):
            rec[i] = ord(c)
        struct.pack_into('<H', rec, 18, swid)
        struct.pack_into('<H', rec, 20, subid)
        rec[22] = 1
        struct.pack_into('<I', rec, 24, 1)
        data.extend(rec)
    return bytes(data)

COPIE_SCR = """#!/bin/ksh
# PCM-Forge activation — https://github.com/dspl1236/PCM-Forge
for USBPATH in /fs/usb0 /fs/usb1 /fs/usb /media/usb0; do
    [ -f "${USBPATH}/PagSWAct.002" ] && break
done
[ -f "${USBPATH}/PagSWAct.002" ] && cp "${USBPATH}/PagSWAct.002" /HBpersistence/PagSWAct.002
touch /HBpersistence/DBGModeActive
sync
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_codes.py <VIN> [USB_PATH]")
        print("  VIN       17-digit Porsche VIN")
        print("  USB_PATH  Optional: write files directly to USB drive (e.g. E:\\)")
        sys.exit(1)

    vin = sys.argv[1].upper()
    usb_path = sys.argv[2] if len(sys.argv) > 2 else None

    if len(vin) != 17:
        print(f"Error: VIN must be 17 characters (got {len(vin)})"); sys.exit(1)

    print(f"\n  PCM-Forge: Porsche PCM 3.1 Activation")
    print(f"  VIN: {vin}\n")

    for name, feat_hex, swid, subid, desc in FEATURES:
        code = generate_code(vin, feat_hex)
        ok = verify_code(vin, code, feat_hex)
        print(f"  {name:<15s}: {code}  {'✓' if ok else '✗'}")

    out = usb_path if usb_path else "."
    pagswact_path = os.path.join(out, "PagSWAct.002")
    copie_path = os.path.join(out, "copie_scr.sh")

    with open(pagswact_path, 'wb') as f:
        f.write(build_pagswact(vin, FEATURES))
    with open(copie_path, 'w', newline='\n') as f:
        f.write(COPIE_SCR)

    print(f"\n  Written: {pagswact_path}")
    print(f"  Written: {copie_path}")
    print(f"\n  Copy both files to FAT32 USB root, insert into PCM.\n")

if __name__ == '__main__':
    main()
