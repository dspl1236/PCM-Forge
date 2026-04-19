#!/usr/bin/env python3
"""
PCM-Forge: Porsche PCM 3.1 Activation Code Generator
https://github.com/dspl1236/PCM-Forge

Generates activation codes for ALL 26 features of the Porsche PCM 3.1.

Usage:
  python generate_codes.py <VIN>                     # list all codes (911 default)
  python generate_codes.py <VIN> <USB_PATH>          # write to USB (911 default)
  python generate_codes.py <VIN> --model <key>       # pick model variant
  python generate_codes.py <VIN> <USB_PATH> --model <key>
  python generate_codes.py --list-models             # show available models

Model keys (for correct FeatureLevel / boot logo):
  cayenne-958      Cayenne 958 base                        (SubID 0x0039)
  cayenne-958s     Cayenne 958 S                           (SubID 0x003a)
  cayenne-958t     Cayenne 958 Turbo                       (SubID 0x003b)
  cayenne-958ts    Cayenne 958 Turbo S                     (SubID 0x003c)
  cayenne-958gts   Cayenne 958 GTS                         (SubID 0x003d)
  cayenne-958sh    Cayenne 958 S Hybrid                    (SubID 0x003e)
  cayenne-958-v6   Cayenne 958 V6                          (SubID 0x003f)
  cayenne-958se    Cayenne 958 S E-Hybrid                  (SubID 0x0043)  [Andrew's car!]
  991              911 (991) Carrera                        (SubID 0x0003)  [default]
  991-base         911 (991) base variant                 (SubID 0x0000)
  991t             911 (991) Turbo                        (SubID 0x0005)
  boxster-cayman   Boxster / Cayman (981)                 (SubID 0x0007)
  997              911 (997) Carrera                      (SubID 0x002a)
  panamera         Panamera (970) V8                      (SubID 0x002d)
  997t             911 (997) Turbo                        (SubID 0x002e)
  997-alt          911 (997) alternate coding             (SubID 0x0031)

For unknown models (Macan 95B, GT3/GT2):
  Pass --featlevel-subid 0xNNNN with the known SubID for that vehicle.
"""
import struct, sys, os, argparse

N = 0x69f39c927ef94985
E = 0x4c1c5eeaf397c0b3
D = 0x5483975015d0287b

# Model → FeatureLevel SubID mapping (brute-forced from PagSWAct.csv + VIN decode)
# Cayenne SubIDs confirmed from bootscreen map (CustomBootscreen_056-067)
MODELS = {
    'cayenne-958':    (0x0039, 'Cayenne 958 base (E2)'),
    'cayenne-958s':   (0x003a, 'Cayenne 958 S'),
    'cayenne-958t':   (0x003b, 'Cayenne 958 Turbo'),
    'cayenne-958ts':  (0x003c, 'Cayenne 958 Turbo S'),
    'cayenne-958gts': (0x003d, 'Cayenne 958 GTS'),
    'cayenne-958sh':  (0x003e, 'Cayenne 958 S Hybrid'),
    'cayenne-958-v6': (0x003f, 'Cayenne 958 V6 (E2V6)'),
    'cayenne-958s2':  (0x0040, 'Cayenne 958 S (alt)'),
    'cayenne-958ds':  (0x0041, 'Cayenne 958 Diesel S'),
    'cayenne-958sh2': (0x0042, 'Cayenne 958 S Hybrid (alt)'),
    'cayenne-958se':  (0x0043, 'Cayenne 958 S E-Hybrid'),
    '991':            (0x0003, '911 (991) Carrera'),
    '991-base':       (0x0000, '911 (991) base variant'),
    '991t':           (0x0005, '911 (991) Turbo'),
    'boxster-cayman': (0x0007, 'Boxster / Cayman (981)'),
    '997':            (0x002a, '911 (997) Carrera'),
    'panamera':       (0x002d, 'Panamera (970) V8'),
    '997t':           (0x002e, '911 (997) Turbo (G1T)'),
    '997-alt':        (0x0031, '911 (997) alternate coding'),
}

def features_for(featlvl_subid):
    """Build the feature list using a specific FeatureLevel SubID."""
    featlvl_hex = f"010e{featlvl_subid:04x}"
    return [
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
        ("FeatureLevel",     featlvl_hex, 0x010e, featlvl_subid, "Feature level / boot logo"),
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

# Default backwards-compatible feature list (911 991 Carrera)
FEATURES = features_for(0x0003)

def vin_to_number(vin):
    """Weighted-sum VIN → integer, matching CPPorscheEncrypter::vinToNumber."""
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
    """Character-by-character interleave (NOT concatenation)."""
    return ''.join(a[i] + b[i] for i in range(8))

def generate_code(vin, feat_hex):
    """Generate a single 16-char activation code for a (VIN, feature) pair."""
    vh = f"{vin_to_number(vin):08x}"
    pt = int(interleave(feat_hex, vh), 16)
    return f"{pow(pt, D, N):016x}"

def build_pagswact(vin, features):
    """Pack all feature codes into the 28-byte-per-record PagSWAct.002 format."""
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

COPIE_SCR = (
    "#!/bin/ksh\n"
    "# PCM-Forge — https://github.com/dspl1236/PCM-Forge\n"
    "for USBPATH in /fs/usb0 /fs/usb1 /fs/usb /media/usb0; do\n"
    "    [ -f \"${USBPATH}/PagSWAct.002\" ] && break\n"
    "done\n"
    "[ -f \"${USBPATH}/PagSWAct.002\" ] && cp \"${USBPATH}/PagSWAct.002\" /HBpersistence/PagSWAct.002\n"
    "touch /HBpersistence/DBGModeActive\n"
    "sync\n"
)

def list_models():
    print("\n  Available model keys for --model:\n")
    print(f"  {'Key':<18s} {'SubID':<8s} {'Description'}")
    print(f"  {'-'*18}  {'-'*6}  {'-'*40}")
    for key, (sub, desc) in MODELS.items():
        print(f"  {key:<18s} 0x{sub:04x}  {desc}")
    print("\n  For unknown variants, use: --featlevel-subid 0xNNNN\n")

def parse_args(argv):
    """Parse args compatibly with old positional usage + new --model flag."""
    # Support old positional style: VIN [USB_PATH]
    # New style: VIN [USB_PATH] [--model KEY] [--featlevel-subid HEX]
    p = argparse.ArgumentParser(
        description='Generate Porsche PCM 3.1 activation codes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument('vin', nargs='?', help='17-character VIN')
    p.add_argument('usb_path', nargs='?', default=None,
                   help='Optional USB drive path (e.g. E:\\ on Windows)')
    p.add_argument('--model', '-m', default=None,
                   help='Vehicle model key (see --list-models). Sets the FeatureLevel SubID.')
    p.add_argument('--featlevel-subid', default=None,
                   help='Override FeatureLevel SubID directly (e.g. 0x0039). For unknown models.')
    p.add_argument('--list-models', action='store_true',
                   help='Show available model keys and exit')
    p.add_argument('--quiet', '-q', action='store_true',
                   help='Only print activation codes, no headers')
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    if args.list_models:
        list_models()
        return 0

    if not args.vin:
        print("Error: VIN required. Use --help for usage.", file=sys.stderr)
        return 1

    vin = args.vin.upper()
    if len(vin) != 17:
        print(f"Error: VIN must be 17 characters (got {len(vin)})", file=sys.stderr)
        return 1

    # Resolve FeatureLevel SubID
    if args.featlevel_subid:
        try:
            featlvl_subid = int(args.featlevel_subid, 16) if args.featlevel_subid.startswith('0x') \
                else int(args.featlevel_subid, 16)
        except ValueError:
            print(f"Error: --featlevel-subid must be hex (e.g. 0x0039)", file=sys.stderr)
            return 1
        model_desc = f"custom SubID 0x{featlvl_subid:04x}"
    elif args.model:
        if args.model not in MODELS:
            print(f"Error: unknown model '{args.model}'. Use --list-models to see options.",
                  file=sys.stderr)
            return 1
        featlvl_subid, model_desc = MODELS[args.model]
    else:
        # No model specified — default to 911 Carrera for backwards compatibility
        featlvl_subid = 0x0003
        model_desc = '911 (991) Carrera [default — use --model for others]'

    features = features_for(featlvl_subid)

    if not args.quiet:
        print(f"\n  PCM-Forge — All 26 Activation Codes")
        print(f"  VIN:   {vin}")
        print(f"  Model: {model_desc}\n")

    for name, feat_hex, swid, subid, desc in features:
        code = generate_code(vin, feat_hex)
        if args.quiet:
            print(f"{name}:{code}")
        else:
            print(f"  {name:<22s}: {code}  {desc}")

    if args.usb_path:
        out = args.usb_path
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "PagSWAct.002"), 'wb') as f:
            f.write(build_pagswact(vin, features))
        with open(os.path.join(out, "copie_scr.sh"), 'w', newline='\n') as f:
            f.write(COPIE_SCR)
        if not args.quiet:
            print(f"\n  Written to {out}/: PagSWAct.002 + copie_scr.sh")
    else:
        # Behavior change from original: previously always wrote to "."
        # Now only writes if USB path is given. Hint at the option.
        if not args.quiet:
            print(f"\n  (Codes only; pass a USB path to write PagSWAct.002 + copie_scr.sh)")

    return 0

if __name__ == '__main__':
    sys.exit(main())
