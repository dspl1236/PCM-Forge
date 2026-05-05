# PCM 3.1 USB Activation — Confirmed Mechanism

## How It Works (Reverse-Engineered)

The PCM 3.1 uses the **same `copie_scr.sh` autorun mechanism as the Audi MMI3G**.

### Boot Sequence
1. `srv-starter-QNX` launches from `pcm3_starter.cfg`
2. `start-medialaunch.sh` starts `vdev-medialaunch` for USB detection
3. `proc_scriptlauncher` connects to `/dev/medialauncher`
4. On USB insertion, it looks for **`/copie_scr.sh`** on the mounted media
5. `script_decoder` processes the file (XOR PRNG, seed 0 = plaintext)
6. Decoded script is saved to `/HBpersistence/copie_scr.sh`
7. Script is executed with `/bin/ksh`

> **Critical timing:** The USB must be inserted **after** the PCM has fully booted
> (home screen visible). `proc_scriptlauncher` monitors for USB insert *events* —
> a drive already present at boot is treated as media storage and the script is
> never triggered.

### USB Stick Contents
```
USB Root (FAT32)/
├── copie_scr.sh      ← Autorun script
└── PagSWAct.002      ← VIN-specific activation codes
```

### What the Script Does
```bash
#!/bin/ksh
cp /fs/usb0/PagSWAct.002 /HBpersistence/PagSWAct.002
touch /HBpersistence/DBGModeActive
sync
```

The script copies the activation file to internal storage and creates the engineering mode flag. On next boot, `PCM3Root` reads `/HBpersistence/PagSWAct.002` and validates each activation code against the VIN using `CPPorscheEncrypter::verify`.

## PagSWAct.002 Binary Format

28 bytes per feature record:

| Offset | Size | Field | Example |
|--------|------|-------|---------|
| 0–16 | 17 | Activation code (hex string + null) | `297646776cafd751\0` |
| 17 | 1 | Padding | `0x00` |
| 18–19 | 2 | SWID (uint16 LE) | `0x010b` (ENGINEERING) |
| 20–21 | 2 | SubID (uint16 LE) | `0x0000` |
| 22 | 1 | State (1 = unlocked) | `0x01` |
| 23 | 1 | Padding | `0x00` |
| 24–27 | 4 | Type (uint32 LE, 1 = permanent) | `0x00000001` |

## Key Firmware Paths

| Path | Purpose |
|------|---------|
| `/HBpersistence/PagSWAct.001` | Activation data (old format, 24-byte records) |
| `/HBpersistence/PagSWAct.002` | Activation data (new format, 28-byte records) |
| `/HBpersistence/DBGModeActive` | Engineering mode flag (existence = enabled) |
| `/fs/usb0/` | USB mount point |
| `/HBbin/proc_scriptlauncher` | Script autorun daemon |

## Script Encoding

`proc_scriptlauncher` includes a `script_decoder` that XORs each byte with a PRNG key stream. The PRNG state is stored at `0x8043bb4` in the scriptlauncher's `.bss` section, initialized to 0. With seed = 0, the XOR key is 0 for every byte, meaning **plaintext scripts work directly**.

### PRNG Algorithm (if needed for encoded scripts)
```python
def prng_next(state):
    bit0 = state & 1
    r2 = ((state >> 1) | (bit0 << 31)) & 0xFFFFFFFF
    r1 = (((r2 >> 16) & 0xFF) + r2) & 0xFFFFFFFF
    r2 = (((r1 >> 8) & 0xFF) << 16) & 0xFFFFFFFF
    new_state = (r1 - r2) & 0xFFFFFFFF
    return state & 0xFF, new_state  # (key_byte, new_state)
```

## Activatable Features

| Feature | SWID | Description |
|---------|------|-------------|
| ENGINEERING | 0x010b | Full engineering/diagnostic menu |
| BTH | 0x010a | Bluetooth telephony |
| KOMP | 0x0106 | Component activation |
| Navigation | various | Regional map database activation |
| SDARS | — | Satellite radio |
| SSS | — | Speech recognition |
| TVINF | — | Video in motion |
| UMS | — | USB media support |

## Engineering Menu Access (After Activation)

Once the ENGINEERING activation code is accepted and `DBGModeActive` exists, the engineering menu should be accessible. Reported access methods:
- Hold **both rotary knobs** simultaneously for 5 seconds
- **Tuner + Info** button combination
- Some firmware versions: **Source + Sound** combo
