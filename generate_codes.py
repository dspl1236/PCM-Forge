#!/usr/bin/env python3
"""
PCM-Forge: Porsche PCM 3.1 Activation Code Generator
https://github.com/dspl1236/PCM-Forge

Generates activation codes for ALL 26 features.
Usage:
  python generate_codes.py <VIN>
  python generate_codes.py <VIN> <USB_PATH>
"""
import struct, sys, os

N = 0x69f39c927ef94985
E = 0x4c1c5eeaf397c0b3
D = 0x5483975015d0287b

FEATURES = [
    ("ENGINEERING",      "010b0000", 0x010b, 0x0000, "Engineering & diagnostic menu"),
    ("BTH",              "010a0000", 0x010a, 0x0000, "Bluetooth telephony"),
    ("KOMP",             "01060000", 0x0106, 0x0000, "Component activation"),
    ("Navigation",       "01010000", 0x0101, 0x0000, "Navigation system"),
    ("UMS",              "01090000", 0x0109, 0x0000, "USB media support"),
    ("FB",               "01030000", 0x0103, 0x0000, "Feature base / boot image"),
    ("SSS",              "01040000", 0x0104, 0x0000, "Voice control"),
    ("SC",               "01050000", 0x0105, 0x0000, "Sport Chrono"),
    ("TVINF",            "01070166", 0x0107, 0x0166, "Video in Motion"),
    ("SDARS",            "01080000", 0x0108, 0x0000, "Satellite radio"),
    ("INDMEM",           "010d0000", 0x010d, 0x0000, "Individual memory"),
    ("FeatureLevel",     "010e0003", 0x010e, 0x0003, "Feature level (caution!)"),
    ("HDTuner",          "010f0000", 0x010f, 0x0000, "HD Radio tuner"),
    ("DABTuner",         "01100000", 0x0110, 0x0000, "DAB digital radio"),
    ("OnlineServices",   "01110001", 0x0111, 0x0001, "Online services"),
    ("NavDBEurope",      "200100ff", 0x2001, 0x00ff, "Nav: Europe"),
    ("NavDBNorthAmerica","200200ff", 0x2002, 0x00ff, "Nav: North America"),
    ("NavDBSouthAfrica", "200300ff", 0x2003, 0x00ff, "Nav: South Africa"),
    ("NavDBMiddleEast",  "200400ff", 0x2004, 0x00ff, "Nav: Middle East"),
    ("NavDBAustralia",   "200500ff", 0x2005, 0x00ff, "Nav: Australia"),
    ("NavDBAsiaPacific", "200600ff", 0x2006, 0x00ff, "Nav: Asia Pacific"),
    ("NavDBRussia",      "200700ff", 0x2007, 0x00ff, "Nav: Russia"),
    ("NavDBSouthAmerica","200800ff", 0x2008, 0x00ff, "Nav: South America"),
    ("NavDBChina",       "200900ff", 0x2009, 0x00ff, "Nav: China"),
    ("NavDBChile",       "200a00ff", 0x200a, 0x00ff, "Nav: Chile"),
    ("NavDBArgentina",   "200b00ff", 0x200b, 0x00ff, "Nav: Argentina"),
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

def build_pagswact(vin, features):
    data = bytearray()
    for name, feat_hex, swid, subid, desc in features:
        code = generate_code(vin, feat_hex)
        rec = bytearray(28)
        for i, c in enumerate(code[:16]): rec[i] = ord(c)
        struct.pack_into('<H', rec, 18, swid)
        struct.pack_into('<H', rec, 20, subid)
        rec[22] = 1
        struct.pack_into('<I', rec, 24, 1)
        data.extend(rec)
    return bytes(data)

COPIE_SCR = "#!/bin/ksh\n# PCM-Forge — https://github.com/dspl1236/PCM-Forge\nfor USBPATH in /fs/usb0 /fs/usb1 /fs/usb /media/usb0; do\n    [ -f \"${USBPATH}/PagSWAct.002\" ] && break\ndone\n[ -f \"${USBPATH}/PagSWAct.002\" ] && cp \"${USBPATH}/PagSWAct.002\" /HBpersistence/PagSWAct.002\ntouch /HBpersistence/DBGModeActive\nsync\n"

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_codes.py <VIN> [USB_PATH]")
        sys.exit(1)
    vin = sys.argv[1].upper()
    usb_path = sys.argv[2] if len(sys.argv) > 2 else None
    if len(vin) != 17:
        print(f"Error: VIN must be 17 characters"); sys.exit(1)

    print(f"\n  PCM-Forge — All 26 Activation Codes")
    print(f"  VIN: {vin}\n")
    for name, feat_hex, swid, subid, desc in FEATURES:
        code = generate_code(vin, feat_hex)
        print(f"  {name:<22s}: {code}  {desc}")

    out = usb_path or "."
    with open(os.path.join(out, "PagSWAct.002"), 'wb') as f:
        f.write(build_pagswact(vin, FEATURES))
    with open(os.path.join(out, "copie_scr.sh"), 'w', newline='\n') as f:
        f.write(COPIE_SCR)
    print(f"\n  Written to {out}/: PagSWAct.002 + copie_scr.sh\n")

if __name__ == '__main__':
    main()
