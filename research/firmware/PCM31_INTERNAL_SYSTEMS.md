# PCM 3.1 Internal Systems — Deep Dive

> Reverse-engineered from PCM3Root (6.6MB SH4 ELF)
> Updated: April 19, 2026

## 1. VIN Management System

The PCM has **two VIN sources** that serve different purposes:

### VIN Sources
```
CAN VIN (VIN_A)              Flash VIN (/HBpersistence/vin)
─────────────────            ─────────────────────────────
Read from instrument         Read from flash persistence
cluster via CAN bus          17-byte plaintext file
                            
AUTHORITATIVE for:           Used for:
 - Activation code verify    - Engineering menu display
 - Component protection      - FeatureLevel / bootscreen
 - Feature validation        - Demo VIN override
                             - Variant configuration
Cannot be changed by PCM     Written by Engineering menu
Always reflects real VIN     Can be overridden
```

### Key Functions
| Function | Purpose |
|----------|---------|
| `requestGetVIN_A()` | Request VIN from MOST network |
| `VIN_A from CAN: '%s'` | VIN received from CAN bus |
| `Using VIN_A from CAN!` | CAN VIN selected as source |
| `CGDeviceInfoServerIODevCtrl::readVINFromFlash` | Read /HBpersistence/vin |
| `writeVINToFlash(), VIN => %s` | Write to /HBpersistence/vin |
| `processVIN_A: VIN(A)='%s'` | Process received VIN |
| `ReadWriteVIN` | Combined read/write handler |
| `Performing %d request for VIN` | VIN request tracking |

### VIN Error Handling
```
"Cannot open vin file!"          → flash file doesn't exist
"vin file does not exist"        → first boot / factory reset
"vin file opened successfully"   → flash VIN loaded
"VIN could not be received correctly!" → CAN/MOST VIN failed
"VIN_A was not received!"        → no response from cluster
```

### Engineering Menu VIN Behavior (Observed on Car)
When selecting a demo VIN from PagSWAct.csv:
1. PCM reads real VIN from CAN (instrument cluster)
2. Loads demo VIN template (e.g., WP0AB2A78AL060050)
3. **Auto-merges** real VIN data into template (observed: serial "64179" from real VIN)
4. Writes merged VIN to /HBpersistence/vin
5. Changes FeatureLevel SubID to demo car's model (e.g., Panamera 0x002d)
6. Loads corresponding bootscreen
7. Activation codes STILL WORK because verification uses CAN VIN, not flash VIN

### VIN Hash (for activation codes)
Only positions [7, 9, 11, 12, 13, 14, 15, 16] are used:
```
Position: 0123456789ABCDEF0
VIN:      WP1AE2A28GLA64179
Used:            ^_^_^^  ^^^^^^
                 2 G A 6 4 1 7 9
```

## 2. Diagnostic State System

### DiagState Values
```
HBDiagnosisState = 0x%08X                    → base state (32-bit bitmask)
HBDiagnosisState = 0x%08X (with SecurityAccess) → elevated access
KWP2000DiagnosisState = 0x%X                 → KWP2000 compatibility layer
```

### Diagnostic Sessions
| Session | Purpose |
|---------|---------|
| `DIAG_SESSION_0` | Default / normal operation |
| `ActiveDiagSession(activeSession)` | Active diagnostic session |
| `WURDiagSession()` | Wake-Up Reason diagnostic session |
| `onEnterDiagSession` | Session entry handler |
| `DIAG_MODE_DEFAULT` | Switch off / force power down |

### Diagnostic Mode Control
```
requestSetDiagnosisMode(0x%08X)     → set mode (32-bit value)
requestGetHBDiagnosisState()        → query current state
requestGetKWP2000DiagnosisState()   → query KWP2000 state
DiagnosisActivationState = %s       → activation subsystem state
processDiagnosisUnlockRequest       → handle unlock attempt
```

### Component Diagnosis States
Each component has its own diagnosis state:
- SysInfo-SWActivation
- Bluetooth
- BTPhoneReceiver
- NADPhone
- SDARS
- DVD
- ADIV-Selftest (antenna)
- Mic-Selftest
- Video-Selftest

### Diagnostic Coding
```
DiagAuxilaryInputCoding=%d          → aux input configuration
DiagBluetoothCoding=%d              → BT module configuration
DiagMicrophoneTypeCoding=%s         → microphone type
DiagNADModuleCoding=%d              → NAD phone module
```
Stored in CVALUE files: `CVALUE0002032d.CVA` etc.

## 3. Component Protection (KOMP)

KOMP is **NOT traditional anti-theft**. It's the MOST network component registration system.

### What KOMP Actually Does
- Registers hardware components on the MOST (fiber optic) network
- Tracks which devices are present and authenticated
- Manages DTCP (Digital Transmission Content Protection) certificates
- Handles component hot-plug (connect/disconnect)

### Component Registration
```
requestSetInternalComponentPresent:
  - headunit       (always present)
  - navigation     (depends on activation)
  - phone          (NAD module)
  - DVDChanger     (disc drive)
  - SDS            (Speech Dialog System)
  - digitalradio   (DAB tuner)
  - iPod           (dock connector)
```

### Why Features Work Without KOMP
- KOMP activation unlocks the component registration system
- But the CAN VIN always matches (same car), so components authenticate anyway
- KOMP only fails when moving a PCM to a DIFFERENT car with a different VIN
- The activation code system (PagSWAct.002) is separate from component protection

## 4. Feature Level / Variant Coding

### Variant Coding Parameters
```
requestSetVariantCoding(
    VehicleType=0x%X,    → Cayenne(E)/911(G)/Boxster(S)/Panamera(C)
    RoofType=0x%X,       → Cabrio detection (Boxster identification)
    SteeringPos=%d,      → LHD (0) / RHD (1)
    ModelType=0x%X        → specific model variant
)
```

### FeatureLevel → Boot Screen Mapping
```
FeatureLevel SubID = Boot Screen Number (direct 1:1 mapping)

PCM reads: /HBpersistence/PagSWAct.002 → finds FeatureLevel record → SubID
PCM loads: /HBpersistence/CustomBootscreen_{SubID:03d}.bin
Fallback:  /mnt/share/bootscreens/CustomBootscreen_{SubID:03d}.bin

If no FeatureLevel: "No unlock code for FeatureLevel present, set empty PathToBootscreen"
```

### Known SubIDs by Market
| Model | EU SubID | NA SubID | Notes |
|-------|:--------:|:--------:|-------|
| Cayenne 958 | 0x0039 (57) | 0x0043 (67) | Confirmed on car |
| 991 Carrera | 0x0003 (3) | 0x000d (13)? | Needs verification |
| 991 Turbo | 0x0005 (5) | 0x000f (15)? | Needs verification |
| Panamera V8 | 0x002d (45) | 0x0037 (55)? | Needs verification |
| Cayenne V6 | 0x003f (63) | 0x0049 (73)? | Needs verification |

### Upgrade Level Check
```
"check upgrade level => %s (dataBase = %d / unlockCode = %d)"
"check upgrade level => %s (no info about upgrade level)"
```
NavDB activations also use an "upgrade level" system — the SubID (0x00FF for most)
determines which navigation database version is allowed.

## 5. Persistence System (FSC)

### Architecture
```
/HBpersistence/
  ├── EarlyPersistencyFiles/     → loaded at boot (critical settings)
  ├── NormalPersistencyFiles/     → loaded after startup
  │     ├── generalPersistencyData_DTCPDevCtrl
  │     ├── generalPersistencyData_{component}
  │     └── profilePersistencyData_{component}_{profile}
  ├── CVALUE*.CVA                → variant coding values
  ├── PagSWAct.002               → activation codes
  ├── vin                        → VIN override
  ├── CustomBootscreen_NNN.bin   → boot splash
  └── ...
```

### FSC State Machine
```
PS_LOADING_FSC                          → loading factory settings
PS_STORING_FSC                          → saving factory settings
PS_STORING_PERSADMIN_FSC_REQUIRED       → admin store needed
SS_PERSISTENCE_AND_FSC_READY            → system ready

Persistence states:
  STORE_PERSISTENCE_4                   → store request
  STORE_PERSISTENCE_ALLOWED_65          → store permitted
  STORE_PERSISTENCE_ALLOWED_RESET_96    → store + reset permitted
  STORE_PERSISTENCE_NOT_ALLOWED_RESET_97 → store blocked during reset
  PERSISTENCE_READY_STORED_170          → store complete
  PERSISTENCE_RESET_19                  → persistence reset
  EarlyPersistency_125                  → early load phase
  EarlyPersistencyAdmin_126             → early admin phase
```

### FSC Subsystems
| Code | System | Purpose |
|------|--------|---------|
| SV | Setting Value | Individual settings |
| SVI | Setting Value Instance | Indexed settings |
| SFS | Setting Factory Setting | Factory defaults |
| GFS | General Factory Setting | General defaults |
| DR | Data Reset | Factory reset data |
| CFS | Copy Factory Setting | Profile copy |

### Persistence Clients (52 total!)
Every major subsystem registers as a persistence client:
OnOff, GlobalSettings, SysInfo, Sound, Tuner, TVTuner, HMISettings,
Communication, Combi, Map, Diagnosis, HandSet, Telephone, SWDL,
LogBook, SportChrono, Trip, Media, Nav, and more.

## 6. CVALUE Files (Variant Coding Storage)

From the diagnostic dump:
```
CVALUE0002021b.CVA    →  DID 0x021B (audio settings?)
CVALUE00020226.CVA    →  DID 0x0226 (unknown)
CVALUE0002032d.CVA    →  DID 0x032D (diagnostic coding)
CVALUE000203b3.CVA    →  DID 0x03B3 (unknown, 172 bytes)
CVALUE0002064d.CVA    →  DID 0x064D (unknown)
CVALUE00020685.CVA    →  DID 0x0685 (170 bytes)
CVALUE00020686.CVA    →  DID 0x0686 (4270 bytes — largest!)
CVALUE00020687.CVA    →  DID 0x0687 (488 bytes)
CVALUE0002068c.CVA    →  DID 0x068C
CVALUE0002068d.CVA    →  DID 0x068D
CVALUE0002068e.CVA    →  DID 0x068E
CVALUE0002068f.CVA    →  DID 0x068F (5742 bytes)
CVALUE010b0006.CVA    →  0x010B = ENGINEERING, 0x0006 = variant?
```

The hex in the filename is the DID (Data Identifier) used by UDS/KWP2000
diagnostic protocols. These are the same DIDs that PIWIS reads/writes.

## 7. Open Questions

- [ ] What are the full DiagState bitmask values? (0x01=normal, 0x03=engineering?)
- [ ] Does KOMP check partial VIN or full VIN for anti-theft?
- [ ] What triggers the auto-merge of CAN VIN into demo VIN?
- [ ] Can we read CVALUE files via USB to decode variant coding?
- [ ] What DID values map to which vehicle parameters?
- [ ] Is SecurityAccess needed for certain Engineering operations?
- [ ] How does the FSC profile system work with key fobs (driver profiles)?

## 8. Firmware Variant Architecture (NEW — from ISO Extract analysis)

### Platform Codes
| Code | Platform | Model(s) |
|------|----------|----------|
| PCMG | G1 | 911/997 |
| PCME | E2 | Cayenne 958 |
| PCMC | C | Panamera 970 |
| PCMS | S | Boxster/Cayman 981 |

### Market Variants
| Prefix | Market | Key Differences |
|--------|--------|-----------------|
| RDW | Rest of World (EU) | Full feature set, EU nav, SDS/TTS |
| CHN | China | Asian speller (pinyin), CJK fonts, no SDS, no Browser |
| ARB | Arabic/Middle East | Arabic SSS config, full nav/map traces, PCM3Browser |
| LOW | Low-cost | Reduced feature set |

### IFS Binary Variants (fw400)
```
PCM3_IFS1.ifs              — Cayenne/Panamera (standard)
PCM3_IFS1_MOPF.ifs         — Cayenne/Panamera facelift
PCM3_IFS1_9x1.ifs          — 991 Carrera/Turbo
PCM3_IFS1_MOPF_9x1.ifs    — 991 facelift
PCM3_IFS1_Macan.ifs        — Macan 95B (NEW in fw400!)
PCM3_IFS1_MOPF_Macan.ifs  — Macan facelift
PCM3_IFS1_Navis.ifs        — Navigation-focused (CHN only)
PCM3_IFS2.ifs              — Shared resources (all platforms)
```

### Firmware Evolution (CHN200 → CHN400)
- fw200: 6 IFS files, no Macan, no MOPF, 4 IFS1 variants
- fw400: 10 IFS files, Macan added, MOPF variants, Emergency_LOW added
- Bootscreens: 0 in fw200/300, 79 in fw400
- IFS1 grew from 8.5MB to 10.2MB (+20%)
- IFS2 grew from 28MB to 32MB (+14%)

### Boot Screen Ranges (confirmed from fw300→fw400 diff)
| Range | Model | Added In | Status |
|-------|-------|----------|--------|
| 001-016 | 911/997 variants | fw300 (partial) | Known |
| 020-031 | Panamera variants | fw400 | New |
| 034-054 | 997/Panamera mixed | fw300 (partial) | Known |
| 056-067 | Cayenne 958 | fw300 (partial), 064-067 in fw400 | 067=NA confirmed |
| 071-079 | **Macan 95B** | fw400 | ✅ CONFIRMED by image! |
| 086-088 | Special editions | fw400 | 086=911 50th Anniversary |
| 094-099 | Unknown/regional | fw400 | 099=62KB (largest) |
