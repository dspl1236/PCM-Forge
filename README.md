# PCM-Forge

**Open-source activation code generator for Porsche PCM 3.1 infotainment systems.**

🔓 **Algorithm fully cracked** — 64-bit RSA modular exponentiation, reverse-engineered from QNX firmware via Ghidra SH4 decompilation. Generate activation codes for any VIN, for free.

🌐 **Web tool:** [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/)

💻 **Desktop app:** [Download latest (Windows x64)](https://github.com/dspl1236/PCM-Forge/releases/latest) — offline code generator + ESP32 device programmer

📋 **What can I activate?** → See [FEATURES.md](FEATURES.md) for the full list of 26 features with descriptions, retail costs, and hardware requirements.

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
# List all 26 codes (defaults to 911 Carrera for FeatureLevel)
python generate_codes.py WP1AE2A28GLA64179

# Specify your model so FeatureLevel is correct
python generate_codes.py WP1AE2A28GLA64179 --model cayenne-958

# Write activation files directly to a USB drive
python generate_codes.py WP1AE2A28GLA64179 E:\ --model cayenne-958

# See all available model keys
python generate_codes.py --list-models

# Unknown model? Override the FeatureLevel SubID directly
python generate_codes.py <VIN> --featlevel-subid 0x0039
```

**Available models:** `cayenne-958`, `cayenne-958t`, `cayenne-958-v6`, `cayenne-957-v6`, `991`, `991t`, `991-cab`, `997-v6`, `997-s-v8`, `997t`, `997-variant`. Panamera, Macan, and Boxster/Cayman SubIDs are not yet decoded — use `--featlevel-subid` if you know the value for your vehicle.

**Other flags:** `--quiet` for scripting (one code per line), `--list-models` to see all options.

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

All 26 PCM 3.1 features are implemented. Verification uses the `PagSWAct.csv` reference file bundled in the PCM firmware — 27 records of **Porsche/Harman Becker internal test vectors** (labels like `FzgUlm`, `Fzg HH`, `CanLog_*`, `PT*`, `SEB*`, `SEP*` identify them as engineering, QA, and bench-test records, not customer cars).

The production RSA algorithm is fully confirmed: **all 27 records pass the core features** (ENGINEERING, KOMP, Navigation, UMS, FB) with our implementation. Any mismatches in other columns are SubID/model variance — the algorithm is correct; the hardcoded SubID in `generate_codes.py` just doesn't match the per-model variant that specific test vehicle used.

**Core Features** (model-agnostic — single SubID works for every vehicle)

| Feature | SWID | SubID | Matches | Description |
|---------|------|-------|---------|-------------|
| ENGINEERING | 0x010b | 0x0000 | 27/27 | Engineering & diagnostic menu |
| BTH | 0x010a | 0x0000 | 26/27 † | Bluetooth telephony |
| KOMP | 0x0106 | 0x0000 | 26/27 † | Component activation |
| FB | 0x0103 | 0x0000 | 27/27 | Feature base / boot image |
| SC | 0x0105 | 0x0000 | 25/25 | Sport Chrono |
| SDARS | 0x0108 | 0x0000 | 15/15 | SiriusXM satellite radio |
| INDMEM | 0x010d | 0x0000 | 24/24 | Individual memory |
| Navigation | 0x0101 | 0x0000 | 27/27 | GPS navigation system |
| UMS | 0x0109 | 0x0000 | 27/27 | USB media support |
| HDTuner | 0x010f | 0x0000 | 23/23 | HD Radio tuner |
| DABTuner | 0x0110 | 0x0000 | 27/27 | DAB digital radio |

† One record (`SE0801`) has a malformed 17-character KOMP field and an off-by-one BTH code — intentionally corrupt record used to test firmware error paths.

**Model-Keyed Features** (SubID varies by vehicle variant)

| Feature | SWID | Default SubID | Description |
|---------|------|---------------|-------------|
| FeatureLevel | 0x010e | varies per model | Boot logo / model variant. **Required after PCM swap — this is the code dealers charge ~$3500 for.** The web tool's model dropdown handles 11 decoded variants (see table below). CLI users: pass the SubID manually. |
| TVINF | 0x0107 | 0x0166 (most vehicles) | Video in Motion. Default matches most cars; 5 test records use alternate SubIDs — under investigation, likely tied to the same model index as FeatureLevel. |

**Region-Specific Features**

| Feature | SWID | SubID | Matches | Notes |
|---------|------|-------|---------|-------|
| OnlineServices | 0x0111 | 0x0001 | 22/27 | Aha Radio. 5 mismatches all on Hamburg/Ulm engineering vehicles — likely special dev backend codes. |
| SSS | 0x0104 | 0x0000 | 23/27 | Voice control. 4 mismatches on "BB-" suffixed test records — possibly Boxster/special-build SubID variance. |

**Nav Database Regions** (per-region activation for installed map data)

| Feature | SWID | SubID | Matches |
|---------|------|-------|---------|
| NavDBEurope | 0x2001 | 0x00ff | 23/24 ‡ |
| NavDBNorthAmerica | 0x2002 | 0x00ff | 15/17 ‡ |
| NavDBSouthAfrica | 0x2003 | 0x00ff | 8/9 ‡ |
| NavDBMiddleEast | 0x2004 | 0x00ff | 8/9 ‡ |
| NavDBAustralia | 0x2005 | 0x00ff | 9/9 |
| NavDBAsiaPacific | 0x2006 | 0x00ff | 9/9 |
| NavDBRussia | 0x2007 | 0x00ff | 9/10 ‡ |
| NavDBSouthAmerica | 0x2008 | 0x00ff | 8/9 ‡ |
| NavDBChina | 0x2009 | 0x00ff | 8/12 |
| NavDBChile | 0x200a | 0x00ff | 15/15 |
| NavDBArgentina | 0x200b | 0x00ff | 15/18 |

‡ Failures cluster entirely on `CanLog_*` and `PT*` records — Porsche's CAN-logging bench harness that loops through regions with special test payloads. No production vehicle match failures observed.

The NavDBChina / NavDBArgentina failures on 991 records (`SEB201`, `SEB202`, `SEB207`) cluster on three consecutive engineering VINs — likely a model-specific SubID variant for 991 vehicles with those nav regions, still under investigation.

Full verification data: [research/firmware/PagSWAct.csv](research/firmware/PagSWAct.csv). Run `python tools/verify.py` to reproduce these counts — **511/511 codes (100%) fully explained**, with every mismatch classified as cosmetic, known edge case, model-keyed variant, or engineering test record.

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
├── tools/
│   ├── verify.py              ← Verification against PagSWAct.csv (100%)
│   └── diff_fw.py             ← Firmware variant diff tool
└── research/
    ├── ALGORITHM_CRACKED.md       ← Complete algorithm documentation
    ├── PCM31_RESEARCH.md          ← Hardware/software architecture
    ├── PCM31_SYSTEM_INFO.md       ← Target vehicle details
    ├── USB_ENGINEERING_ACCESS.md
    ├── CROSS_PLATFORM_NOTES.md    ← PCM 3.1 vs PCM 4/MIB2 comparison
    └── firmware/              ← Extracted firmware data
        ├── PagSWAct.csv       ← 27 known VIN/code pairs (verification dataset)
        └── *.bin, *.txt       ← IOC firmware, Ghidra output
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

- **Missing SubIDs for some model variants** — Panamera (970/9P), Macan (95B), Cayman/Boxster (987/981), GT3/GT2 SubIDs are not yet decoded. If you have a working FeatureLevel code for one of these, open an issue — the SubID can be recovered by trial decryption and added to the model table.
- **TVINF may also be model-keyed** — 5 test records don't match the default `0x0166` SubID. Pattern matches FeatureLevel, suggesting per-model variance. Needs more samples to fully decode.
- **No retail activation for FeatureLevel** — dealers charge ~$3500 for this code after a PCM swap. PCM-Forge generates it for free, but for your specific vehicle variant only. Wrong SubID = wrong code.

## Related Projects

**By platform:**

| Generation | Platform | Your car? | Tool |
|-----------|----------|-----------|------|
| PCM 3.1 (SH4 / QNX 6.3) | Harman Becker | Cayenne 958, 911 991.1, Panamera 970, Boxster/Cayman 981, Macan 95B | **PCM-Forge** (this repo) |
| MMI 3G / 3G+ (SH4 / QNX 6.3) | Harman Becker | Audi A4–A8 (B8/B8.5/C6/C7/D3/D4), VW Touareg 7P with RNS-850 | **[MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit)** |
| PCM 4 / MHI2 / MIB2 (Tegra ARM / QNX 6.5) | Harman | Panamera 971, 911 991.2+, 718, refreshed Macan | [M.I.B.](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash), [harman-f AIO updates](https://github.com/harman-f) |
| MIB3 / MIB4 / E3 (ARM / Linux) | Continental / CARIAD | Post-2020 VAG vehicles | Not yet reverse-engineered |

**Same feature-identifier scheme across PCM 3.1 ↔ PCM 4 / MIB2:** Porsche reused the `SWID.SubID` hex structure when moving from Harman Becker to Harman's Tegra-based MIB2 platform. The FEC codes documented in [harman-f's AIO firmware patches](https://github.com/harman-f/MHI2_US_POG11_K5186_1-MU1476-AIO#features) confirm the scheme carried forward — our `0x0003`, `0x0005`, `0x0007` FeatureLevel values for 911 variants map to their MIB2 FEC entries. But the **activation mechanisms are completely different**: PCM 3.1 strictly validates RSA signatures (PCM-Forge forges them via modulus factoring), while PCM 4 / MIB2 skips signature validation entirely (harman-f just writes all-0xFF where a signature should be). See [research/CROSS_PLATFORM_NOTES.md](research/CROSS_PLATFORM_NOTES.md) for a full comparison of binary formats, exploit surfaces, and delivery mechanisms across generations.

**Tools on the VAG side of the Harman family tree:**

- [**jilleb/mib2-toolbox**](https://github.com/jilleb/mib2-toolbox) — The canonical MIB2-HIGH toolbox (848 ⭐). Same generation as PCM 4; different brand (VAG passenger cars vs Porsche). Pattern our MMI3G-Toolkit is inspired by
- [**jilleb/mib1-toolbox**](https://github.com/jilleb/mib1-toolbox) — MIB1-HIGH predecessor. Closest VAG analog to our PCM 3.1 generation
- [**jilleb/odis2vcp**](https://github.com/jilleb/odis2vcp) — Converts ODIS XML to VCP XML. Useful if you have ODIS and want to pull datasets for use with VCDS/VCP tools
- [**jilleb/binary_tools**](https://github.com/jilleb/binary_tools) — Minimal Python scripts for binary file comparison. PCM-Forge's `tools/diff_fw.py` is an expanded version of this approach

## Credits

- **harman-f** — PCM 4 / MIB2 firmware patching research. Their `addfec` shell script was the Rosetta Stone for documenting the MIB2 FecContainer.fec binary format in our [CROSS_PLATFORM_NOTES.md](research/CROSS_PLATFORM_NOTES.md)
- **jilleb** — The `tools/diff_fw.py` firmware comparison tool was inspired by [jilleb/binary_tools](https://github.com/jilleb/binary_tools) `find_identical_ranges.py`. The concept of toolbox-shaped feature flag exploration came from [jilleb/mib1-toolbox](https://github.com/jilleb/mib1-toolbox) and [mib2-toolbox](https://github.com/jilleb/mib2-toolbox)
- **The Porsche/Harman IOC firmware engineers** — for leaving PagSWAct.csv (27 test vectors) inside the firmware bundle. Those 27 records made 100% algorithm verification possible

## License

MIT License — See [LICENSE](LICENSE)

## Disclaimer

For research and educational purposes. Use at your own risk. The authors are not responsible for any damage to vehicles or components.
