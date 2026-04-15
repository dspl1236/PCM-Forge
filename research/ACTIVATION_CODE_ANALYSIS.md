# PCM 3.1 Activation Code Analysis

## Andrew's Vehicle
- VIN: WP1AE2A28GLA64179
- PCM3.1 V4.76
- HWID: PCME02XX1221
- Cayenne 958, 2016 model year, Leipzig assembly

## PagSWAct.csv Structure

29 columns, semicolon-delimited:
- Col 0: Name (test label)
- Col 1: VIN (17-char)
- Col 2: Vehicle type (E1, E2, G1, 991, etc.)
- Col 3: ENGINEERING code (16-digit hex)
- Col 4-12: Feature codes (BTH, KOMP, FB, INDMEM, SDARS, SSS, SC, TVINF, UMS)
- Col 13: Navigation code
- Col 14-24: Regional NavDB codes
- Col 25-27: HDTuner, DABTuner, OnlineServices
- Col 28: FeatureLevel

## Known VIN/Code Pairs for ENGINEERING Menu

27 pairs extracted from PagSWAct.csv (see csv file for full data).
Same VIN always produces same code (verified with WP0ZZZ97Z8L040010).
All code values < 2^63.

## Algorithm Analysis

Tested and RULED OUT:
- MD5(VIN) — no match
- SHA1(VIN) — no match
- MD5(VIN + "ENGINEERING") — no match
- MD5(VIN + column_index) — no match

The algorithm is NOT a simple public hash of the VIN.
It's likely a keyed cipher or HMAC using a secret key embedded
in the PCM firmware. The key would be in the IFS images.

## Next Steps to Crack the Algorithm

1. **Extract PCM3_IFS1.ifs and PCM3_IFS2.ifs** from the firmware ISO
   - These QNX IFS images contain the application code
   - The activation validation function is in here

2. **Find the validation function** in the extracted binaries
   - Search for references to "PagSWAct" or the column names
   - The function that reads and validates CSV entries
   - Likely computes HMAC or keyed hash of (VIN + feature_id + secret_key)

3. **Extract the secret key** from the validation function
   - Once we have the key, generating codes is trivial
   - The key is probably a static byte array in the binary

4. **Alternative: Buy one code for Andrew's VIN**
   - $30-90 from euronavmaps for engineering menu activation
   - Gives us one more data point (Andrew's VIN → known code)
   - Also gets engineering menu access for further exploration

## IFS Image Analysis

### IFS1 (PCM3_IFS1.ifs) — 6.51 MB
- Standard QNX IFS format (starts with 0xEB 0x7E jump instruction)
- Contains 60 ELF binaries (SH architecture, Big-Endian + Little-Endian mixed)
- QNX 6.3.0SP1 confirmed (TAGID=330)
- Build date: 14.04.30 (April 30, 2014)
- Contains "SWActivation" string at 0x0055dcdf
- Context: "Qent %d (SysInfo-SWActivation) state 0x%02X"
- This is the boot/kernel IFS with base system services

### IFS2 (PCM3_IFS2.ifs) — 25.79 MB
- Harman Becker custom format ("hbcifs" magic at offset 0)
- Compressed — needs custom decompression to extract binaries
- Contains the main application code including:
  - MD5 references (5 occurrences) — crypto library present
  - NavDB_Eur — Navigation database activation
  - SDARS — Satellite radio activation (5 occurrences)
  - BTH — Bluetooth activation (18 occurrences)
  - VIN_A: '%s' — VIN processing with format string
  - KeyID — Key identifier system
  - UNLOCK_FUNC — Unlock function reference
  - CPEngineeringCAN — Engineering CAN interface
  - .csv — CSV file parsing
  - j9 — J9 JVM reference (same as MMI3G!)
  - 0123456789abcdef — Hex conversion table
  - CRC8 — CRC calculation
  - pcm3 — PCM3 identification

### Key Findings
1. The activation code algorithm is in IFS2
2. IFS2 uses HB custom compression ("hbcifs" format)
3. MD5 is present as a library — likely used in the code generation
4. VIN processing function found (VIN_A format string)
5. UNLOCK_FUNC and KeyID suggest a key-based unlock mechanism
6. The hex conversion table (0-f) is near offset 0x0000ccd1

### Next: Decompress hbcifs Format
The hbcifs format needs reverse engineering to extract the binaries.
Once extracted, the UNLOCK_FUNC and VIN processing code can be
analyzed in Ghidra to find the exact algorithm.

Alternative: The IFS1 contains the "SWActivation" state machine
which may have enough logic to understand the validation flow,
even if the actual crypto is in IFS2.

## IFS Firmware Analysis Session

### IFS Images Extracted
- PCM3_IFS1.ifs (6.8 MB) — QNX boot IFS, contains native binaries
- PCM3_IFS2.ifs (25.8 MB) — "hbcifs" format, contains application data

### Key Findings in IFS1

1. **TEA/XTEA delta constant (0x9E3779B9)** found at offset 0x000b2bc3
   - This confirms a TEA-family cipher is used somewhere in the system
   - Located in a binary between ldqnx.so.2 boundaries

2. **SWActivation system** at offset 0x0055dcdf
   - In a 2.5MB binary (0x0032f177 - 0x0058e37d)
   - Contains: "Qent %d (SysInfo-SWActivation) state 0x%02X"
   - Related strings: "Activated", "ENABLE", "Persistency_"
   - Feature names: "SGHDTunerEngineering"
   - "HexArray: len =#,=#X" — hex code parser
   - ". Displaying keys! " — debug key display
   - "MPLETELY_VALIDM" — validation result

3. **QNX filesystem contents identified**:
   - /bin/ksh, /bin/sh — shells
   - /usr/lib/ldqnx.so.2 — dynamic linker
   - /dev/ipc/ioc/c — IOC (V850) IPC device
   - proc/boot/server.cfg — boot configuration
   - Multiple shared libraries

4. **SH4 cross-tools installed**: sh4-linux-gnu-objdump available
   for disassembly, but offset alignment needs proper IFS extraction

### Brute Force Key Search Results

Tested with C implementation scanning entire IFS1 (6.8MB):
- Standard TEA encrypt with 10 VIN-to-input methods: NO MATCH
- Standard XTEA encrypt with 10 VIN-to-input methods: NO MATCH
- Both LE and BE key interpretations tested
- ~1.7M key positions tested per method

### Conclusion

The algorithm is NOT standard TEA/XTEA with a key directly stored
in IFS1 and VIN bytes as plaintext input. It's likely:

1. A **modified TEA/XTEA** with custom round function or key schedule
2. The input is **derived** from VIN (hashed/transformed before encryption)
3. The key might be **computed at runtime** from device-specific data
4. The 0x9E3779B9 constant might be used in a different algorithm
   entirely (e.g., Jenkins hash, or a custom mixing function)

### Next Steps

1. **Proper QNX IFS extraction** — Use dumpifs or write a complete
   QNX6 IFS parser to extract individual binaries
2. **SH4 Ghidra analysis** — Load extracted binaries with correct
   base addresses into Ghidra for proper function analysis  
3. **Focus on "HexArray" function** — This parses the 16-digit hex
   codes, the validation logic is near it
4. **Alternative: Buy one activation** — $150 gets engineering menu
   access AND a sample activation file to reverse engineer

## IFS Deep Analysis Session 2

### Corrected Understanding
- The IFS imagefs starts at offset 0x0000D10B (not 0x0000D108)
- The TEA delta constant (0x9E3779B9) at 0x000b2bc3 IS in the imagefs
- MD5 init constants found at 0x000bdf1e
- SHA256 H0 constant found at 0x000be212
- All crypto constants are in the same binary region

### Crypto Constants Found in IFS1 Imagefs
| Offset | Constant | Algorithm |
|--------|----------|-----------|
| 0x000b2bc3 | 0x9E3779B9 | TEA/XTEA/Golden ratio |
| 0x000bdf1e | 0x67452301 | MD5 init value A |
| 0x000bdf22 | 0x89ABCDEF | MD5 init value B |
| 0x000be212 | 0xD76AA478 | SHA256 H0 (round constant) |
| 0x0015ab89 | 0x67452301 | MD5 init A (in different binary) |

### What's Been Ruled Out
1. Standard TEA/XTEA with any 16-byte key from IFS1 — tested entire file
2. Simple MD5/SHA1/SHA256 of VIN+feature — no match
3. HMAC-MD5/SHA1 with obvious salt strings — no match
4. Direct hash with firmware string salts — no match

### What the Algorithm Likely Is
The activation code algorithm uses a **keyed construction** with a 
secret key embedded in the firmware. Options:
1. HMAC-MD5 or HMAC-SHA256 with a non-obvious key
2. A custom cipher using the golden ratio constant as a mixer
3. AES or similar block cipher with a firmware-derived key
4. A proprietary Harman Becker algorithm

### ELF Binary Structure in IFS
The QNX IFS uses a non-standard format for its embedded executables.
The `/usr/lib/ldqnx.so.2` references mark dynamically-linked binaries
but proper ELF headers aren't always present or correctly aligned.
The SH4 decompiler produces "bad instruction data" for many regions,
suggesting either compression, encryption, or alignment issues.

### Status
This is a deep reverse engineering task that requires:
1. A proper QNX IFS extraction tool (dumpifs or custom parser)
2. Correct identification of the SWActivation binary boundaries
3. Proper SH4 disassembly with correct base address/entry points
4. Tracing the code path from CSV parsing to code validation

The tooling is in place (Ghidra 11.3 with SH4 support, sh4-linux-gnu
cross-tools). The limitation is finding correct binary boundaries
within the QNX IFS format to feed clean executables to the disassembler.

### Practical Alternative
For $150, buying an engineering menu USB activation gives:
1. Immediate access to engineering menu on the Cayenne
2. The USB stick file format to reverse engineer
3. One confirmed VIN/code pair to validate future analysis
4. This approach may actually reveal the algorithm faster
   than firmware RE, since the USB stick format likely
   contains the activation code in a simple format

## MAJOR BREAKTHROUGH: QNX IFS Fully Extracted

### LZO Decompression Success
- Format: BE 16-bit length prefix per LZO block
- 227 blocks decompressed: 6.8MB → 14.2MB (matches image_size perfectly)
- imagefs header signature confirmed at byte 0

### Full IFS Extraction: 129 Files
- Complete QNX IFS directory parsed (image_attr struct format)
- All regular files, symlinks, and directory entries documented
- 80+ ELF binaries extracted (SH4A architecture, LE, QNX)
- Proper file offsets and sizes from directory entries

### Critical Binary: PCM3Root (5.8MB)
- **File**: mnt/ifs1/HBproject/PCM3Root  
- **Type**: ELF 32-bit LSB executable, Renesas SH (SH4A)
- **Entry point**: 0x8046360
- **Linked**: dynamically, interpreter /usr/lib/ldqnx.so.2
- **Contains**: SWActivation system, HexArray parser, all activation logic

### TEA Constant = RED HERRING
The 0x9E3779B9 constant is in **npm-tcpip-v4.so** (a TCP/IP networking
library), NOT in the activation code system. It's used for network 
protocol hashing, completely unrelated to activation codes.

### Ghidra Analysis of PCM3Root
- **12,604 functions** identified with SH4A processor
- Proper ELF loading with correct base addresses
- Decompiler produces readable C pseudocode
- Key string locations:
  - SWActivation at 0x084b8a5f
  - HexArray at 0x084bf800
  - Displaying keys at 0x0858a387
  - Activated at 0x084eb262
  - PersistencySysCtrl manages activation persistence

### Main App Architecture (from FUN_08048b98)
Subsystem controllers initialized:
- Bootstrap, OnOffDevCtrl, GauLogTrace
- OnOffPresCtrl (feature enable/disable)
- GlobalSettingsPresCtrl
- DSPHeartbeatMonitor, MOSTSubSystem, MOSTServiceBroker
- AudioAmplifier, PersistencySysCtrl (activation codes)
- FSCSysCtrl, ErrorMemory

### Next Steps
1. Find the function that READS activation codes from persistence
2. Trace to the VALIDATION function that compares VIN-derived code
3. Identify the crypto algorithm used (NOT TEA — that was a red herring)
4. Extract the secret key
5. Build the Python activation code generator
