# Cross-Platform Notes: PCM 3.1 ↔ PCM 4 / MIB2

This document compares the Porsche PCM 3.1 activation mechanism (what PCM-Forge exploits)
with the PCM 4 / MIB2 mechanism exploited by the [harman-f AIO project](https://github.com/harman-f)
and the [M.I.B. tool](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash).

Compiled during PCM-Forge research by reading harman-f's `addfec` and support scripts.

## Platform Generations

| Generation | Platform name | CPU / OS | Representative vehicles |
|---|---|---|---|
| PCM 3.1 | Harman Becker | Renesas SH4A / QNX 6.3.0 SP1 | Cayenne 958 (2011–2016), 911 991.1, Panamera 970, Boxster/Cayman 981, Macan 95B (pre-refresh) |
| PCM 4 / MHI2 / MIB2 | Harman | NVIDIA Tegra ARM / QNX 6.5.0 SP1 | Panamera 971, 911 991.2+, 718, Macan refresh |
| PCM 6 / MIB3 | Continental/CARIAD | ARM / Linux | Post-2020 Porsches |

Both PCM 3.1 and PCM 4 / MIB2 are from Harman, sharing some high-level architecture
(QNX-based, `.esd` engineering menu files, SD card script autorun). But their
**feature activation mechanisms are completely different**.

## Feature-Code Identifier Scheme (Shared Across Generations)

This is the surprising commonality: **both platforms use the same `SWID.SubID` hex
identifier scheme** for features.

```
PCM 3.1 record key:  010e0039      (SWID=0x010e FeatureLevel, SubID=0x0039 Cayenne 958)
PCM 4 FEC code:      00030000      (type=0x0003, sub=0x0000 — 911 Carrera variant)
                     00070100      (type=0x0007, sub=0x0100 — 991 Cab variant 0100)
                     06310099      (type=0x0631, sub=0x0099 — unknown higher-order group)
```

The SWIDs in PCM 3.1's `0x01xx` range (FeatureLevel=0x010e, BTH=0x010a, etc.)
don't appear in harman-f's `addFecs.txt` — those are PCM-3.1-specific Harman-Becker
feature codes. The MIB2 FECs harman-f adds are in the `0x0003`, `0x0006`, `0x0007`
range which map to **Porsche-specific features** (CarPlay, Android Auto, Navigation
activation) rather than Harman infotainment framework features.

**Implication:** the SWID namespace is shared but partitioned. Low SWIDs (0x00xx)
are Porsche-assigned feature codes. Higher SWIDs (0x01xx, 0x02xx on PCM 3.1) are
Harman-Becker/Becker-specific features.

## Activation File Formats

### PCM 3.1 — `PagSWAct.002` (28 bytes per record)

```
offset  size  field
  0-15    16  ASCII hex activation code (16 hex chars = 64-bit RSA result)
 16-17     2  padding (0x00 0x00)
 18-19     2  SWID (u16 little-endian)
 20-21     2  SubID (u16 little-endian)
    22     1  state (0x01 = unlocked)
    23     1  padding
 24-27     4  type (u32 LE, 0x00000001 = permanent)
```

The 16-char activation code is the **RSA-encrypted** result of interleaving the
feature constant (SWID+SubID) with the VIN-derived number.

### PCM 4 / MIB2 — `FecContainer.fec` (193-byte single records, variable multi-records)

Reverse-engineered from harman-f's `common/tools/addfec` shell script
([source](https://github.com/harman-f/MHI2_US_POG11_K5186_1-MU1476-AIO/blob/main/common/tools/addfec)):

File header:
```
offset  size  field
     0     1  FECCOUNT — number of FEC entries
   1-3     3  padding (0x000000)
```

Single FEC record (type 0x1102, 193 bytes):
```
offset  size  field
     0     1  0xAB — record start marker
   1-3     3  padding
   4-5     2  0x1102 — record type (single FEC)
   6-9     4  FEC code (e.g. 00030000, 00060100)
 10-14     5  VCRN (Vehicle Coding Resource Number) — 03FFFFFFFFFF = wildcard
 15-31    17  VIN (ASCII, space-padded if needed)
    32     1  padding
 33-36     4  epoch timestamp
 37-46    10  padding
47-175   129  RSA signature field — harman-f fills this with 0xFF bytes
176-179    4  0x01000000
180-183    4  FECLE — FEC code in byte-swapped little-endian (validation mirror)
184-187    4  0x01000000
188-191    4  0x03000000
   192     1  0xFF trailer
```

Multi-FEC record (type 0x1107, variable): packs multiple FEC codes into a single
signed block to reduce storage overhead.

## The Critical Difference: Where the Crypto Lives

### PCM 3.1: Crypto is IN the activation code

The 16-char hex activation code is itself the cryptographic proof:

```python
plaintext = interleave(feat_hex, vin_to_number(VIN))
code = pow(plaintext, d, n)          # RSA sign with private key
# PCM verifies: pow(code, e, n) == plaintext ?
```

The PCM's `CPPorscheEncrypter::verify` function performs the modexp and compares
the decrypted plaintext against the expected (feat_hex || vin_hex) structure.
**No valid code can exist without knowledge of the private key** — or the ability
to factor the 64-bit modulus (which is how PCM-Forge works).

### PCM 4 / MIB2: Crypto is skipped entirely

The FEC record has a 128-byte signature field that should contain an RSA signature.
But harman-f's `addfec` builds that field like this:

```bash
while [ ${#SIGNATURE} -ne 256 ]; do
    SIGNATURE="FF"$SIGNATURE
done
```

The signature is just **128 bytes of 0xFF**. There is no cryptographic operation.
The PCM 4 firmware either:
1. Doesn't validate the signature field at all (debug/leftover code path), or
2. Accepts all-0xFF as a special "unsigned/wildcard" debug signature

Either way, the result is the same: **FEC records require no cryptography to forge**.

## Why Each Platform Has a Different Exploit

The two exploits are structurally opposite:

| | PCM 3.1 | PCM 4 / MIB2 |
|---|---|---|
| Crypto validation | Strictly enforced (`CPPorscheEncrypter::verify`) | Bypassed (signature = 0xFF) |
| Key size | 64-bit RSA (weak) | Likely 1024+ bit on MIB2 secure boot, but irrelevant to FEC layer |
| Exploit | Factor the modulus, sign legitimately | Skip the signature entirely |
| Who can exploit | Anyone with modern compute | Anyone who can write the file to efs-persist |
| Delivery | `copie_scr.sh` via USB (unsigned scripts allowed) | `metainfo2` exploit in signed SWDL update bundle |

**On PCM 3.1** harman-f's approach wouldn't work — `CPPorscheEncrypter::verify`
actually checks the RSA, and an all-0xFF signature would be rejected. But because
PCM-Forge factored the modulus, we can produce mathematically-valid signatures
without touching the signature-validation code path.

**On PCM 4** PCM-Forge's approach wouldn't apply — MIB2 doesn't use the interleaved-
VIN-RSA scheme at all. Features are authorized by mere presence in `FecContainer.fec`,
which is trusted by the PCM when the 0xFF signature is there.

## Delivery Mechanism Differences

### PCM 3.1: `proc_scriptlauncher` + `copie_scr.sh`

```
1. USB inserted at /fs/usb0
2. proc_scriptlauncher (running as root) sees new mount
3. Looks for /fs/usb0/copie_scr.sh
4. XOR-decodes with PRNG (seed=0 → identity XOR → plaintext works)
5. Executes as root with /bin/ksh
6. Script copies PagSWAct.002 to /HBpersistence/PagSWAct.002
7. Touches /HBpersistence/DBGModeActive
8. PCM reboot validates and activates features
```

No firmware update required. No signed update bundle. No dealer tool.
The `copie_scr.sh` mechanism is a maintenance/diagnostic tool that was left open
on production firmware.

### PCM 4 / MIB2: `metainfo2` exploit within SWDL package

MIB2 firmware updates are delivered as digitally-signed SWDL packages that the
bootloader verifies before applying. However, harman-f and the M.I.B. project
discovered that:

1. The `metainfo2.txt` manifest inside the SWDL package is NOT signed
2. `metainfo2.txt` specifies which payloads to apply and in what order
3. The manifest includes a `FinalScriptMaxTime` field allowing 300s of arbitrary
   script execution as root after the "real" update completes

harman-f's AIO technique:
```
1. Take an official signed Porsche SWDL update
2. Modify metainfo2.txt to include finalScriptSequence.sh
3. The script runs the pre-compiled helpers: addfec, navon, wlan, gem install, etc.
4. FecContainer.fec is rewritten with all desired FECs using all-0xFF signatures
5. Navigation, CarPlay, Android Auto, WLAN, GEM all become enabled
6. The "update" ends and the unit boots with expanded features
```

This works for vehicles whose firmware train is in harman-f's supported list
(MHI2 US POG11 and related variants). Not every Porsche PCM 4 is exploitable —
the metainfo2 bug has been partially patched in newer firmware.

## Shared Infrastructure

Despite the different activation mechanisms, several components are identical or
near-identical across generations:

| Component | PCM 3.1 | PCM 4 / MIB2 |
|---|---|---|
| Engineering menu | `.esd` files in `/mnt/efs-system/engdefs/` | `.esd` files in `/eso/hmi/engdefs/` |
| Engineering menu access | Hidden button combo (varies by model) | Hidden button combo (CAR + TUNER on some variants) |
| SD card script autorun | `proc_scriptlauncher` + XOR-encoded `copie_scr.sh` | `proc_scriptlauncher` + `metainfo2` |
| Persistent storage | `/mnt/efs-persist/`, `/HBpersistence/` | `/net/rcc/mnt/efs-persist/` |
| OS | QNX 6.3.0 SP1 | QNX 6.5.0 SP1 |

PCM-Forge's Audi sister project [MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit)
exploits the same `copie_scr.sh` mechanism on the PCM 3.1 generation of Audi MMI
(MMI 3G / 3G+ / RNS-850). The shared Harman Becker heritage means the exploit
surface is nearly identical between Audi MMI3G+ and Porsche PCM 3.1.

## References

- [harman-f/MHI2_US_POG11_K5186_1-MU1476-AIO](https://github.com/harman-f/MHI2_US_POG11_K5186_1-MU1476-AIO)
  — The AIO firmware package that prompted this comparison. License: GPL-2.0.
- [Mr-MIBonk/M.I.B._More-Incredible-Bash](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash)
  — The underlying bash framework that harman-f's apps are built on.
- [mibsolution.one](https://mibsolution.one/) — Community firmware hosting.
- [mibwiki.one](https://mibwiki.one/) — MIB2 reverse engineering documentation.
- [DrGER2](https://github.com/DrGER2) — Audi MMI3G+ research. Same copie_scr.sh
  mechanism, different vehicle platform.

## What This Means for PCM-Forge Users

None of the MIB2 work applies to your Cayenne 958, 911 991.1, Boxster 981, Macan 95B,
or any PCM 3.1 vehicle. If you're on those platforms, PCM-Forge is the correct tool.

If you have a newer Porsche (2016+ Panamera, 991.2+, 718, refreshed Macan), you likely
have PCM 4 / MIB2 and should use harman-f's AIO updates and/or the M.I.B. tool.
They are well-maintained, have an active community, and work on the appropriate
attack surface for that platform.
