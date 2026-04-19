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

# Complete Model → FeatureLevel SubID mapping
# All 78 models visually confirmed from PCM 3.1 bootscreen images
# SubID = FeatureLevel value = boot logo selector (they're the same!)
MODELS = {
    # ── 911 (997) Coupe ──
    '911':                   (0x0001, '911 (997) base'),
    '911-carrera':           (0x0002, '911 (997) Carrera'),
    '911-carrera-s':         (0x0003, '911 (997) Carrera S'),
    '911-carrera-4':         (0x0004, '911 (997) Carrera 4'),
    '911-carrera-4s':        (0x0005, '911 (997) Carrera 4S'),
    # ── 911 (997) Cabriolet ──
    '911-cab':               (0x0006, '911 (997) Carrera Cabriolet'),
    '911-cab-s':             (0x0007, '911 (997) Carrera S Cabriolet'),
    '911-cab-4':             (0x0008, '911 (997) Carrera 4 Cabriolet'),
    '911-cab-4s':            (0x0009, '911 (997) Carrera 4S Cabriolet'),
    # ── 911 (997) Targa ──
    '911-targa-4':           (0x000a, '911 (997) targa 4'),
    '911-targa-4s':          (0x000b, '911 (997) targa 4S'),
    # ── 911 (997) Turbo / GT ──
    '911-turbo':             (0x000c, '911 (997) Turbo'),
    '911-turbo-cab':         (0x000d, '911 (997) Turbo Cabriolet'),
    '911-turbo-s':           (0x000e, '911 (997) Turbo S'),
    '911-turbo-s-cab':       (0x000f, '911 (997) Turbo S Cabriolet'),
    '911-gt3':               (0x0010, '911 (997) GT3'),
    '911-gt3rs':             (0x0012, '911 (997) GT3 RS'),
    # ── 911 (991) ──
    '911-991':               (0x0014, '911 (991)'),
    '911-991-alt':           (0x0015, '911 (991) alt'),
    '911-991-gts':           (0x0016, '911 (991) Carrera GTS'),
    '911-991-4gts':          (0x0017, '911 (991) Carrera 4 GTS'),
    '911-991-gts-cab':       (0x0018, '911 (991) Carrera GTS Cabriolet'),
    '911-991-4gts-cab':      (0x0019, '911 (991) Carrera 4 GTS Cabriolet'),
    # ── Boxster (987 / 981) ──
    'boxster':               (0x001a, 'Boxster'),
    'boxster-alt':           (0x001b, 'Boxster (alt)'),
    'boxster-s':             (0x001c, 'Boxster S'),
    'boxster-rs':            (0x001d, 'Boxster RS'),
    'boxster-gts':           (0x001e, 'Boxster GTS'),
    'boxster-spyder':        (0x001f, 'Boxster Spyder'),
    # ── Cayman (987 / 981) ──
    'cayman':                (0x0022, 'Cayman'),
    'cayman-alt':            (0x0023, 'Cayman (alt)'),
    'cayman-s':              (0x0024, 'Cayman S'),
    'cayman-r':              (0x0025, 'Cayman R'),
    'cayman-gts':            (0x0026, 'Cayman GTS'),
    'cayman-gt4':            (0x0027, 'Cayman GT4'),
    # ── Panamera (970) ──
    'panamera':              (0x0029, 'Panamera'),
    'panamera-alt':          (0x002a, 'Panamera (alt)'),
    'panamera-4':            (0x002b, 'Panamera 4'),
    'panamera-s':            (0x002c, 'Panamera S'),
    'panamera-4s':           (0x002d, 'Panamera 4S'),
    'panamera-turbo':        (0x002e, 'Panamera Turbo'),
    'panamera-turbo-s':      (0x002f, 'Panamera Turbo S'),
    'panamera-gts':          (0x0030, 'Panamera GTS'),
    'panamera-sh':           (0x0031, 'Panamera S Hybrid'),
    'panamera-2':            (0x0032, 'Panamera (gen2)'),
    'panamera-s2':           (0x0033, 'Panamera S (gen2)'),
    'panamera-4sd':          (0x0034, 'Panamera 4S Diesel'),
    'panamera-sh2':          (0x0035, 'Panamera S Hybrid (gen2)'),
    'panamera-se':           (0x0036, 'Panamera S E-Hybrid'),
    # ── Cayenne (958) ──
    'cayenne':               (0x0038, 'Cayenne'),
    'cayenne-alt':           (0x0039, 'Cayenne (alt)'),
    'cayenne-s':             (0x003a, 'Cayenne S'),
    'cayenne-turbo':         (0x003b, 'Cayenne Turbo'),
    'cayenne-turbo-s':       (0x003c, 'Cayenne Turbo S'),
    'cayenne-gts':           (0x003d, 'Cayenne GTS'),
    'cayenne-sh':            (0x003e, 'Cayenne S Hybrid'),
    'cayenne-v6':            (0x003f, 'Cayenne V6'),
    'cayenne-s-alt':         (0x0040, 'Cayenne S (alt)'),
    'cayenne-ds':            (0x0041, 'Cayenne Diesel S'),
    'cayenne-sh2':           (0x0042, 'Cayenne S Hybrid (alt)'),
    'cayenne-se':            (0x0043, 'Cayenne S E-Hybrid'),
    # ── Macan (95B) ──
    'macan':                 (0x0047, 'Macan'),
    'macan-s':               (0x0048, 'Macan S'),
    'macan-hybrid':          (0x0049, 'Macan Hybrid'),
    'macan-se':              (0x004a, 'Macan S E-Hybrid'),
    'macan-turbo':           (0x004b, 'Macan Turbo'),
    'macan-turbo-s':         (0x004c, 'Macan Turbo S'),
    'macan-gts':             (0x004d, 'Macan GTS'),
    'macan-diesel':          (0x004e, 'Macan Diesel'),
    'macan-sd':              (0x004f, 'Macan S Diesel'),
    # ── 911 Special Editions ──
    '911-50th':              (0x0056, '911 50th Anniversary'),
    '911-clubsport':         (0x0057, '911 Club Sport'),
    '911-r':                 (0x0058, '911 R'),
    # ── 911 (991.2) / Targa ──
    '911-targa-4gts':        (0x005e, '911 targa 4 GTS'),
    '911-targa':             (0x005f, '911 targa'),
    '911-targa-s':           (0x0060, '911 targa S'),
    '911-991-2':             (0x0061, '911 (991.2)'),
    '911-991-2-cab':         (0x0062, '911 (991.2) Cabriolet'),
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
