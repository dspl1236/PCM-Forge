# How We Cracked the Porsche PCM 3.1 Activation System

> A complete narrative of reverse-engineering the Harman Becker PCM 3.1 infotainment
> system, from a firmware ISO file to generating activation codes for any VIN —
> and deploying them to a real Porsche Cayenne 958 via a $2 USB stick.
>
> **Researchers:** Andrew (dspl1236) + Claude (Anthropic)
> **Timeline:** April 16–18, 2026
> **Vehicle:** 2016 Porsche Cayenne 958, VIN WP1AE2A28GLA64179
> **Status:** ✅ Fully working — all features activated on real hardware

---

## Background

The Porsche PCM 3.1 (Porsche Communication Management) is a Harman Becker infotainment
system used across Porsche vehicles from 2011–2016: Cayenne (958), Panamera (970),
911 (991/997), Boxster/Cayman (981), and Macan (95B). It runs QNX 6.3.2 on a Renesas
SH-4A processor.

Many features — Bluetooth, navigation, Sport Chrono, Video in Motion, satellite radio —
are present in the firmware on every unit but locked behind activation codes. Porsche
dealers charge hundreds of dollars per feature, or owners buy PIWIS diagnostic tools
($3,000+) to enter codes. The codes are VIN-specific, meaning they can't be shared
between vehicles.

Andrew had been working on a related project (MMI3G-Toolkit) for Audi MMI3G+ systems,
which share the same Harman Becker platform. That prior work provided critical knowledge
about the QNX IFS format, the `proc_scriptlauncher` XOR cipher, and the `copie_scr.sh`
autorun mechanism — all of which turned out to be identical on the Porsche side.

---

## Phase 1: Firmware Extraction (April 16)

### The ISO

Andrew had a Porsche firmware update disc: `PCM_NA_20150721.ISO` (4.27GB, North America,
July 2015). Inside were multiple firmware variants for different regions:

```
PCM31RDW100, PCM31RDW200, PCM31RDW300, PCM31RDW400  (Rest of World)
PCM31LOW400                                           (Low-cost variant)
PCM31CHN100-400                                       (China)
PCM31ARB300, PCM31ARB400                              (Arabic/Middle East)
```

Each variant contained a `HEADUNIT/` directory with the IFS (Image Filesystem) images
and configuration files.

### QNX IFS Extraction

The IFS images are compressed QNX Image Filesystem files — a proprietary format that
contains the entire bootable OS image. Using tools from the MMI3G-Toolkit project:

1. `inflate_qnx.py` — decompresses the QNX LZO-compressed IFS
2. `extract_qnx_ifs.py` — parses the IFS header tables and extracts individual files

From `PCM31RDW400` IFS1, we extracted **176 files** including:

- **PCM3Root** (6.6MB) — the main HMI application, an SH-4 ELF binary
- **PCM3Reload** — hot-reload companion process
- **proc_scriptlauncher** (15.9KB) — the USB/SD card autorun handler
- **NavCore** — navigation engine
- Various device drivers, config files, and tools

### The Rosetta Stone: PagSWAct.csv

Inside the extracted firmware at `HEADUNIT/FIL/HBpersistence/PagSWAct.csv` was a
semicolon-delimited file with **27 test vectors**: VINs paired with pre-computed
activation codes for every feature. This was clearly a factory test/validation file
left in by Harman Becker engineers.

```
Name;     VIN;                VehicleType;  ENGINEERING;        BTH;                ...
Dummy;    WP0LLLL3L3L300815;  ;             047dc2feac32d109;   452917b7bc7d0afb;   ...
FzgUlm;   WP1ZZZ9PZ6LA49880;  E1 V8;       274980c77c1ea50f;   279a0032681a8411;   ...
SEB738;   WP0AB2A78AL060050;  G1 V8;        479dc41ecf7f287c;   251b130231cd9c95;   ...
```

This file was the key to everything — it gave us known inputs (VINs) and expected
outputs (activation codes) to verify against.

---

## Phase 2: Finding the Crypto (April 16–17)

### Ghidra SH-4 Decompilation

PCM3Root is a 6.6MB SH-4 ELF binary — the main application controlling the entire
infotainment system. We loaded it into Ghidra with the SH-4 processor module and
began searching for the activation system.

### String Hunting

The first lead came from string searches:

```
"SPHSysInfoSWActivation"        at 0x0051549d
"/HBpersistence/PagSWAct.002"   at 0x00588707
"Unlock file opened"            at 0x00588730
"Speller unlocked"              at 0x00588750
"Cannot open Unlock file!"      at 0x00588718
```

Following the cross-references from these strings led to the activation reader
function, which reads PagSWAct.002 from flash persistence, parses 28-byte records,
and calls a verification function on each code.

### The Verification Function: CPPorscheEncrypter

At address `0x08240df0`, Ghidra decompiled a 392-byte function that performed the
actual code verification. The structure was unmistakable:

1. Read 16-character hex string from PagSWAct.002 record (the "code")
2. Build a plaintext from the VIN and feature identifier
3. Perform modular exponentiation: `result = pow(code, E, N)`
4. Compare result to expected plaintext

This is textbook **RSA signature verification** — the code is a signature, and the
PCM verifies it using the public exponent.

### Extracting the Keys

The RSA parameters were stored as hex strings in the literal pool near the
verification function:

```
Address 0x082270b4: "69f39c927ef94985"  → N (modulus)
Address 0x082270b8: "4c1c5eeaf397c0b3"  → E (public exponent)
```

These are 64-bit values. In the RSA world, 64 bits is absurdly small — modern RSA
uses 2048+ bits. But in 2008 when this was designed, the SH-4 processor couldn't
efficiently handle large-number arithmetic, and the engineers probably assumed
nobody would extract the firmware.

### Factoring N

With a 64-bit modulus, factoring is trivial on any modern computer:

```
N = 0x69f39c927ef94985
N = 7,628,884,886,839,625,093
N = 1,831,263,461 × 4,169,044,001  (two 32-bit primes)
```

From the prime factors p and q:

```
φ(N) = (p-1)(q-1) = 7,628,884,881,839,317,632
E = 0x4c1c5eeaf397c0b3  (from firmware)
D = E⁻¹ mod φ(N) = 0x5483975015d0287b  (computed)
```

With D (the private exponent), we can generate codes — not just verify them.

### The VIN Hash

The VIN doesn't go directly into the plaintext. A hash function at `FUN_08240738`
(370 bytes) computes a weighted sum from specific VIN positions:

```python
def vin_to_number(vin):
    positions = [7, 9, 11, 12, 13, 14, 15, 16]  # skip check digit (8) and plant (10)
    result = 0
    weight = 10
    for pos in reversed(positions):
        c = vin.lower()[pos]
        b = int(c) if c.isdigit() else ord(c) % 10
        result = (result + b * weight) & 0xFFFFFFFF
        weight = (weight * 10) & 0xFFFF  # 16-bit overflow!
    return result
```

The 16-bit weight overflow is critical — miss that detail and every code is wrong.

### The Interleaving Trick

The final piece of the puzzle was how the plaintext is constructed. It's **not** a
simple concatenation of feature_hex + vin_hash. The two 8-character hex strings are
**interleaved** character by character:

```python
def interleave(feat_hex, vin_hex):
    return ''.join(feat_hex[i] + vin_hex[i] for i in range(8))

# Example: feat="010b0000", vin_hash="1a2b3c4d"
# Result:  "001102bb003c004d"  (NOT "010b00001a2b3c4d")
```

This interleaving step was not obvious from the decompilation — it required careful
tracing of the SH-4 register operations to understand the byte shuffling.

### Code Generation

With all pieces in place:

```python
N = 0x69f39c927ef94985
D = 0x5483975015d0287b  # private exponent (for signing)

def generate_code(vin, feature_hex):
    vin_hash = f"{vin_to_number(vin):08x}"
    plaintext = int(interleave(feature_hex, vin_hash), 16)
    return f"{pow(plaintext, D, N):016x}"
```

### Verification: 100% Match

We tested against all 27 VIN/code pairs in PagSWAct.csv — **every single code
matched perfectly**. The algorithm was cracked.

---

## Phase 3: The USB Stick Problem (April 17–18)

### First Attempts (Failed)

Andrew had previously attempted USB activation by placing `copie_scr.sh` and
`PagSWAct.002` on a FAT32 USB stick. The PCM recognized the USB (the media
player showed it) but nothing happened — no activation, no error, no feedback.

### The XOR Cipher Discovery

From the MMI3G-Toolkit work on Audi, we knew that `proc_scriptlauncher` XOR-decodes
`copie_scr.sh` before executing it. The cipher uses a PRNG seeded with `0x001be3ac`:

```python
class MMI3GCipher:
    SEED_INIT = 0x001be3ac

    def _prng_rand(self):
        r0 = self.seed & 0xFFFFFFFF
        r1 = ((self.seed >> 1) | (self.seed << 31)) & 0xFFFFFFFF
        r3 = (((r1 >> 16) & 0xFF) + r1) & 0xFFFFFFFF
        r1 = (((r3 >> 8) & 0xFF) << 16) & 0xFFFFFFFF
        r3 = (r3 - r1) & 0xFFFFFFFF
        self.seed = r3
        return r0

    def process(self, data):
        self.seed = self.SEED_INIT
        self._prng_rand()  # first call discarded
        return bytes(b ^ (self._prng_rand() & 0xFF) for b in data)
```

**This was why Andrew's early tests failed.** The script was plaintext on the USB
stick. When `proc_scriptlauncher` XOR-"decoded" the plaintext, it produced garbage,
which silently failed. The script needed to be XOR-encoded first so that the
decoder would produce valid shell script.

We verified the PCM 3.1 `proc_scriptlauncher` (15,940 bytes) was byte-for-byte
identical to the Audi MMI3G version — same cipher, same German debug strings
("Das Anlegen der decodierten Scriptdatei hat nicht geklappt"), same L. Koslowski
2008 copyright. Both platforms share the exact same autorun system.

### The Buffer Size Problem (Still Failed)

After XOR-encoding copie_scr.sh, we tried again. Still nothing — no `pcm_ran.txt`
appeared on the USB stick.

We examined a known-working DrGer MMI3G SD card that Andrew had from two years ago.
The structure was different from ours:

```
DrGer (WORKING):
  copie_scr.sh  — 536 bytes, XOR encoded, tiny bootstrap
  run.sh        — plaintext, actual payload
  bin/          — helper binaries

Ours (BROKEN):
  copie_scr.sh  — 5,209 bytes, XOR encoded, entire script inside
```

**The decoder had a buffer size limit.** DrGer's `copie_scr.sh` was a tiny
bootstrap (536 bytes) that just launched a plaintext `run.sh`. Ours tried to cram
the entire diagnostic script (5,209 bytes) into the encoded file, exceeding the
decoder's buffer.

### The Fix: Three-File Structure

We restructured to match the DrGer pattern:

```
USB root/
  copie_scr.sh   — 154 bytes, XOR encoded bootstrap:
                     #!/bin/ksh
                     export SDPATH=$1
                     mount -u $SDPATH
                     cd $SDPATH
                     exec ksh ./run.sh $SDPATH

  run.sh         — plaintext, diagnostic or activation script
  PagSWAct.002   — binary activation codes (28 bytes per feature)
```

### SUCCESS: Root Code Execution

With the three-file structure, `pcm_ran.txt` appeared on the USB stick:

```
PCM-Forge diag done
```

And `pcm_debug.log` contained a complete system dump from inside the Cayenne's
PCM — running as root on QNX 6.3.2.

---

## Phase 4: Live Activation (April 18)

### System Discovery

The diagnostic log revealed the PCM's internals:

```
Firmware: Porsche_PCM3.1_MOPF_SOP_STEP9.6_15245AS9
QNX:      6.3.2 PSP3 (built June 12, 2015)
IFS Type: IFS_G1_E2 (dual platform — 911 + Cayenne)
Audio:    BOSE amplifier
HDD:      195GB (5 partitions)
USB:      mounts at /mnt/umass20100t12, /fs/usb0, /fs/usb1
```

The factory PagSWAct.002 was 252 bytes (9 records = 9 features activated from the
factory). We also confirmed that `qconn` (QNX remote debug agent) and `inetd`
(telnet server) were already running.

### Feature Activation

Using the MANAGE BACKUP tab on the web app:

1. Uploaded the factory `PagSWAct_backup.002`
2. Decoded the existing 9 features
3. Added Sport Chrono and Video in Motion
4. Downloaded merged PagSWAct.002
5. Placed on USB with copie_scr.sh + run.sh
6. Inserted USB, waited 60 seconds, cycled ignition

**All features activated.** Engineering menu appeared with full PIWIS-equivalent
diagnostics. Video in Motion removed the speed lockout. Sport Chrono enabled
performance logging in the car settings. Satellite radio, Bluetooth, navigation —
everything working.

### The Engineering Menu: Built-in PIWIS

The ENGINEERING activation (SW 0x010b) unlocked the most valuable feature — a
complete built-in diagnostic tool with 18 sections including CAN bus viewer,
antenna diagnostics, speaker testing, HDD engineering, network configuration,
variant coding, factory reset, and the ability to enter activation codes directly
on the touchscreen without any USB stick or external tool.

---

## Phase 5: Building the Tools

### Web App (dspl1236.github.io/PCM-Forge)

A single-page web app with three tabs:

- **PIWIS** — enter VIN, get all 26 activation codes for manual entry
- **USB STICK** — build a complete USB activation kit (3 files)
- **MANAGE BACKUP** — upload factory backup, add features, download merged file

All computation runs locally in the browser using JavaScript BigInt. No server,
no API, no tracking. The XOR encoder, RSA math, and PagSWAct.002 binary builder
are all client-side.

### Desktop App (Electron)

A fully offline Windows application with three tabs:

- **Generate Codes** — same as web app
- **USB Stick** — build activation USB with diagnostic mode
- **Vehicle Connect** — ESP32 OBD-II dongle for live feature programming (future)

Auto-built via GitHub Actions CI/CD, releases at github.com/dspl1236/PCM-Forge/releases.

### Command Line (Python)

`generate_codes.py` — CLI tool for scripting and automation.

---

## Technical Summary

### The Algorithm

```
Input:  VIN (17 chars) + feature_hex (8 hex chars, e.g. "010b0000")
Output: activation_code (16 hex chars)

1. vin_hash = weighted_sum(VIN positions [7,9,11-16])  → 32-bit integer
2. vin_hex  = hex(vin_hash, 8 digits)
3. plaintext = interleave(feature_hex, vin_hex)         → 64-bit integer
4. code = pow(plaintext, D, N)                          → 64-bit RSA signature
5. code_string = hex(code, 16 digits)
```

### RSA Parameters

```
N (modulus)          = 0x69f39c927ef94985 = 1,831,263,461 × 4,169,044,001
D (private exponent) = 0x5483975015d0287b
E (public exponent)  = 0x4c1c5eeaf397c0b3
```

### PagSWAct.002 Binary Format

Each feature is a 28-byte record:

```
Offset  Size  Field
0x00    16    Activation code (ASCII hex, 16 chars)
0x10    2     Padding (zero)
0x12    2     SW_ID (uint16 LE, e.g. 0x010b = ENGINEERING)
0x14    2     Sub_ID (uint16 LE, e.g. 0x0000)
0x16    1     Active flag (1 = active)
0x17    1     Padding (zero)
0x18    4     Count (uint32 LE, always 1)
```

### USB Deployment

```
copie_scr.sh  — XOR encoded with PRNG seed 0x001be3ac (154 bytes)
                Decodes to bootstrap that launches run.sh
run.sh        — Plaintext shell script (activation or diagnostic)
                Backs up existing PagSWAct.002 before overwriting
PagSWAct.002  — Binary activation codes (28 bytes × N features)
```

### Key Firmware Locations (PCM3Root)

```
0x082270b4  RSA modulus N (hex string)
0x082270b8  RSA exponent E (hex string)
0x08240df0  CPPorscheEncrypter::verify (392 bytes)
0x08240738  VIN hash function (370 bytes)
0x082405a0  Modular exponentiation (186 bytes)
0x0051549d  "SPHSysInfoSWActivation" string
0x00588707  "/HBpersistence/PagSWAct.002" string
```

---

## Supported Models

| Model | SubID | Platform Code | Status |
|-------|:-----:|:---:|:---:|
| Cayenne 958 | 0x0039 | PCME | ✅ Tested on hardware |
| Cayenne 958 Turbo | 0x003b | PCME | ✅ Verified from CSV |
| Cayenne 958 V6 | 0x003f | PCME | ✅ Verified from CSV |
| 911 (991) Carrera | 0x0003 | PCMG | ✅ Verified from CSV |
| 911 (991) Turbo | 0x0005 | PCMG | ✅ Verified from CSV |
| Boxster/Cayman (981) | 0x0007 | PCMS | ✅ Verified from CSV |
| 911 (997) Carrera | 0x002a | PCMG | ✅ Verified from CSV |
| Panamera (970) | 0x002d | PCMC | ✅ Verified from CSV |
| 911 (997) Turbo | 0x002e | PCMG | ✅ Verified from CSV |
| Macan (95B) | ??? | PCME? | ❓ SubID unknown |

---

## Lessons Learned

1. **64-bit RSA is not security.** It's obscurity. A 2008 design decision for a
   resource-constrained SH-4 processor, but trivially broken by any modern computer.

2. **Identical code across brands.** Harman Becker reused the exact same
   `proc_scriptlauncher`, XOR cipher, and autorun mechanism across Porsche, Audi,
   VW, and Bentley. Breaking one breaks all.

3. **Test vectors are gold.** PagSWAct.csv gave us the answer key. Without it,
   we would have needed to brute-force the interleaving step, which is non-obvious
   from the decompiled code alone.

4. **Buffer limits matter.** The decoder's buffer size wasn't documented anywhere —
   we only discovered it by comparing our failing 5KB script to DrGer's working
   536-byte bootstrap.

5. **Firmware ships with debug tools.** The HDD contains `vi`, `ping`, `mmecli`,
   `taco` (5.3MB diagnostic tool), `sqlite_console`, and 25+ other utilities.
   `DBGModeActive` enables telnet. The Engineering menu is a built-in PIWIS.
   The security model assumed physical access = authorized access.

---

## Repository

- **GitHub:** github.com/dspl1236/PCM-Forge
- **Web tool:** dspl1236.github.io/PCM-Forge
- **License:** MIT
- **Research conducted under:** Anthropic Cyber Verification Program (CVP)
