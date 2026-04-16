# PCM-Forge

**Open-source activation code generator for Porsche PCM 3.1 infotainment systems.**

🔓 **Algorithm fully cracked** — 64-bit RSA modular exponentiation, reverse-engineered from QNX firmware via Ghidra SH4 decompilation. Generate activation codes for any VIN, for free.

🌐 **Web tool:** [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/)

## Supported Vehicles

All Porsche models with PCM 3.1 (Harman Becker, 2011–2016):

| Model | Years | Notes |
|-------|-------|-------|
| Cayenne (958) | 2011–2016 | Primary development target |
| Panamera (970) | 2011–2016 | Compatible |
| 911 (991.1) | 2012–2016 | Compatible |
| Boxster/Cayman (981) | 2013–2016 | Compatible |
| Macan (95B) | 2014–2016 | Compatible |

## Quick Start

### Web Tool
Visit [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/), enter your VIN, download the activation file.

### Command Line
```bash
python generate_codes.py WP1AE2A28GLA64179
python generate_codes.py WP1AE2A28GLA64179 E:\   # write directly to USB
```

### USB Activation
1. Format a USB stick as **FAT32**
2. Copy `copie_scr.sh` and `PagSWAct.002` to the USB root (**LF line endings only** — CRLF breaks it)
3. Insert into the PCM's USB port with ignition on
4. The PCM's `proc_scriptlauncher` detects and processes the files
5. Reboot — features are activated

## What's Cracked

### Activation Code Algorithm
The PCM 3.1 uses **64-bit RSA** implemented in the `CPPorscheEncrypter` C++ class:

```
n (modulus)  = 0x69f39c927ef94985 = 1831263461 × 4169044001
e (public)   = 0x4c1c5eeaf397c0b3
d (private)  = 0x5483975015d0287b
```

Code generation: `activation_code = pow(plaintext, d, n)`

The plaintext is constructed by **interleaving** a feature constant (SWID + SubID) with a VIN-derived number, character-by-character.

See [research/ALGORITHM_CRACKED.md](research/ALGORITHM_CRACKED.md) for the complete algorithm and implementation details.

### Feature Coverage

All 26 PCM 3.1 features are implemented and tested against 27 reference VINs from the firmware's `PagSWAct.csv`. Verification status as of this commit:

**Core Features** (model-agnostic — single SubID works for every vehicle)

| Feature | SWID | SubID | Verified | Description |
|---------|------|-------|----------|-------------|
| ENGINEERING | 0x010b | 0x0000 | 27/27 ✓ | Engineering & diagnostic menu |
| BTH | 0x010a | 0x0000 | 26/27 ✓ | Bluetooth telephony |
| KOMP | 0x0106 | 0x0000 | 27/27 ✓ | Component activation |
| FB | 0x0103 | 0x0000 | 27/27 ✓ | Feature base / boot image |
| SC | 0x0105 | 0x0000 | 25/25 ✓ | Sport Chrono |
| SDARS | 0x0108 | 0x0000 | 15/15 ✓ | SiriusXM satellite radio |
| INDMEM | 0x010d | 0x0000 | 24/24 ✓ | Individual memory |
| Navigation | 0x0101 | 0x0000 | 27/27 ✓ | GPS navigation system |
| UMS | 0x0109 | 0x0000 | 27/27 ✓ | USB media support |
| HDTuner | 0x010f | 0x0000 | 23/23 ✓ | HD Radio tuner |
| DABTuner | 0x0110 | 0x0000 | 27/27 ✓ | DAB digital radio |

**Model-Keyed Features** (SubID varies by vehicle — web tool's model dropdown handles this)

| Feature | SWID | SubID | Verified | Notes |
|---------|------|-------|----------|-------|
| FeatureLevel | 0x010e | varies | 3/16 partial | Per-model SubID decoded for 11 variants (see below). Required after PCM swap. |
| TVINF | 0x0107 | 0x0166† | 19/24 partial | Video in Motion. Some vehicles use a different SubID — under investigation. |
| OnlineServices | 0x0111 | 0x0001 | 22/27 partial | Aha Radio. 5 engineering/test VINs diverge. |
| SSS | 0x0104 | 0x0000 | 23/27 partial | Voice control. 4 VINs diverge — possibly model-keyed. |

†Default SubID `0x0166`; some vehicles may require a model-specific value.

**Nav Database Regions** (per-region activation for installed map data)

| Feature | SWID | SubID | Verified |
|---------|------|-------|----------|
| NavDBEurope | 0x2001 | 0x00ff | 23/24 ✓ |
| NavDBNorthAmerica | 0x2002 | 0x00ff | 15/17 ✓ |
| NavDBSouthAfrica | 0x2003 | 0x00ff | 8/9 ✓ |
| NavDBMiddleEast | 0x2004 | 0x00ff | 8/9 ✓ |
| NavDBAustralia | 0x2005 | 0x00ff | 9/9 ✓ |
| NavDBAsiaPacific | 0x2006 | 0x00ff | 9/9 ✓ |
| NavDBRussia | 0x2007 | 0x00ff | 9/10 ✓ |
| NavDBSouthAmerica | 0x2008 | 0x00ff | 8/9 ✓ |
| NavDBChina | 0x2009 | 0x00ff | 9/12 partial |
| NavDBChile | 0x200a | 0x00ff | 15/15 ✓ |
| NavDBArgentina | 0x200b | 0x00ff | 15/18 partial |

> **Reading this table:** `✓` = all real mismatches explained (the few non-matches are either engineering/test VINs or cosmetic leading-zero formatting in the CSV — our 16-char zero-padded output is the correct 64-bit representation). `partial` = real algorithmic mismatches exist and are under investigation. Full verification data: [research/firmware/PagSWAct.csv](research/firmware/PagSWAct.csv).

### FeatureLevel SubIDs (decoded from reference VINs)

FeatureLevel controls the boot logo and model variant identification. After a PCM swap, this is the code owners typically pay $3500 for at a dealer. Decoded variants:

| SubID | Model |
|-------|-------|
| 0x0003 | 911 (991) Carrera |
| 0x0005 | 911 (991) Turbo |
| 0x0007 | 911 (991) Cabriolet/Targa |
| 0x002a | 911 (997) Carrera V6 |
| 0x002d | 911 (997) Carrera S V8 |
| 0x002e | 911 (997) Turbo |
| 0x0031 | 911 (997) variant |
| 0x0039 | Cayenne 958 base / 957 V6 |
| 0x003b | Cayenne 958 Turbo |
| 0x003f | Cayenne 958 V6 |
| 0x0041 | Cayenne 957 V6 |

Unknown / needs samples: Panamera (970/9P), Macan (95B), Cayman/Boxster (987/981), GT3/GT2.

### USB Delivery Mechanism
The PCM uses `proc_scriptlauncher` — the same `copie_scr.sh` autorun mechanism as the Audi MMI3G. When a USB stick is inserted at `/fs/usb0`, the launcher looks for `/copie_scr.sh`, decodes it (XOR with PRNG, seed 0 = plaintext), and executes it with `/bin/ksh`. The script copies activation data to the PCM's internal `/HBpersistence/PagSWAct.002` and touches `/HBpersistence/DBGModeActive` to mark features unlocked.

### PagSWAct.002 binary format
28 bytes per record:
- `[0..15]` — 16 ASCII hex characters of the activation code
- `[16..17]` — padding
- `[18..19]` — SWID (u16 little-endian)
- `[20..21]` — SubID (u16 little-endian)
- `[22]` — state (`1` = unlocked)
- `[23]` — padding
- `[24..27]` — type (u32 LE, `1` = permanent)

### Firmware Architecture

| Component | Detail |
|-----------|--------|
| OS | QNX 6.3.0 SP1 |
| CPU | Renesas SH4A (SuperH) |
| Main binary | PCM3Root (5.8MB ELF, 12,604 functions) |
| IOC gateway | Renesas V850 with CMX-RTX RTOS |
| IFS format | QNX IFS with LZO compression (BE 16-bit length prefix) |
| Crypto | Custom 64-bit RSA in `CPPorscheEncrypter` class |
| Key location | Literal pool at 0x082270b4 / 0x082270b8 in PCM3Root |

## Repository Structure

```
PCM-Forge/
├── README.md
├── generate_codes.py          ← Command-line code generator (26 features)
├── docs/index.html            ← Web tool (GitHub Pages)
├── research/
│   ├── ALGORITHM_CRACKED.md   ← Complete algorithm documentation
│   ├── PCM31_RESEARCH.md      ← Hardware/software architecture
│   ├── PCM31_SYSTEM_INFO.md   ← Target vehicle details
│   ├── USB_ENGINEERING_ACCESS.md
│   └── firmware/              ← Extracted firmware data
│       ├── PagSWAct.csv       ← 27 known VIN/code pairs (verification dataset)
│       └── *.bin, *.txt       ← IOC firmware, Ghidra output
└── shared/uds/                ← UDS diagnostic stack (shared with MMI3G)
```

## How It Was Done

The complete reverse engineering chain:

1. **QNX IFS extraction** — LZO decompression of firmware image (227 blocks, 6.8MB → 14.2MB)
2. **Binary extraction** — 129 files from IFS directory structure
3. **Ghidra decompilation** — PCM3Root loaded as SH4A ELF, 12,604 functions analyzed
4. **Function tracing** — Located `CPPorscheEncrypter::verify` via string cross-references
5. **Algorithm identification** — Modular exponentiation (square-and-multiply) at `FUN_082405a0`
6. **Key extraction** — RSA parameters found in literal pool as hex strings
7. **Modulus factoring** — 64-bit modulus factored in milliseconds via Pollard's rho
8. **Private key computation** — `d = e^(-1) mod φ(n)`
9. **VIN mapping** — Weighted sum with 16-bit overflow, verified against all 27 known pairs
10. **Plaintext discovery** — Character-by-character interleaving (not concatenation)
11. **USB delivery** — `proc_scriptlauncher` + `copie_scr.sh` autorun mechanism

## Known Limitations

- **FeatureLevel requires model selection** — the SubID varies per vehicle. The web tool's model dropdown covers 11 decoded variants. Two outlier test VINs in the reference dataset suggest additional SubIDs exist outside 0x0001–0x007f; needs more samples.
- **TVINF partial verification** — 5 of 24 reference VINs don't match the default `0x0166` SubID. Likely a model-keyed parameter similar to FeatureLevel; under investigation.
- **No retail activation for FeatureLevel** — this code is what dealers charge ~$3500 for after a PCM swap. PCM-Forge generates it for free, but for your specific vehicle variant only. Wrong SubID = wrong code.

## Related Projects

- **[MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit)** — Sister project for Audi MMI3G/3G+ (same Harman Becker platform)
- [M.I.B.](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash) — For PCM 4.x / MIB2 systems

## License

MIT License — See [LICENSE](LICENSE)

## Disclaimer

For research and educational purposes. Use at your own risk. The authors are not responsible for any damage to vehicles or components.
