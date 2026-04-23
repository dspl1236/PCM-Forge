# PCM4 / MHI2 FEC Activation System

## Overview

PCM4 (Porsche Communication Management 4.0) uses the **FEC (Feature Enablement Code)** system
for feature activation — the MIB2-generation successor to PCM 3.1's PagSWAct RSA-64 codes.

FEC is shared across the entire VAG MIB2 ecosystem: Audi, VW, Porsche, Bentley, Skoda, SEAT.
It is architecturally related to — but distinct from — **Component Protection (CP)** on Audi MMI3G+.

## Comparison: PCM 3.1 vs PCM 4 vs Audi CP

| Aspect | PCM 3.1 (PagSWAct) | PCM 4 / MIB2 (FEC) | Audi MMI3G+ (CP) |
|--------|-------------------|-------------------|------------------|
| File | PagSWAct.002 | FecContainer.fec | Per-module EEPROM |
| Crypto | RSA-64 (CRACKED) | RIPEMD-160 + RSA | AES-128 / UDS challenge |
| Binding | VIN-based | VIN + VCRN | ECU serial (FAZIT) |
| Location | /HBpersistence/ | /mnt/efs-persist/FEC/ | J533/J255 internal |
| Bypass | Code generation | IFS patch + FEC inject | Key extraction via UDS |
| Scope | Single head unit | Head unit (MMX+RCC) | Per-ECU (gateway, HVAC, etc.) |
| Protocol | Offline codes | SWaP (Software as Product) | UDS RoutineControl |

## FecContainer.fec Binary Format

Based on community reverse engineering (MIB2_FEC_Generator.sh):

```
OFFSET  SIZE    FIELD
0x00    4       File version/type marker (\x01\x00\x00\x00)
0x04    4       File size (little-endian)
0x08    4       Magic bytes
0x0C    4       Version
0x10    10      VCRN (Vehicle Component Registration Number)
0x1A    17      VIN (ASCII, null-terminated)
0x2B    8       Epoch timestamp (hex)
0x33    4       FEC count (little-endian, 32-bit)
0x37    N×4     FEC codes (4 bytes each, big-endian)
...     64      RIPEMD-160 signature (RSA-signed digest)
...     N×4     LE FEC list (repeated for ExceptionList)
...     12      Trailer bytes
```

### Signature Verification
- Hash: RIPEMD-160 of the data block (magic through FEC list)
- Signing: RSA private key (`MIB-High_FEC_private.pem`)
- Verification: MIBRoot checks signature against embedded public key
- **Bypass: Patch MIBRoot in IFS stage2 to skip signature check**

### VCRN (Vehicle Component Registration Number)
- 10-byte identifier tying FECs to a specific head unit
- Obtainable via PIWIS measurement channels or hex dump of FecContainer
- Required input for FEC generation alongside VIN

## Known FEC Codes

### Core Feature FECs (4 bytes each, big-endian hex)
```
00030000    SWaP base / Component Protection
00030001    SWaP variant
00040100    Voice Control
00050000    Navigation
00060100    Map update entitlement (base)
00060500    Map region variant
00060700    Map update (alternate)
00060800    CarPlay
00060900    Android Auto
00060A00    MirrorLink
00070100    AMI / Media Interface
00070200    AMI variant

023000XX    Map update expiry (XX = year/region code)
023D00XX    Map update unlimited (XX = region)
            00EE = Europe ROW
            0032 = North America
```

### Map Expiry Byte (last byte of 0230/023D)
The final byte encodes the expiry year or unlimited status:
- `0x20` = base entitlement
- `0x26` = valid until 2026
- `0x4A` = valid until 2030+ (community trick)
- `0xEE` = Europe/ROW region
- `0xFF` = unlimited

### Performance Monitor / Sport Features
```
00030000    Required base FEC
+ VCDS/PIWIS adaptation for display activation
```

## ExceptionList.txt

The ExceptionList provides a firmware-level bypass mechanism:

```ini
# Exception list for development purpose (MIB2plus-High)

#StartOfFazitIDs
#EndOfFazitIDs

[SupportedFSC]
#EndOfFSCs

[ECU-Signature]
signature1 = "47b7c2890cfcd99da63797fd092c6bfc"  # MD5
signature2 = "e3c58cd0a5a3b3cc70493a15dc9c1e7f"
...
signature8 = "013bcaa24fc396808baa65179a4ca596"
```

### ExceptionList Fields
- **FazitIDs**: Factory serial numbers that bypass CP checks
- **SupportedFSC**: Freischaltcode list (activation codes that pass without signing)
- **ECU-Signature**: MD5 hashes of authorized ECU configurations
- Installed to `/mnt/persist_new/` during firmware update
- Can be injected via SD card update without root access

### ExceptionList BUG (documented by Mr-MIBonk)
A known bug allows ExceptionList to override FEC validation — FECs listed
in the ExceptionList are treated as valid regardless of FecContainer signing.

## Connection to Audi Component Protection

### Shared Heritage
FEC and CP are both Harman-designed feature-locking mechanisms:

| Layer | CP (Audi MMI3G+) | FEC (MIB2/PCM4) |
|-------|-----------------|-----------------|
| Purpose | Lock features to specific ECU | Lock features to specific head unit |
| Identity | FAZIT (factory serial) | VCRN + VIN |
| Transport | UDS RoutineControl 0x31 | File-based (FecContainer.fec) |
| Crypto | AES-128 challenge-response | RIPEMD-160 + RSA signing |
| Storage | ECU EEPROM | QNX filesystem |
| Bypass | Extract keys via DID reads | Patch IFS + inject FecContainer |

### Your CP Research (VAG-CP-Docs) Cross-Reference
- CP Gen3 `RoutiContrStartRoutiCompoProte` maps to FEC's signing verification
- Both use per-device binding (FAZIT ↔ VCRN)
- Both can be bypassed by neutralizing the verification layer
- CP keys are in ECU EEPROM; FEC keys are in the IFS filesystem
- J533 gateway CP ↔ RCC Component Protection on MIB2 (same concept, different bus)

## PCM4 Architecture for FEC

```
┌─────────────────────────────────────┐
│          PCM4 Head Unit             │
│                                     │
│  ┌──────────┐    ┌──────────┐      │
│  │  MMX2P   │    │   RCC    │      │
│  │ (QNX)    │◄──►│ (QNX)    │      │
│  │ Display  │MOST│ Radio    │      │
│  │ Nav/Media│150 │ CAN bus  │      │
│  │ FEC check│    │ Telnet   │      │
│  └──────────┘    └──────────┘      │
│       │                │            │
│       ▼                ▼            │
│  /mnt/efs-persist/    /mnt/efs-persist/
│  └─FEC/               (RCC side)   │
│    └─FecContainer.fec              │
│    └─ExceptionList.txt             │
│                                     │
│  ┌──────────┐                      │
│  │ SubCPU   │  (IOC / V850)        │
│  │ Variant  │  (EEPROM CP data)    │
│  └──────────┘                      │
└─────────────────────────────────────┘
```

### Root Access Path
1. Connect USB ethernet adapter (AX88772/A)
2. Static IP: laptop 172.16.250.250, PCM at 172.16.250.248
3. Telnet to port 123 (NOT port 23 like PCM3.1)
4. Login: `root` / password from MHI2 password list
5. Known passwords: `oaIQOqkW`, `CeaCCDmi`, `waMC0ISm`

### FEC Activation Workflow
1. **Export existing FECs**: `cat /mnt/efs-persist/FEC/FecContainer.fec | hexdump`
2. **Note VCRN**: bytes 0x10-0x19 of FecContainer
3. **Generate new FecContainer**: MIB2_FEC_Generator.sh with desired FEC codes
4. **Patch IFS**: Remove signature verification from MIBRoot
5. **Flash patched IFS**: `flashunlock` → `flash.it` → `flashlock`
6. **Copy new FecContainer**: Replace on efs-persist
7. **Reboot**: Hold power 30s

### Alternative (No Root Required)
ExceptionList injection via SD card update:
1. Prepare custom update package with ExceptionList.txt
2. Add desired FEC codes to the list
3. Install via standard SWDL update process
4. Codes appear as valid (ExceptionList bug)

## Firmware Packages on Hand

### MH2p_ER_POG35_K9829_9Y0919360B (Cayenne E3)
- Platform: MHI2P (Porsche variant)
- Part: 9Y0919360B
- Format: JSON manifests, sequential SWUP
- Hardware: CLU24 + NL3017 configs
- ExceptionList: 8 ECU signatures, empty FSC/FAZIT lists

### MHI2_US_POG24_K5136_MU1416 (718/Macan US)
- Platform: MHI2 standard
- Format: metainfo2.txt + .dat update files
- Variant: FM2-P-TNSL-US-PO-MLE
- Region: USA
- Vendor: HARMAN (HAD)

## Research Priorities

1. [ ] Decode FecContainer.fec format from a live car (need root shell)
2. [ ] Map FEC codes to Porsche-specific features (PCM4 vs generic MIB2)
3. [ ] Cross-reference ExceptionList ECU signatures with car's actual config
4. [ ] Compare FEC verification to CP Gen3 routine (shared Harman codebase?)
5. [ ] Document POG35 vs POG24 FEC differences
6. [ ] Build FEC analysis tool for PCM-Forge (parse + display FecContainer)
7. [ ] Investigate ExceptionList injection path for PCM4 specifically
