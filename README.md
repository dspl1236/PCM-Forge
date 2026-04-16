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
2. Copy `copie_scr.sh` and `PagSWAct.002` to the USB root
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

The plaintext is constructed by **interleaving** a feature constant with a VIN-derived number. All 27 known VIN/code pairs from the firmware verified with 100% accuracy.

See [research/ALGORITHM_CRACKED.md](research/ALGORITHM_CRACKED.md) for the complete algorithm and implementation details.

### Features

| Feature | SWID | Status |
|---------|------|--------|
| ENGINEERING | 0x010b | ✓ Verified |
| BTH (Bluetooth) | 0x010a | ✓ Verified |
| KOMP (Component) | 0x0106 | ✓ Verified |

### USB Delivery Mechanism
The PCM uses `proc_scriptlauncher` — the same `copie_scr.sh` autorun mechanism as the Audi MMI3G. When a USB stick is inserted, the launcher looks for `/copie_scr.sh`, decodes it (XOR with PRNG, seed 0 = plaintext), and executes it with `/bin/ksh`. The script copies activation data to the PCM's internal `/HBpersistence/` partition.

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
├── generate_codes.py          ← Command-line code generator
├── docs/index.html            ← Web tool (GitHub Pages)
├── research/
│   ├── ALGORITHM_CRACKED.md   ← Complete algorithm documentation
│   ├── PCM31_RESEARCH.md      ← Hardware/software architecture
│   ├── PCM31_SYSTEM_INFO.md   ← Target vehicle details
│   ├── USB_ENGINEERING_ACCESS.md
│   └── firmware/              ← Extracted firmware data
│       ├── PagSWAct.csv       ← 27 known VIN/code pairs
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

## Related Projects

- **[MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit)** — Sister project for Audi MMI3G/3G+ (same Harman Becker platform)
- [M.I.B.](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash) — For PCM 4.x / MIB2 systems

## License

MIT License — See [LICENSE](LICENSE)

## Disclaimer

For research and educational purposes. Use at your own risk. The authors are not responsible for any damage to vehicles or components.
