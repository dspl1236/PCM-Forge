# PCM 4 / MIB2 — Activation & Component Protection Research

## Firmware Source

```
D:\MMI\MHI2_ER_POG24_K5137_MU1417_971919360T
  Part: 971919360T (Panamera)
  Vendor: HARMAN (HAD)
  Variant: FM2-P-N-EU-PO-MLE (Premium, Navigation, Europe, Porsche)
  Region: Europe + RoW
```

## Platform Architecture

| Component | Platform | Size | Role |
|-----------|----------|------|------|
| MMX2 | **QNX 6.5.0 SP1 on NVIDIA Tegra 3 (ARMv7 Cortex-A9)** — NOT Linux (corrected Session 5) | 716MB / 972MB app.img | Main HMI, Java apps, SWaP logic |
| RCC | QNX (machine=0x28 ARM per IFS header; "SH4" unverified) | 22MB ifs-root.ifs | Radio, media, CAN |
| IOC | V850 | 1.1MB per variant | CAN bus, power management |
| DU | — | 555–653KB | Display units |

### IOC Variants (V850 firmware for each VW Group platform)

| Binary | Platform |
|--------|----------|
| V850app_MLBPO.bin | **Porsche MLB** (Cayenne/Macan/Panamera) |
| V850app_MLB.bin | Audi MLB (A4/A5/Q7 older) |
| V850app_MLBEVO.bin | Audi MLB Evo (A4/A5/Q5/Q7 newer) |
| V850app_MQB.bin | VW MQB (Golf/Passat) |
| V850app_MQBTT.bin | Audi MQB TT |
| V850app_MSSR8.bin | Bentley |

## Activation System: SWaP (Software as Product)

### Architecture (from firmware string analysis)

```
Java HMI Layer
  de/audi/tghu/dsitrace/DSISWaPProxy.class
  de/audi/tghu/dsitrace/DSISWaPListenerProxy.class
      ↓ DSI interface (same framework as PCM 3.1!)
      ↓ @updateSWaPStatus:@status=i@validFlag=i
      ↓ @updateSWaPStatus:@swapStatus=i@validFlag=i
      ↓ @getPublicKey:@publicKey=#iS@valid=b
Native C++ Layer
  asi::fec::ComponentProtection
  asi::sdisComponentProtection
  FecDSICompProtImpl
      ↓ getFscDetails
      ↓ checkFecAppInfo
      ↓ encryptFile
      ↓ getPublicKey
      ↓ getHistory
Crypto Layer
  RIPEMD-160 (signature verification)
  RSA (public/private key pair)
Persistence
  CPersistencyContainer
  FecContainer (VCRN + VIN + date)
```

### Key DSI Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| updateSWaPStatus | `@status=i @validFlag=i` | Set feature activation state |
| getPublicKey | `@publicKey=#iS @valid=b` | Retrieve public key locally |
| getFscDetails | — | Get FSC code details |
| checkFecAppInfo | — | Validate FEC container |
| encryptFile | — | File encryption |
| getHistory | — | Activation history |

### Configuration

`asi.sdisComponentProtection.ems_table.json` — JSON config for CP system.

### ExceptionList (Bypass)

Located at `common/tools/0/default/ExceptionList.txt`:
- `[SupportedFSC]` section — currently EMPTY (no pre-approved codes)
- 8 MD5 signature hashes validate the file integrity
- Boardbook and PPOI data paths defined
- Script at `common/tools/0/default/finalScript.sh` runs with SHA1 checksum verification

### FEC Activation Parameters

From DSI string: `@version=uiC @vin=s @vcrn=s @date=s`

| Parameter | Type | Description |
|-----------|------|-------------|
| version | unsigned int | FEC format version |
| vin | string | Vehicle Identification Number |
| vcrn | string | Vehicle Component Registration Number |
| date | string | Activation date |

### VCRN Runtime Check

```
idx [%X] state [%X] vcrn [%s]
```
Logs index, state, and VCRN during activation validation.

## Key Observations

### Potentially Offline (like PCM 3.1!)

- `getPublicKey` retrieves the key LOCALLY via DSI — no server call
- `getFscDetails` operates locally
- `ExceptionList` is a local bypass mechanism
- `CPersistencyContainer` stores state locally
- NO `onlineActivation`, `server`, `cloud`, `backend` references found in CP code paths
- **Hypothesis: Porsche may be running FEC/SWaP entirely offline, same as PCM 3.1**

### Same DSI Framework

The DSI (Device Service Interface) proxy/stub pattern is identical to PCM 3.1 / MMI3G+. Java wraps native C++ via DSI. If we can call `getPublicKey` from a root shell, we get the key directly.

### RSA Key Size: 2048-bit (CONFIRMED)

All 345 RSA public keys found in the app.img are **2048-bit** (257-byte modulus, DER SubjectPublicKeyInfo format). No smaller keys found anywhere in the 716MB image.

This is a fundamentally different security posture from PCM 3.1:
- **PCM 3.1:** RSA-64 — factored in milliseconds
- **PCM 4:** RSA-2048 — not factorable with current technology

**However, the key itself is NOT the only attack surface.** Other vectors:
1. ExceptionList bypass — the `[SupportedFSC]` section is validated by MD5 signatures, not RSA. MD5 is broken.
2. `importFSCsList` function — may accept unsigned or weakly verified lists
3. Logic flaws in FecDSICompProtImpl — state machine bypass, race conditions
4. The system is confirmed OFFLINE — no server-side validation to bypass

## Crypto Libraries Present

| Library | Purpose |
|---------|---------|
| RIPEMD-160 | Signature verification for FEC containers |
| RSA | Public/private key operations |
| MD5 | ExceptionList integrity verification |
| SHA1 | Script checksum verification |
| AES | Present (encryption) |

## Next Steps

1. **Mount/extract app.img** — identify filesystem format (not FAT despite EB1090 header), extract to access binaries
2. **Extract ems_table.json** — full CP configuration
3. ~~Find RSA key size~~ — **DONE: 2048-bit, not factorable**
4. **Extract DSISWaPProxy.class** — decompile Java for activation logic
5. **Extract FecDSICompProtImpl binary** — Ghidra analysis of native CP implementation
6. **Root shell on PCM 4** — call getPublicKey via DSI to get the key directly
7. **Compare Porsche vs Audi** — does Porsche strip online validation like they did with PCM 3.1?

## Comparison: PCM 3.1 vs PCM 4

| Feature | PCM 3.1 (HN+) | PCM 4 (MIB2) |
|---------|---------------|--------------|
| CPU | Renesas SH4 | ARM (Linux) + SH4 (QNX) |
| OS | QNX 6.3.2 | Linux (MMX2) + QNX (RCC) |
| Activation | RSA-64 / PagSWAct.002 | FEC / SWaP / RIPEMD-160 |
| Key size | 64-bit (cracked) | 2048-bit (not crackable via factoring) |
| Validation | Offline | Likely offline (TBD) |
| DSI framework | Yes | Yes (identical) |
| Java layer | Yes (limited) | Yes (extensive) |
| CP enforcement | None | FecDSICompProtImpl |
| ExceptionList | N/A | Present (empty) |
| Modem | Cinterion AC75i (2G) | Cinterion ALS6 (LTE!) |

## Files of Interest

```
MMX2/app/50/default/app.img          — 716MB Linux app filesystem
MMX2/app/70/default/app.img          — 972MB Linux app filesystem (variant)
RCC/ifs-root/31/default/ifs-root.ifs — 22MB QNX IFS (radio controller)
IOC/Main/31/default/V850app_MLBPO.bin — 1.1MB Porsche V850 IOC
common/tools/0/default/ExceptionList.txt — FEC bypass list
common/tools/0/default/disableGEM    — 27KB binary
common/tools/0/default/finalScript.sh — update finalization
```

## Binaries Extracted

### libSdisComponentProtection.so (223KB ARM EXEC)
- Extracted from app.img at offset 0x1CEABC00
- Component Protection handler — DSI proxy to FecManager
- 44 references to "ComponentProtection", 2 to "FecDSI"
- **NO online/server references** — confirmed offline
- Build path: `/home/jenkins/workspace/PM_build_swdl/fec/../framework/qnx_arm_mmx_sdk/`
- Links to `libcrypto.so.2` (OpenSSL), uses `d2i_RSA_PUBKEY`, `EVP_PKEY_set1_RSA`

### Media Launcher (781KB ARM EXEC)
- Extracted from app.img at offset 0x1CBCB400
- Main application with media, persistence, SWDL functionality
- Contains `verifyCustomerUpdate` function
- File paths reveal QNX ARM architecture (`/mnt/app/armle/bin`)
- RCC accessible via `/net/rcc/mnt/efs-persist/`

## Attack Surface Analysis

### Not Viable: RSA Key Factoring
All RSA keys are 2048-bit. Factoring is not feasible.

### Potentially Viable: ExceptionList Bypass
The ExceptionList.txt uses 8 **MD5** hashes for integrity validation. MD5 is cryptographically broken — collision attacks are practical. If we can forge a valid MD5 signature for a modified ExceptionList with populated `[SupportedFSC]` entries, features could be activated without valid FEC containers.

### Potentially Viable: FSC Import
The `importFSCsList` DSI function accepts a list of FSC codes. If the validation of imported codes is weak or bypassable, codes could be injected directly.

### Potentially Viable: State Machine Bypass
The FEC state machine logs `fecState`, `fsid`, and state transitions. If there's a way to force a state transition (e.g., from "locked" to "unlocked") without proper cryptographic verification, features could be enabled. The `ignore fsid [0x%X] fecState [%d]` vs `include fsid [0x%X] fecState [%d]` logic is worth analyzing in Ghidra.

### Requires Investigation: Porsche-Specific Differences
PCM 3.1 proved that Porsche strips security relative to Audi. The MIB2 platform may have Porsche-specific weaknesses not present in Audi. Need to compare the Porsche MLBPO IOC firmware with the Audi MLB variant.

## Session 2 Findings: Bypass Mechanisms

### 1. SWDL Skip Flags (swdlclient binary, 833KB ARM)

The firmware update client has compiled-in checksum bypass flags:

| Flag | Description |
|------|-------------|
| `m_skipCheckSum` | Skip all checksum validation |
| `m_skipFileCopyChecksum` | Skip file copy checksums |
| `SkipCheckSum` | Named config option |
| `CheckType Skip` | First-class "skip" check type |
| `skipinit` | Skip initialization |

Config file: `/var/swdl/swdlclient.cfg` (writable, ramdisk)

Build path: `/home/jenkins/workspace/PM_build_swdl/swdl/swdlclient/`

### 2. Engineering Mode DSI Flag

```
@updateIsEngineeringMode:@isEngineeringMode=b@validFlag=i
```

Engineering Mode is a **settable boolean** via DSI. If calling this function with `isEngineeringMode=true` disables CP enforcement...

### 3. Debug Mode DSI Flag

```
@useDebugMode:@display_id=i@use=b
```

Debug mode is also a DSI boolean. Combined with Engineering Mode, this could bypass validation.

### 4. ESD Test Screens (same format as PCM 3.1!)

```
DABTUNER_ENABLE_TEST_MODE
  label    "Test Mode"
  poll     2000
```

The ESD engineering screen format is **identical** to PCM 3.1. Custom ESD screens with `sys 1 0x0100 "cmd"` may work for script execution.

### 5. RSA Implementation Details

Custom RSA implementation at `swdllib/src/cryptolib/rsa.c` (not just OpenSSL wrapper).

Functions: `calcSignature`, `restoreSignature`, `destroySignature`, `Could not decrypt signature`

This is used for SWDL verification, possibly shared with FEC validation.

### 6. Challenge-Response CP Authentication (ems_table.json)

```
@requestAuthString:@challenge=s
@replyAuthString:@challenge=s@response=s
@replyAuthString:@challenge=s@response=s@mac=s
```

Module-to-module authentication on MOST bus. Head unit authenticates to protected components using stored key. All local, no server.

### 7. Production Whitelist

`/app/eso/production/whitelist.txt` — a production whitelist file. Purpose unknown.

### 8. Key File Paths

| Path | Purpose |
|------|---------|
| `/var/swdl/swdlclient.cfg` | SWDL config (writable) |
| `/net/rcc/mnt/efs-persist/SWDL/` | RCC-side SWDL state |
| `/mnt/persist/var/swdl/` | Persistent SWDL data |
| `/mnt/app/eso/bin/apps/` | Application binaries |
| `/app/eso/production/whitelist.txt` | Production whitelist |
| `/etc/openssl/cert.pem` | Certificate store |

## Updated Attack Vectors (Priority Order)

1. **Engineering Mode DSI flag** — simplest if it disables CP. Just call the DSI function.
2. **SWDL skip flags** — modify swdlclient.cfg to flash custom firmware with CP disabled.
3. **ExceptionList MD5 forge** — populate SupportedFSC with desired feature IDs, forge MD5 signature.
4. **ESD script execution** — deploy custom ESD screens that call DSI functions to set Engineering/Debug modes.
5. **FEC state machine** — Ghidra analysis of `include`/`ignore` fsid logic for state bypass.

## Session 3 Findings: GEM Feature Toggle (THE SIMPLE PATH)

### Navigation Enabled via GEM File Flag

The navigation startup controller (`PCStarterImpl` in the nav binary) checks a
**local file flag** to decide whether navigation runs:

```
/navigation/FSID_Navi_Enabled    -> "Navigation Application ENABLED via GEM!"
/navigation/FSID_Navi_Disabled   -> "Navigation Application DISABLED via GEM!"
NaviApplicationEnabledState: oldstate=... newState=...
"Navigation not enabled! Shutdown..."
"Navigation enabled. Restart to take effect..."
```

**This is a file-presence / persistence flag check, NOT a per-boot cryptographic
FEC validation.** The string explicitly says "via GEM" — the engineering menu can
toggle navigation on/off directly.

### Two-Layer Architecture

The MIB2 activation has two distinct layers:

1. **FEC / SWaP layer (2048-bit RSA)** — the official VAG activation. Validates FEC
   containers cryptographically and writes the resulting feature state into persistence.

2. **Application layer (FSID flags)** — individual apps (navigation, etc.) check a
   local FSID flag in persistence to decide whether to run. These flags are what GEM
   sets directly.

The crypto gate is at the FEC import step. But if GEM (engineering mode) can write the
downstream FSID flag directly, the cryptographic layer is bypassed for that feature.
This is the same pattern as PCM 3.1: the security infrastructure exists, but there is a
developer/GEM path that sets the activated state without the crypto check.

### SFscDetails Structure (the "feature table")

The runtime feature record — the MIB2 equivalent of the PCM 3.1 PagSWAct.csv:

```
@dsi.swap.SFscDetails = { @swid=i @state=i @version=iS @vin=s @date=s }
```

| Field | Type | Meaning |
|-------|------|---------|
| swid | int | Software/feature ID |
| state | int | Activation state (enabled/disabled/expired) |
| version | int+string | FEC version |
| vin | string | Vehicle VIN |
| date | string | Activation date |

This table is populated at runtime from FEC containers, not stored as a CSV in firmware.
That is why no test-VIN CSV exists in the MIB2 image (unlike PCM 3.1).

### Empty FEC Config

`asi.fec.fecconfig.ems_table.json` = `{}` (empty). The FEC config table has no locked
entries in this firmware build.

### GEM Engineering Screens Present

The navigation engineering screen (ESD format, identical to PCM 3.1):
```
button
  value  per 2000  0x01  "navigation_hmi::navdebug"
  label  "navigation_hmi::navdebug"
button
  value  per 2000  0x01  "navigation_hmi::all"
  label  "navigation_hmi::all"
```

`per 2000` = persistence partition 2000. These ESD screens write persistence values
directly — the same mechanism that could set FSID flags.

## Revised Attack Vector Priority

1. **GEM FSID flag toggle** — set `/navigation/FSID_Navi_Enabled` (or its persistence
   equivalent in partition 2000) via engineering mode. Per-app, bypasses FEC crypto.
   This is the most promising and simplest path.
2. **Engineering Mode DSI flag** — `@updateIsEngineeringMode:@isEngineeringMode=true`.
3. **SWDL skip flags** — modify swdlclient.cfg for custom firmware flashing.
4. **ExceptionList MD5 forge** — populate SupportedFSC, forge MD5 signature.
5. **FEC state machine bypass** — Ghidra analysis of include/ignore fsid logic.

## Binaries Extracted (Session 3)

- `fec_fsid_binary.elf` — navigation startup controller with FSID GEM toggle logic

## Open Questions

- What persistence partition/key does `/navigation/FSID_Navi_Enabled` map to?
- Can GEM be entered on a retail PCM 4 without authentication? (PCM 3.1 needed RSA-64
  activation for GEM; PCM 4 GEM entry mechanism unknown.)
- Are non-nav features (CarPlay, SiriusXM, etc.) also gated by simple FSID flags, or
  only navigation?
- Does writing the FSID flag persist across the FEC re-validation that runs on VIN change?

## Session 4 Findings: The GEM Engineering Script Library (THE ROADMAP)

### Embedded GEM Scripts Confirmed in app.img

Region 0x16D90000 - 0x16E60000 of app.img contains the complete GEM (engineering menu)
script library: **568 .sh script references and 215 ESD menu labels**. These are the
exact same `engdefs` concept as PCM 3.1, living at `/eso/hmi/engdefs/scripts/`.

### Navigation Toggle Scripts (full source recovered)

ENABLE (naviAppEnable.sh):
```sh
#!/bin/sh
# enable navigation application
#remount rw
/eso/hmi/engdefs/scripts/navpre.sh
#create file
touch /navigation/FSID_Navi_Enabled
rm /navigation/FSID_Navi_Disabled 2>/dev/null
sync
echo "please restart target to take effect"
```

DISABLE (naviAppDisable.sh): touch FSID_Navi_Disabled, rm FSID_Navi_Enabled
RESTORE (naviAppRestoreDefault.sh): rm both flags (reverts to FEC-controlled state)

**This is a file-flag toggle. No crypto. The restore script removing both flags reverts
to FEC control, which proves the flag OVERRIDES the FEC decision when present.**

### Feature Activation Scripts (the high-value targets)

The script library contains direct feature activation scripts:

| Script | Feature |
|--------|---------|
| naviAppEnable.sh / naviAppDisable.sh / naviAppRestoreDefault.sh | Navigation |
| activate_CarPlay.sh / deactivate_CarPlay.sh | Apple CarPlay |
| activate_AndroidAuto.sh / deactivate_AndroidAuto.sh | Android Auto |
| activate_MirrorLink.sh / deactivate_MirrorLink.sh | MirrorLink |
| activate_Baidu_Carlife_Android.sh / _IOS.sh | Baidu CarLife |
| activate_online_features.sh / _au_row.sh | Online Services |
| activate_mobile_online_services.sh | Mobile Online |
| activate_picture_nav.sh | Picture Navigation |
| activateVZO.sh / deactivateVZO.sh | VZO (traffic) |
| activateVZOPlus5.sh / deactivateVZOPlus5.sh | VZO Plus |
| enableVZOLGI.sh / disableVZOLGI.sh | VZO LGI |
| nav_activate.sh / nav_deactivate.sh (SCALE) | Nav (SCALE variant) |
| phone_activate.sh / phone_deactivate.sh (SCALE) | Telephone |
| clustermap_activate.sh / clustermap_deactivate.sh | Cluster Map |
| BT_activate.sh / MOST_activate.sh / WLAN_activate.sh (SCALE) | Connectivity |
| paytmc_activate.sh / paytmc_SIRIUS_activate.sh / paytmc_nar_activate.sh | Pay TMC / SiriusXM traffic |
| activate_messaging_MAP.sh | Messaging |
| activate_second_Phone.sh / activate_TwoTelSupport.sh | Dual phone |
| activate_radio_stationlogo_DB.sh | Station logos |

### FEC Control Scripts (DIRECT FEC MANIPULATION)

These scripts directly manipulate the FEC system - the actual cryptographic layer:

| Script | Effect |
|--------|--------|
| **fec_off.sh** | Turn FEC enforcement OFF |
| **fec_on.sh** | Turn FEC enforcement ON |
| **fecSig_on.sh** | FEC signature checking on |
| **disablesigcheck.sh** | DISABLE SIGNATURE CHECK |
| **enablesigcheck.sh** | Enable signature check |
| **enable_cache_fecs.sh / disable_cache_fecs.sh** | FEC cache control |

**`fec_off.sh` and `disablesigcheck.sh` are the smoking guns.** If these scripts disable
FEC enforcement / signature verification globally, every feature unlocks. These are
factory GEM scripts shipped in the firmware.

### Coding / VIN Scripts

| Script | Effect |
|--------|--------|
| **ols-activateUseFakeVin.sh / ols-deactivateUseFakeVin.sh** | Fake VIN for online services |
| activateNCFSCoding.sh / deactivateNCFSCoding.sh | NCFS coding |
| activateDevelMode.sh / activateReleaseMode.sh | Development vs Release mode |
| EBDevelMode.sh | EB (Elektrobit nav) dev mode |
| country_China.sh / country_EU.sh / country_NAR.sh / country_ROW_*.sh | Country/region coding |
| BentleyMulsanne_Car_Codierung.sh / BentleySUV_Car_Codierung.sh | Car coding (Bentley) |
| ols-showLicenses.sh / ols-showServices.sh | Show licenses/services |

### ESD Engineering Menu Structure (215 labels)

Top-level ESD menu sections (the GEM menu tree):
ALL, Addressbook, Audiomanagement, Bluetooth, CAR Services, Combi Cluster,
Diagnostic, Displaymanagement, **GEarth Streetview**, HMI Framework, HMI Graphics,
HMI RemoteHMI, HMI Widgets, Media, Navigation, Onlineservices, Persistence,
Powermanagement, SDS, SWDL, **SWaP**, TMC, Telephone, Tuner, Tuner TV

Note the **SWaP** submenu - direct access to the activation system from the engineering menu.

### Persistence Verbosity Targets (partition mapping clues)

ESD per-app verbosity entries reveal the persistence/app namespace:
adb_hmi, audio_hmi, bluetooth, browser, cluster_hmi, connectivity_hmi,
connectivity_launcher, displaymanager, esosearch, explorer, google, media,
media_hmi, messaging, messaging_hmi, nad, navi, navigation_hmi, networking,
online, onoff_system, organizer, persistence

### VZO/LGI Activation (confirmed at 0x050D59AE)

```
VZO/LGI activated via GEM!
VZO feature not enabled!
m_vzoHandler == NULL
```

VZO is activated via GEM and the binary logs the result. Same pattern as navigation.

## REVISED CONCLUSION

The PCM 4 / MIB2 activation has the **identical philosophy to PCM 3.1**:

1. Full cryptographic infrastructure (FEC/SWaP, 2048-bit RSA, RIPEMD-160) — uncrackable
   by brute force.
2. A complete GEM engineering backdoor that bypasses all of it with simple shell scripts:
   - Per-feature file flags (FSID_Navi_Enabled, etc.)
   - Global FEC disable (fec_off.sh)
   - Global signature check disable (disablesigcheck.sh)

**The crypto was never the lock. The GEM scripts are the key — and they ship in the
firmware.** The only remaining question is GEM entry authentication on retail units.

## CRITICAL NEXT STEPS

1. **Recover full source of the FEC-control scripts**: fec_off.sh, disablesigcheck.sh,
   enable_cache_fecs.sh, activate_CarPlay.sh, activateVZO.sh. Need exact persistence
   writes / file ops each performs.
2. **Determine GEM entry on retail PCM 4**: ESD screen access, key combo, or persistence
   flag. PCM 3.1 used RSA-64 unlock; PCM 4 mechanism TBD.
3. **Map navpre.sh**: the common pre-script all nav toggles call (does the remount rw).
4. **Find where scripts are invoked from**: ESD `sys 1 0x...` calls at 0x16D97000 region.
5. **Confirm whether GEM scripts require root**: they do `remount rw` so they need write
   access to read-only partitions.

## Session 4b: FULL SCRIPT SOURCE RECOVERED — The Two Activation Mechanisms

Recovered complete plaintext source of 452 GEM scripts from app.img region
0x16D90000-0x16E90000. The activation system uses **two distinct mechanisms**:

### Mechanism A: File-Flag Toggles (navigation & nav-feature layer)

Simple touch/rm of flag files under /navigation/ or /mnt/app/navigation/.
The navigation binary checks these files at startup. Examples:

| Script | Action | Flag File |
|--------|--------|-----------|
| naviAppEnable.sh | touch | /navigation/FSID_Navi_Enabled |
| naviAppDisable.sh | touch | /navigation/FSID_Navi_Disabled |
| naviAppRestoreDefault.sh | rm both | (reverts to FEC) |
| enableVZOLGI.sh | touch | /navigation/VZOLGI_ENABLED |
| activateVZO.sh | touch | /mnt/app/navigation/ACTIVATE_VZO |
| enableTMCLoc.sh | rm | /navigation/DISABLE_TMCLOC_ACTIVATION |
| forceExternalGyro.sh | touch | /navigation/FORCE_EXTERNAL_GYRO |
| stylesFromSDCardEnable.sh | touch | /navigation/LoadStylesFromSDCard |

### Mechanism B: dumb_persistence_writer (coding/feature layer)

The binary `/eso/bin/dumb_persistence_writer` writes directly to the persistence
database, bypassing the FEC/SWaP cryptographic layer entirely. This is the
**master key** for most premium features. General form:

```sh
export LD_LIBRARY_PATH=/mnt/app/root/lib-target:/eso/lib:...
export IPL_CONFIG_DIR=/etc/eso/production
/eso/bin/dumb_persistence_writer -P [-L len -O offset] 0 <PARTITION> <VALUE>
```

Confirmed partition/offset writes (partition 3221356628 = 0xC0040114 = the coding block):

| Feature | Script | persistence write |
|---------|--------|-------------------|
| Online features | activate_online_features.sh | -P 0 3221356628 ... |
| Mobile online | activate_mobile_online_services.sh | -P 0 3221356674 01; -P -L 1 -O 28 0 3221356628 80 |
| OTA update | activateOTA.sh | -P -L 1 -O 70 0 3221356628 80 |
| Picture Nav | activate_picture_nav.sh | -P -L 1 -O 15 0 3221356628 .. |
| Station logo DB | (de)activate_radio_stationlogo_DB.sh | -P -O 48 0 3221356628 .. |
| Cluster mode | clusterCoding{LVDS,MMI,MOST,OFF}.sh | -P -f 0 3221356656 {03,04,02,00} |
| SDIS coding check | rdiCheckSDISCoding.sh | reader -O 412 -L 1 28442848 100 |

Partition 3221356656 = 0xC0040130 = cluster config.
There is a matching `/eso/bin/dumb_persistence_reader` to read current values.

### Mechanism C: FEC Signature Bypass (THE GLOBAL KILL SWITCH)

These scripts disable the FEC cryptographic signature checking outright:

**fec_off.sh**:
```sh
/eso/hmi/engdefs/scripts/navpre.sh
rm -fv /navigation/USE_FEC
rm -fv /navigation/USE_FEC_SIG
sync
```

**fec_on.sh**: touch /navigation/USE_FEC
**fecSig_on.sh**: touch /navigation/USE_FEC_SIG

**disablesigcheck.sh** (renames every map DB signature file):
```sh
mount -u /mnt/navdb
mount -u /mnt/app
find /mnt/navdb/database -name content.sig -exec mv {} {}§back \; -print
touch /navigation/NO_FEC_SIG
sync
```

**enablesigcheck.sh** (restores them):
```sh
find /mnt/navdb/database -name content.sig§back ... mv back to content.sig
rm -f /navigation/NO_FEC_SIG
```

So FEC enforcement for navigation is gated by the presence of `/navigation/USE_FEC`
and `/navigation/USE_FEC_SIG` flag files, plus `/navigation/NO_FEC_SIG`. Removing
USE_FEC / USE_FEC_SIG (fec_off.sh) disables FEC. The map signature check is defeated
by moving the .sig files aside (disablesigcheck.sh). **All file operations. No keys.**

### The RCC Coding Channel (VIPCmd)

The SCALE coding scripts (auto_*.sh, *_Car_Codierung.sh) drive feature coding through
the RCC via the `on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc <FEATURE> <0|1>` command.
This is the factory coding interface. Confirmed features settable this way:

VZAPro, Online_POI, Online_POI_Voice, Online_portal__Browser_Dienste,
Online_Navi__Google_Earth, WIFI_Hotspot, MyAUDI, Picture_Navi, Online_Dictation,
Remote_HMI, Gracenote_*, UPnP, Support_second_phone, LTE_Modul,
Support_of_threeway_calling, RVC_Video_Input, Station_Logo_DB_Mode, VZO, ProbeCar_VZO,
LGI, ProbeCar_LGI, Online_Media, Google_GAL, Apple_DIO, Update_Over_The_Air__UOTA,
WLAN_Client_mode, Online_Navi__Google_Earth (= Google Earth / Street View!)

`ee bc` = base coding, `ee vc` = variant/feature coding. Run from RCC QNX shell via `on -f rcc`.

### navpre.sh (the prerequisite)

Almost every script calls /eso/hmi/engdefs/scripts/navpre.sh first. It does the
`mount -uw` remount-read-write of the protected partitions (/mnt/navdb, /mnt/app,
/mnt/system per setMcdRw.sh / MountSDCardWritable.sh). This is why GEM scripts need
write access — they remount RO partitions RW.

### System Reset With Persistence

`performePersReset.sh` / the reset request:
```sh
mount -uw /mnt/system
touch /etc/ooc.allow.reset
echo hmi-sys-reset > /dev/ooc/reset
```

## DEFINITIVE CONCLUSION

The PCM 4 / MIB2 feature activation has **three independent bypass layers**, all
shipped in the factory firmware, all requiring only filesystem write access (root):

1. **File flags** — touch/rm files under /navigation/ (nav, VZO, TMC, styles, etc.)
2. **dumb_persistence_writer** — write coding bits directly to persistence DB,
   bypassing FEC (online services, OTA, picture nav, cluster, station logos)
3. **VIPCmd coding** — RCC factory coding channel for all variant features
   including Google Earth / Street View
4. **FEC kill switch** — fec_off.sh + disablesigcheck.sh disable signature
   verification globally

**The 2048-bit RSA was never the lock.** It validates FEC containers, but the entire
enforcement can be switched off with factory shell scripts that manipulate flag files
and persistence bits. The only barrier on a retail unit is obtaining root / GEM shell
access to RUN these scripts.

## THE ONE REMAINING GATE: Root / GEM Access on Retail PCM 4

Every bypass needs filesystem write + script execution. On PCM 3.1 we achieved this via:
- USB autorun (proc_scriptlauncher) — runs on all units
- Telnet backdoor (port 23 / 2323)
- Engineering menu activation

For PCM 4 we need to find the equivalent. Candidates to investigate:
- The SWDL update mechanism (signed? the swdlclient skip flags from Session 2)
- ESD engineering menu entry (does it run these scripts? the `sys 1 0x` calls)
- A USB autorun equivalent on MMX2 Linux
- The RCC `on -f rcc` remote exec (needs a shell on MMX first)
- Serial/JTAG on the bench unit

This is the same position we were in early with PCM 3.1. The activation is fully
understood and trivially bypassable WITH a shell. Getting the shell is the next project.

## Session 5 Findings: Bypass-Tool Binaries Extracted + Platform Corrected

### PLATFORM CORRECTION (important): MMX2 is QNX, not Linux

Prior sessions labeled MMX2 as "ARM Linux." That is **wrong**. Empirical evidence from app.img + the MMX2 boot images:

- Nearly every meaningful ELF in app.img uses the QNX dynamic linker `/usr/lib/ldqnx.so.2`.
- Version strings in app.img read `qnx-armv7-650sp1-0x06050003` → **QNX Neutrino 6.5.0 SP1, ARMv7-LE**.
- Build path (from libSdisComponentProtection.so) is `.../framework/qnx_arm_mmx_sdk/`.
- Framework tag on the persistence tools: `FRAMEWORK_VERSION=5.51.6.SR1 MIB2MAIN I202 CI70`.

### CPU / SoC identification (confirmed from boot + system images)

| Processor | Chip | Evidence |
|-----------|------|----------|
| **MMX2** (main HMI/nav/MM) | **NVIDIA Tegra 3 (T30)** — ARM Cortex-A9 MPCore (4+1), ARMv7-A; OS QNX 6.5.0 SP1 | `qb_primary.img` = **nVidia Quickboot 17.54**, `tegraid=`, `video=tegrafb`, `tegraprof`; `efs-system.img` `CHIP_VENDOR=NVIDIA`, `devu-iap2ncm-tegra3-ci.so`, `Tegra:HDMI0`; model `DEV_MMX2_PAG_ER_G24_118PROD` (PAG = Porsche AG) |
| **IOC** | **Renesas V850** | `V850app_MLBPO.bin`; "Renesas Technology Corp" string |
| **RCC (HW31)** | TBD (IFS header machine=0x28 ARM; doc's "SH4" unverified) | resolve via ifs-root.ifs decompress |

Note: QNX USB driver `usbumass-omap4430-musbmhdrc` references OMAP4430 — that's the shared Mentor MUSB OTG controller driver, NOT a second main CPU.

### Bypass-tool binaries extracted from app.img

The three "real tools" were searched by NAME first — but the name only matched **GEM script references** (the scripts call `/eso/bin/dumb_persistence_writer ...`), not the binaries (a binary rarely contains its own filename). Re-located by enumerating all **788 ELF32s** in app.img and fingerprinting by internal strings:

| Binary | app.img offset | Size | Status |
|--------|---------------|------|--------|
| `dumb_persistence_writer.elf` | 0x1E2D4C00 | 78,872 B | **EXTRACTED & confirmed** (`NAME=dumb_persistence_writer`, `Requires -P`, `patch length greater than value length`) |
| `dumb_persistence_reader.elf` | 0x1E307400 | 77,264 B | **EXTRACTED & confirmed** (`NAME=dumb_persistence_reader`, `pick-len`) |
| `VIPCmd` | — | — | **NOT in app.img** — only script refs (`on -f rcc /ffs/extbin/apps/bin/VIPCmd`). Lives in RCC `ifs-root.ifs`. Needs task #2 (IFS decompress). |

Both persistence tools are QNX ARM (`ldqnx.so.2`). They are a getopt CLI front-end that connects to a **QNX persistence resource-manager service** via message passing (`persistence.IPersistenceA` / `...AReply`; error `could not connect to persistence:`). Confirmed CLI surface (matches every GEM-script invocation):

- `-P` — patch/write mode (writer); reader is read mode
- `-L <len>` — patch-len (writer) / pick-len (reader)
- `-O <offset>` — byte offset into the value
- `-f` — flag used for cluster writes (`-P -f 0 3221356656 <mode>`)
- positional: `<partition-name> <value>`; `--type int|string` (default int)
- `--version-tag VERSION` — opens partition as VERSION (default `DSI-unversioned`)
- `--name PROCNAME` — overrides default process name

So the writer's "magic" is just a thin client to the persistence service. Whoever can run it (root/GEM shell) can set any coding bit. No crypto involved — consistent with the overall conclusion.

### FEC / ComponentProtection core binaries located (for future Ghidra)

ELFs in app.img containing `FecManager` (QNX ARM): 0x1C554000 (695KB), 0x1CEABC00 (=libSdisComponentProtection, already extracted), 0x1CBCB400 (=media launcher / fec_rsa_binary, already extracted), 0x1D288800, 0x1D8D3800, 0x1DC7F800, 0x1E0E4800, 0x1E27C800. These hold the FEC state machine for the `include/ignore fsid` logic.

### Tooling note
No `strings`/`readelf` on the Win box and Python on PATH is `C:\Python314\python.exe`. ELF enumeration + extraction done in pure Python (mmap scan for `\x7fELF\x01\x01\x01`, parse e_shoff/e_phoff for size). Scripts: `enumerate_elfs.py`, `extract_persistence_pair.py`.

## Session 6 Findings: RCC Remote-Access Vector (qconn / QNET) — THE ACTUAL GATE

Investigated the RCC partition images while pursuing VIPCmd. Two outcomes — one
negative (VIPCmd not shippable) and one major (the root vector is found).

### RCC partition layout (D:\MMI\...\RCC\)
| Image | Size | Format | Notes |
|-------|------|--------|-------|
| ifs-root.ifs | 22.6MB | QNX6 IFS, **LZO** (flags1=0x09, machine=0x28 ARM) | boot OS image; imagefs compressed. `ram_size 0xEA8A10 = startup_size 0x22108 + imagefs_size 0xE86908` (field map confirmed). NOT yet decompressed. |
| efs-system.efs | 25MB | QNX flash FS, **mostly uncompressed** (0xFF-padded) | file contents carvable directly |
| ifs-emergency.ifs | 3.7MB | QNX6 IFS, flags1=0x0d (diff compression, likely UCL) | recovery image; also ships qconn |
| dsp/AUDI_MIB_DSP.bin.bgz | 813KB | gzip | audio DSP |

### VIPCmd is NOT in this firmware package (conclusion)
`VIPCmd` appears as a **readable string nowhere** in the entire firmware tree —
not app.img (only `on -f rcc /ffs/extbin/apps/bin/VIPCmd` script call-sites),
not ifs-root.ifs, not efs-system.efs. The path `/ffs/extbin/...` is an on-unit
**flash partition (/ffs)** that is factory-populated and not shipped in OTA
updates. **Extracting VIPCmd requires a flash/NAND dump from physical bench
hardware**, not these files. (The coding it performs is still fully documented
from the GEM scripts — Session 4b — so this is not blocking.)

### THE ROOT VECTOR: qconn + QNET (this is what the project was stuck on)

efs-system.efs contains a **qconn services table** (at 0x1730903):
```
in.telnetd  /usr/sbin/telnetd  telnetd
/usr/bin/pdebug  pdebug
QCONN_VERSION=1.4.207944  OS=nto  ENDIAN=le
```
**`qconn` 1.4.207944 ships on the RCC**, exposing `pdebug` (process debug/spawn)
and `in.telnetd`. qconn is QNX Neutrino's remote-dev daemon used by the Momentics
IDE — it **spawns and debugs arbitrary processes with NO authentication** and
listens on **TCP 8000** by default. A reachable qconn = remote root-equivalent code
execution. This is the PCM4 analog of the MMI3G+ telnet backdoor, and stronger
(qconn is unauthenticated by design).

**QNET cluster:** every cross-module script uses `on -f rcc <cmd>` / `on -f mmx
<cmd>` and paths `/net/rcc/...`, `/net/mmx/...`. MMX (Tegra3, QNX) and RCC are a
**two-node QNX QNET cluster**. A shell on EITHER node runs commands on BOTH via
`on -f`. So qconn on the RCC ⇒ spawn `on -f mmx /eso/bin/dumb_persistence_writer …`
or run the GEM scripts on the MMX side directly. Network plumbing present:
`io-pkt`, `devnp-mib-rcc.so` (network driver), DHCP (`/net/rcc/mnt/efs-persist/usedhcp`).

### Open questions for qconn vector (next steps)
1. **Is qconn auto-started on a RETAIL unit, or only engineering builds?** The launch
   command lives in the boot init — inside ifs-root.ifs (LZO). Decompress to find the
   rc/init that does `qconn` / `waitfor`, and any guard (engineering-mode check).
2. **What interface is it bound to?** OABR/BroadR-Reach automotive Ethernet, the
   diagnostic Ethernet pins, USB-ethernet, or WiFi? Find io-pkt bringup + ifconfig in
   the boot scripts. (Community MIB2 rooting uses qconn:8000 over the OABR/Ethernet
   diagnostic link — consistent with this.)
3. Confirm telnetd auth (does it read /etc/shadow? a shadow ref exists in ifs-root at
   0xB0113). pdebug needs no auth regardless.

This reframes the project: the activation bypass is fully understood (Sessions 1-5)
and the **root vector is now identified** (qconn/QNET). Remaining work is confirming
qconn's retail autostart + network binding, which needs the ifs-root LZO decompress.

## Session 7 Findings: RCC ifs-root.ifs DECOMPRESSED — full RCC root FS + root vector

### Pure-Python LZO1X decompressor built (works; no libucl/python-lzo needed)

`lzo1x.py` is a faithful port of the Linux kernel `lzo1x_decompress_safe.c`
(classic bitstream v0). The decisive bug in earlier attempts: the **post-literal-run
short match (LZO `state==4`) copies 3 bytes, not 2** — a 1-byte/occurrence shortfall
that silently corrupted everything downstream. With that fixed, decode is byte-exact.

QNX imagefs framing (confirmed): after the uncompressed startup (ends at file
0x22110), the imagefs is a series of **big-endian 2-byte length-prefixed LZO1X
blocks**, each decompressing to 0x10000 (last smaller). 233 blocks →
**15,231,240 bytes = imagefs_size exactly**. Decompressed image saved to
`rcc_ifs-root_imagefs.bin`; 193 files extracted to `rcc_rootfs/`.

Reusable: `lzo1x.py` (decompressor), `ifs_extract.py` (block inflate + QNX dir walk
+ file extraction). Directly applicable to ifs-emergency.ifs and any MIB2 QNX IFS.

### RCC CPU resolved: TI DRA6xx (Jacinto), ARM — NOT SH4

The research doc's "RCC = SH4" was wrong (carried over from PCM 3.1). Evidence from
the decompressed RCC root FS: `/dev/dspipc/dra6xx.0`, `usr/bin/rcc-pcie-init`,
serial `devc-seromap … 0x48020000` (TI OMAP/DRA UART), srv-starter VariantName
`rcc2_C1`, kernel `procnto-j5-instr`. RCC = **TI DRA6xx Jacinto, ARM, QNX 6.5 SP1**.

### THE ROOT VECTOR — fully confirmed from boot config

`etc/inetd.conf` (RCC): **`telnet stream tcp nowait root /usr/sbin/telnetd in.telnetd`
is UNCOMMENTED = enabled** (r-services rsh/rlogin/rexec/tftp all commented out).
`inetd` is listed in `etc/srv-starter.cfg` → **launched at boot**. Network stack
present and started: `bin/io-pkt-v4`, `lib/dll/devnp-mib-rcc.so` (Ethernet driver),
`lib/dll/lsm-qnet.so` (QNET), `usr/sbin/inetd`.

`usr/bin/dhcp_ifconfig.sh` (Harman, Audi MIB) brings up the Ethernet:
```sh
if [ -f /HBpersistence/usedhcp ]; then
  /usr/sbin/dhcp.client -u -T 10 -b -i en0; ...
fi
ifconfig en0 inet 172.16.250.247 netmask 0xffffff00      # default fixed IP
```
So the RCC defaults to **fixed IP 172.16.250.247/24 on en0** (the OABR/diagnostic
automotive Ethernet), DHCP optional.

`proc/boot/.script` (QNX boot init): `setconf CS_DOMAIN mibhigh.net`,
`CS_HOSTNAME rcc`, serial console `devc-seromap -b115200` on /dev/ser1 with
**`login root`** (root serial console).

**Root-access summary for a retail RCC:**
1. **Telnet :23 as root** via inetd (enabled; telnetd binary lives in efs-system /
   provided by qconn's in.telnetd).
2. **qconn :8000** (efs-system, Session 6) — unauthenticated pdebug/telnet, spawns
   processes as root.
3. **Serial console** (115200, /dev/ser1) — `login root`.
4. All reachable at **172.16.250.247** on en0 (or DHCP) over the diagnostic Ethernet.

Via QNET (`on -f mmx …`), an RCC shell drives the MMX side too → run the GEM
activation scripts / dumb_persistence_writer / VIPCmd. **The activation bypass AND
the root vector are now both fully mapped.** Remaining work is hardware: connect to
the diagnostic Ethernet on a bench unit and validate telnet/qconn at 172.16.250.247.

## Session 8 Findings: FEC architecture mapped + SWDL root CVE + CPUs confirmed

### CPUs confirmed (datasheets in hand: D:\MMI\)
- IOC: Renesas V850 ES/Sx3 — `REN_r01uh0248ej0500_v850essj3_MAH_*.pdf`
- MMX2: ARM Cortex-A9 (NVIDIA Tegra 3) — `DDI0388I_cortex_a9_r4p1_trm.pdf` + `Tegra3_publicTRM_*.pdf`
- RCC: TI DRA6xx (Jacinto), ARM — confirmed Session 7 (`/dev/dspipc/dra6xx.0`)

### SWDL root path: CVE-2020-28656 (published, same platform)
VW Polo 2019 "Discover Media" = the same Harman/e.solutions **MIB2** platform.
The updater **parses unsigned parts of the metainfo file**, so a crafted USB/SD
update writes attacker files and **executes them as root** (physically-proximate,
no auth). This is the published form of the Session-2 SWDL findings (skip flags +
`metainfo2.txt` + `finalScript.sh`). It is a SECOND root gate beside the RCC
network vector (telnet/qconn, Session 7). NOTE for this firmware: metainfo has
per-device `*CheckSum` (SHA1) on scripts, but the CVE shows other metainfo
directives are parsed pre-verification — the injection surface to confirm.

### FEC architecture (the actual unlock layer)
From libSdisComponentProtection.so symbol/trace strings (asi::fec namespace):

```
FSC code (Feature enabling Code) on a medium (USB/SD)
   │  importFecs(medium) / importFSCsList (DSI)
   ▼
FecManager  ── RUNS ON THE RCC ──  ("called by FecManager (RCC)...")
   │  checkSingleFsc, checkDataSignature, checkPkgSignature  (RSA-2048 + RIPEMD-160)
   │  validates against VIN / VCRN ; getFscDetails ; getHistory ; exportCCD
   ▼  FEC state PERSISTED in efs-system  (strings: "SWaP..FECHISTORY", hmac-ripemd160)
   │  updateFECs  →  per-FSID state pushed to clients
   ▼
MMX FecAppMMX clients  →  "include fsid [0x%X] fecState [%d]" / "ignore fsid ..."
   ▼
Apps + content.pkg FecChecker ("Check FSIDs ... FSCNeeded/FSCFound") gate features
```

Key facts:
- **The FSC validator (FecManager) and the persistent FEC/SWaP state both live on the
  RCC, inside efs-system.efs** (FecManager strings at 0x175E365/0x177504B; the binary
  is in the QNX flash-FS structure past the cleanly-carvable ELFs — needs an
  efs-system (ETFS/power-safe-FS) parser to extract).
- MMX side only CONSUMES per-FSID states; it does no crypto. So "it's all about the
  FECs" = the RCC FecManager is the real gate, confirming RCC matters for unlocks too.
- content packages (nav map DBs) embed an FSC-ID; `Checker_FecChecker` verifies the
  FSID is activated (format header: "content.pkg STFVERSION 10 MIBH 4 CONTENTVERSION").
- DSI surface: importFSCsList, updateFscList, getHistoryList, getFscDetails.

### Unlock vs bypass (the honest picture)
- **Legit unlock** = a valid FSC (RSA-2048 signed, VIN-bound). Not forgeable (uncrackable).
- **Bypass** (needs root, via SWDL-CVE or RCC telnet/qconn): the factory GEM layer —
  fec_off.sh / disablesigcheck.sh (kill enforcement), dumb_persistence_writer (MMX
  coding bits), VIPCmd ee vc (RCC coding), FSID file flags. Plus a likely RCC-side
  vector: **inject FEC state directly into efs-system** (where FECHISTORY lives).

### Next FEC steps
1. Parse efs-system.efs (QNX ETFS/power-safe-FS) → extract FecManager + the stored
   FECHISTORY/SWaP state; Ghidra the FSC container format + checkSingleFsc validation.
2. Map FSID numbers → feature names (the include/ignore fsid table) for a full unlock list.
3. Confirm the CVE-2020-28656 unsigned-metainfo injection surface on this firmware.

## Session 9 Findings: three threads (ETFS / FSID map / SWDL-CVE)

### Thread 3 — CVE-2020-28656 SWDL root path: CONFIRMED applicable to this firmware
- Update integrity is **SHA1-only** (`MetafileChecksum`, per-device `CheckSum`,
  `FinalScriptChecksum`). SHA1 = integrity, not authenticity (recomputable after edit).
- **No RSA `.sig`/signature files anywhere** in the firmware tree. Payloads are
  `update61852-*.dat` + `metainfo2.txt`.
- `finalScript.sh` (checksummed) does: `ksh ${MEDIUM}/common/tools/0/default/finalScriptSequence.sh`
  — i.e. **executes `finalScriptSequence.sh` from the update medium as root**, and that
  file is NOT in the package and NOT covered by `FinalScriptChecksum`. → drop a malicious
  `finalScriptSequence.sh` on a tampered USB (recompute the SHA1s) = **root exec**. This is
  exactly the CVE. (Retail "Customer SWDL" sets `UserSwdl=true` to skip final script, but
  that flag is in `/HBpersistence/SWDL/update.txt` — controllable.)
- ExceptionList.txt FEC dev-bypass: `[SupportedFSC]` empty, `[Signature]` = **8 MD5 hashes**
  (32-hex). "Exception list for development purpose (MIB-High)." MD5 = broken.

### Thread 2 — FSID→feature map: NOT static in firmware
- `asi.fec.fecconfig.ems_table.json` = `{}` (no locked entries this build).
- FSC = **FreischaltCode** ("FreischaltCode not OK... cannot be parsed").
- DSI passes the table as `@updateFscList:#{ii}i` = array of (fsid:int, state:int) pairs;
  runtime `SFscDetails={swid,state,version,vin,date}`. No static fsid→name table exists.
- ⇒ the real per-unit FSID numbers live in the **efs-system FECHISTORY** (this unit's
  activation state). So Thread 2 converges on Thread 1.

### Thread 1 — FecManager location: efs-system QNX FFS3 (needs an extent parser)
- The validator (FecManager) + persistent FEC state are in `efs-system.efs`, a QNX
  **FFS3 / devf flash** image (driver `devf-generic`; `mount_efs_rw.sh`, `flashmib`).
- Only 12 *contiguous* ELFs are carvable from it (diagnostic utils: qconn, netstat,
  tuner drivers, sort/nice/etc.). The big RCC apps are stored in **fragmented FFS3
  extents**, so FecManager's ELF is not contiguous. The `imp_mib_fecmanager_CFecManager…`
  / `project_asiadapter_presctrl_CASIFecManager` strings at 0x1775xxx are the trace-symbol
  DB, not the binary.
- ifs-root (extracted) holds only early/boot RCC apps (DSIIPCBridge, MMX2RCCEarlyApp,
  NavigationPositioning, …); FecManager is NOT there. ⇒ must parse FFS3 to extract it.
- FEC component classes seen (in the trace DB): CFecManagerDSIFec, CFecManagerDSIPersistency,
  CFecPersistencyDataHelper, CFecLogger, CFecCentralDispatcher, CFecOnOffClient,
  NFecHelper, CASIFecManager/CASIFecClient adapters, `fecDetails`.

### Net: next concrete task
Write a **QNX FFS3 (devf) parser** for efs-system.efs → reassemble fragmented extents →
extract (a) the FecManager binary (Ghidra the FSC container format + checkSingleFsc /
RSA-2048+RIPEMD-160 validation) and (b) the stored FECHISTORY/SWaP blob (real activated
FSID numbers for this unit = the concrete unlock list). Reuse lzo1x.py if any extents are
compressed. This single parser satisfies both Thread 1 and Thread 2.

## Session 10 Findings: QNX EFS parser BUILT — RCC efs-system extracted, FEC keys recovered

### Pure-Python QNX Compressed-EFS (F3S) parser built
`efs_extract.py` + a pure-Python **UCL NRV2B** decompressor (added to it) parse the
QNX F3S/EFS format. Ported from jtang613/qnx_dumpers `efsdump.c` (ref/efsdump.c) but
**adapted for LITTLE-ENDIAN** (efsdump assumes big-endian; our RCC is ARM-LE) and
calibrated against qconn ground truth. Key format facts (LE):
- magic `QSSL_F3S`; boot_info at file 0xC0; 192 units × 0x20000; align_pow2=6.
- dirent: struct_size(2),moves(1),namelen(1),first(extptr),name(4-aligned),stat(20);
  stat.mode 0x4000=dir / 0x8000=file.
- head (32B) grows DOWN from unit_end−32*(i+1); **exttype = (status byte+1)&3**
  (FILE=3,DIR=2,SYS=1); `data_offset = phys*unit_size + (hi*0x10000+lo) << align_pow2`.
- per-file compression: magic `iwlyfmbp`, deflate_filehdr (usize,blksize,cmptype
  0=LZO/1=UCL), then cmphdr-framed blocks (prev,next,pusize,usize); in_len=next−8.
- The UCL decompressor is validated (decoded a 336KB text file correctly).

Extracted /mnt/efs-system → `rcc_efs/` : 158 files, 23 dirs. efs-system is the RCC's
**static config/keys/backup** partition (NOT the main apps): backup/, bin/ (qconn +
diag utils), etc/ (config, TLAM coding, version), opt/audio, scripts.

### FEC VALIDATION KEY MATERIAL recovered (the core of "it's all about the FECs")
`backup/Keys/` holds three RSA-2048 public-key chains, **per OEM** (AU=Audi, BY=Bentley,
PO=**Porsche**, SE=Seat, SK=Skoda, VW + generic MIB-High), each 288 bytes
(256-byte modulus + 32-byte signature wrapper; the pubkey itself is signed):
- **FECKey/** — verifies FSC (FreischaltCode) activation codes  → `PO_MIB-High_FEC_public_signed.bin`
- **DataKey/** — verifies content/data (map DB) signatures        → `PO_MIB-High_DK_public_signed.bin`
- **MetainfoKey/** — verifies the SWDL **metainfo** signature      → `PO_MIB-High_MI_public_signed.bin`

These are PUBLIC keys (can't derive the private halves → FSCs not forgeable, as
expected for RSA-2048). They confirm the validation key set and the trust roots.

### Refines CVE-2020-28656
The presence of MetainfoKey means the metainfo IS meant to be RSA-signed. The CVE
works because parsed items OUTSIDE that signature (e.g. `finalScriptSequence.sh`
pulled from the update medium by finalScript.sh) are executed as root. So: signature
covers the metainfo body, but not the medium-supplied sequence script → root.

### Other recovered artifacts
- `backup/FEC/ExceptionList.txt` (the dev FEC bypass; 8 MD5 sigs, empty SupportedFSC).
- `etc/TLAM/{POG24,POG11,BYG24}/TLAM_GF_*.txt` — per-platform coding tables (Porsche G24).
- one UCL-compressed 336KB text file (decompressed cleanly by the new parser).

### FecManager binary + FECHISTORY status
- FecManager validator BINARY is NOT in efs-system (static) nor ifs-root (boot apps);
  the FecManager-referencing ELFs are in MMX app.img (Session 5: 0x1C554000 etc.).
  `binaries/mmx_FecManager.elf` carved (695KB) but it references FecManager without
  checkSingleFsc/RIPEMD — the actual validator (checkSingleFsc + RSA/RIPEMD) is in
  libSdisComponentProtection.so / a crypto lib; precise ID is the next Ghidra step.
- **FECHISTORY** (per-unit activated FSIDs) lives in **efs-persist** (runtime,
  per-vehicle) — NOT in this firmware image. Getting a real unlock list needs an
  efs-persist dump from bench hardware.

### Tools
- efs_extract.py (QNX EFS/F3S parser + UCL NRV2B + LZO, LE), ref/efsdump.c (C reference).

## Session 11 Findings: FEC key DECODED (1024-bit, e=3!) + crypto/Ghidra targets

### FEC/Data/Metainfo key blob format (all 21 keys, decoded)
288-byte `*_public_signed.bin` = `[ n: 128B ][ e: 32B ][ sig: 128B ]`:
- **n** = 1024-bit RSA modulus (per-OEM, odd, top bit set — valid).
- **e** = 3 (32-byte big-endian field = ...0003; IDENTICAL across all 21 keys).
- **sig** = 1024-bit signature over (n||e) by a VAG ROOT key (makes the blob "signed").

So the entire activation trust chain (FSC, content/data, SWDL metainfo) is
**RSA-1024 with e=3** — NOT 2048-bit. (The 2048-bit keys seen earlier in app.img are
a different/unused set.) Porsche modulus saved: `binaries/PO_FEC_modulus.hex`.

### Two attack surfaces this opens
1. **RSA-1024** — weaker than 2048 (deprecated), though still not DIY-factorable.
2. **e=3 → Bleichenbacher signature forgery** — if any verifier doesn't STRICTLY check
   the full PKCS#1 v1.5 padding (the `00 01 FF..FF 00` run length + DigestInfo), an
   e=3 signature can be FORGED with no private key. That would forge FSCs / signed
   updates with NO root needed — the strongest potential break found so far.

### Where the crypto actually is (Ghidra targets)
- `libSdisComponentProtection.so` = **DSI proxy only** (forwards checkSingleFsc/importFSCs
  to FecManager; "unable to forward call to peer"). No crypto here. Notable flags it
  exposes: **`updateAreFSCsSigned`** (toggle: are FSCs required to be signed?) and
  **`updateIllegalFSCs`** — a signature-enforcement off switch worth tracing.
- **`skip_checksum_binary.elf`** = the **custom RSA** (`cryptolib/rsa.c`): `calcSignature`
  (s^e mod n; "Illegal argument: (modulus/publicExponent/signature) != NULL"),
  `restoreSignature`, `verify_Sha1`. Hashing = **SHA1** (SWDL metainfo/data path).
  Contains the **SHA1 DigestInfo prefix constant at file 0xCAFF0** → it builds a real
  PKCS#1 block. THE Ghidra question: find the xref to 0xCAFF0 and the verify function
  (anchors: strings "Could not decrypt signature" @0xCAED0, "Signature verification
  error" @0xCAEEC, calcSignature @0xCAAD4). Check whether it memcmp's the WHOLE 128-byte
  block (safe) or only the tail / lax FF-run (⇒ e=3 forgery).
- **FecManager** (RCC, NOT yet extracted) = the FSC verify proper, uses **RIPEMD-160**
  (no RIPEMD OID in either extracted binary, confirming it's elsewhere). Needs FecManager
  binary to analyze the FSC-container Bleichenbacher surface.

### Ghidra navigation (skip_checksum_binary.elf, ARM LE, Cortex-A9):
1. Find data xref to 0xCAFF0 (SHA1 DigestInfo) → the expected-block builder.
2. Find string xrefs to "Could not decrypt signature" / "Signature verification error".
3. In that verify fn: confirm e=3 (publicExponent==3), and whether the post-`s^e mod n`
   comparison validates the full padding or just locates the hash (the forgeability test).

## Session 12 Findings: Headless Ghidra + the crypto verdict (FEC = OpenSSL, SAFE)

### Ghidra headless rig (works, reusable)
analyzeHeadless (Ghidra 11.3.2) + JDK21 at D:\CP\tools\. Gotchas solved: (1) project
DIR must pre-exist, (2) don't reuse a Tee'd log file held by a prior task, (3) Jython
scripts need `# -*- coding: utf-8 -*-` if any non-ASCII, (4) use `-process ... -noanalysis`
to re-run scripts without re-importing. Scripts: ghidra_scripts/FindVerify.py,
FindFscVerify.py. Decompiles saved in ghidra_out/.

### Two RSA paths, clearly separated
1. **Tegra boot-config (BCT) signing** = `skip_checksum_binary.elf` `cryptolib/rsa.c`:
   FUN_001ad750 builds a textbook PKCS#1 v1.5 block (00 01, 90×FF, 00, 15B SHA1
   DigestInfo @0x1caff0, 20B SHA1) and FUN_001b5268 = a 1024-bit square-and-multiply
   modexp. This is NVIDIA Tegra secure-boot (NvWriteBct / "PT signature generated"),
   NOT activation. (Custom RSA — but boot chain, out of scope for unlocks.)
2. **FEC/FSC/metainfo/data verify** = **OpenSSL libcrypto.so.2** (ELF @0x02FF2000):
   RSA_verify ×8, EVP_VerifyFinal ×2, **RSA_padding_check_PKCS1_type_1 ×32** (strict
   sig padding), RIPEMD160, d2i_RSA_PUBKEY, BN_mod_exp. The 2 RSA_public_decrypt are
   internal to RSA_verify. FecManager (CFecManager @0x1C554000, app.img) calls into this.
   `libSdisComponentProtection.so` is a DSI proxy/logger only (checkSingleFsc/getPublicKey
   = log stubs that forward to FecManager; zero crypto).

### VERDICT (crypto chapter closed)
FEC/FSC verification = OpenSSL RSA_verify with strict PKCS#1 v1.5 padding check.
**e=3 Bleichenbacher forgery does NOT apply** — FSCs cannot be forged. (1024-bit e=3 is
weak in theory but the implementation is the safe OpenSSL one.) The crypto is the one
hard wall. The unlock path remains the **GEM/root bypass** (factory coding scripts), with
the **ExceptionList MD5 whitelist** as the only crypto-adjacent soft spot (MD5, not RSA).

## Session 13 Findings: CVE-2020-28656 SD-card vector CONFIRMED on Porsche MHI2

Pulled the original disclosure (Context IS, "A code signing bypass for the VW Polo",
via Wayback → ref/vwpolo_blog.txt) and mapped it to this firmware.

### The bug (from disclosure)
In the metainfo parser (`libMetainfoParser.so` on MIB2-STD/Delphi; different name on
MHI2/Harman). `parse_metainfo_file()` parses the WHOLE file, but the **MetafileChecksum
integrity hash covers only two byte ranges**: [start → "MetafileChecksum" line] and
[line after it → "[Signature]" line]. The RSA signature is over that SHA1 checksum.
⇒ **Anything appended AFTER the [Signature] section is parsed-and-acted-on but NOT
signed.** Append a new `[…\File]` section (Source/Destination) → an attacker file is
copied onto the unit without breaking the signature → overwrite a root-run script → root.

### Confirmed identical on this Porsche firmware
- `metainfo2.txt`: `[common]`(l.7) → `MetafileChecksum`(l.30) → … → **`[Signature]`(l.6539)
  is the LAST section** with `signature1..8` (8 hex pairs = 128-byte = RSA-1024 sig).
  The file ends right after `signature8` → appended content lands unsigned. [CONFIRMED]
- Verifier ELF carved: `binaries/metainfo_verify.elf` (app.img @0x04823800, 9.8MB).
  Strings: `'signature1' found`, **`Count of hex chars should be 128`**, `[Signature] not
  found`. [CONFIRMED]
- Ghidra `FUN_0020ab04` = the signature-block assembler: splits by '\n', finds the
  signature lines, hex-pair→byte (FUN_00690104) into a 0x80 buffer, requires exactly
  128 bytes. **Matches the disclosure's described logic exactly.** [CONFIRMED]
- Residual [NEEDS BENCH]: locate MHI2's exact MetafileChecksum-range function to prove
  the two-range exclusion byte-for-byte (the "MetafileChecksum" key isn't a literal in
  the binary — matched via substring search). Everything else is identical, so this is
  very high confidence.

### Exploit recipe (SD-card "toolbox")
1. Take any legitimately-signed Porsche/MHI2 update (or this firmware's metainfo2.txt +
   its signed data files).
2. **Append** a new section AFTER `signature8`:
   `[X\X\0\default\File]` with `Source="../path/to/evil_file_on_card"`,
   `Destination="<a privileged root-run script path>"`, plus its `CheckSum`/`CheckSumSize`
   (the appended section's own checksums are self-consistent; it's outside the signed range).
3. Put `evil_file` on the card. The parser copies it over the target script; the original
   signed content still validates → update accepted.
4. On apply, the overwritten script runs as **root** → it runs the GEM activation commands
   (§ playbook). No crypto break, no pre-existing shell, no FS rewrite.
- Target script: a privileged one executed during/after update (scriptPre/scriptPost or
  finalScriptSequence). [NEEDS BENCH to pick the live target + confirm customer-mode flow]

This is THE consumer delivery vector: a signed update + appended unsigned section =
root, from an SD card, no teardown. Written into handoff/UNLOCK_PLAYBOOK.md §3.

## Session 14 Findings: firmware-side exhausted (coding map, UPD container, SWDL linchpin)

Goal: extract everything possible without a bench unit.

### Complete per-feature coding map → `docs/CODING_MAP.md`
Parsed all factory GEM scripts: **32** `VIPCmd ee vc` variant-coding features, **13**
`dumb_persistence_writer` coding-bit writes (partition 0xC0040114 offsets + 0xC0040130
cluster modes), **22** file-flag toggles. This is the consolidated "what to write to
unlock X" reference.

### SWDL package/container format
The Porsche/MHI2 SD update is **metainfo2.txt + `update61852-*.dat`** containers with a
custom magic **`UPD\x00`** (`55 50 44 00`) — **not** the 7-zip used on the Polo/MIB2-STD.
metainfo `[…\File]` sections reference payloads by `FileName`/`Source`/`Destination`.

### SWDL apply/script linchpin — mechanism confirmed in code, final proof = bench
Ghidra of `skip_checksum_binary.elf` (the SWDL client):
- `FUN_00127634` handles `scriptPre`/`scriptPost`: reads script path + `scriptPreChecksum`,
  SHA1-verifies ("Script file SHA1 checks out"), then runs it. Script *content* is integrity-
  checked, and those checksums sit in the **signed** metainfo region → you can't swap a
  script's bytes; you overwrite the on-disk file via an appended `[…\File]` copy instead.
- `FUN_0016bee4` does file application — `open64(...,O_RDWR|O_CREAT)` + `memcpy` (the
  Source→Destination copy). Consistent with applying parsed `[File]` entries.
- **Not determinable from static decompilation (dense, string-heavy):** whether *customer*
  mode applies `[File]` sections appended **after** `[Signature]`, and whether the dropped
  file lands on a path executed as **root** during the customer-update flow. This is the one
  load-bearing step the Context researchers also proved only on hardware. ⇒ **bench item.**

### Net: firmware-only analysis is complete
Everything derivable from the firmware is done. Remaining unknowns are **hardware-gated**
(insert SD + observe root exec; live telnet/qconn; online-VIN behavior) or require **other
firmware versions** for a vulnerable-range comparison.

## Files Saved
- feature_scripts.txt — full plaintext of ~90 feature/FEC GEM scripts
- engdefs_dump.txt — index of all 568 script names + 215 ESD labels
- binaries/dumb_persistence_writer.elf, binaries/dumb_persistence_reader.elf — Session 5
- binaries/rcc_qconn.elf — qconn 1.4.207944 (RCC), the root-vector daemon — Session 6
- rcc_ifs-root_imagefs.bin — decompressed 15.2MB RCC QNX imagefs — Session 7
- rcc_rootfs/ — 193 extracted RCC root-filesystem files (inetd.conf, .script, etc.) — Session 7
- tools: lzo1x.py (LZO1X decompressor), ifs_extract.py (QNX IFS inflate+extract),
  enumerate_elfs.py, extract_persistence_pair.py, carve_rcc_bins.py
