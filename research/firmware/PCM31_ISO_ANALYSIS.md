# PCM 3.1 ISO Extract — Firmware Analysis

## Overview

Three firmware variants analyzed from the PCM 3.1 update DVD:

| Variant | Size | Date | IFS1 Variants | Notes |
|---------|------|------|:---:|-------|
| PCM31RDW100 | 507MB | Apr 2014 | 2 | Original release, early hardware |
| PCM31RDW400 | 594MB | Jun 2015 | 7 | Latest, includes Macan + MOPF |
| PCM31LOW400 | 133MB | Jun 2015 | 7 | Low-spec variant |

## Architecture — Identical to Audi MMI3G

| Component | Audi MMI3G | Porsche PCM 3.1 |
|-----------|:---:|:---:|
| OS | QNX 6.5.0 | QNX 6.3.2 |
| CPU | SH4 (SH7785) | SH4 (SH7785) |
| IFS magic | eb7eff00 | eb7eff00 |
| Boot | srv-starter-QNX | srv-starter-QNX v4.2.22 |
| Main app | MMI3GApplication (27MB) | PCM3Root (6.6MB) |
| SD script | copie_scr.sh (XOR) | copie_scr.sh (XOR) ✅ |
| IOC | V850 (V850app.bin) | V850 (9600/9608/9612_UPD.bin) |
| FPGA | 9600_D_FPGA.hbbin | 9600_D_FPGA.hbbin |
| Persistence | /HBpersistence/ | /HBpersistence/ |
| Process count | 101 | 67 |
| Activation | FSC codes | PagSWAct RSA codes |

## copie_scr.sh — CONFIRMED IDENTICAL

`proc_scriptlauncher` (15.9KB SH4 ELF) has German debug strings:

```
"Beginne mit decodieren"           → "Starting to decode"
"In Funktion script_decoder"       → "In function script_decoder"
"/HBpersistence/copie_scr.sh"     → Decoded output path
"/copie_scr.sh"                    → Source on SD/USB
"open_medialauncher_SD()"          → SD card handler
"open_medialauncher_USB()"         → USB handler
"/bin/ksh"                         → Execution shell
```

Built by L. Koslowski (USER=lkoslowski), 2008-01-11.
Same XOR PRNG cipher as Audi. Our MMI3G-Toolkit encoder works directly.

## IFS1 Variants (PCM31RDW400)

| Variant | Size | Target |
|---------|------|--------|
| PCM3_IFS1.ifs | 9.3MB | Standard (G1/E2) |
| PCM3_IFS1_9x1.ifs | 9.5MB | Panamera/997 |
| PCM3_IFS1_MOPF.ifs | 9.3MB | Model Year facelift |
| PCM3_IFS1_MOPF_9x1.ifs | 9.5MB | MOPF Panamera |
| PCM3_IFS1_Macan.ifs | 8.7MB | Macan |
| PCM3_IFS1_MOPF_Macan.ifs | 8.7MB | MOPF Macan |
| PCM3_Emergency.ifs | 3.8MB | Emergency recovery |

## PCM3Root — Main Application (52 PresCtrl Classes)

```
AhaPresCtrl              CPOnOffPresCtrl          NavPresCtrl
AuxInPresCtrl            CPSoundPresCtrl          OnOffPresCtrl
BrowserPresCtrl          CPSysInfoPresCtrl        PSportChronoPresCtrl
CBluetoothPresCtrl       CPTunerPresCtrl          PTripPresCtrl
CCommunicationPresCtrl   CPTVTunerPresCtrl        SoundPresCtrl
CDiagnosisPresCtrl       CPVideoManagementPresCtrl SpeechPresCtrl
CHBHMISettingsPresCtrl   CsiPresCtrl              SwdlPresCtrl
CPAuxInPresCtrl          CombiPresCtrl            SysInfoPresCtrl
CPBackFacilitiesPresCtrl DiagnosisPresCtrl        TmcPresCtrl
CPGlobalSettingsPresCtrl EngineeringCANPresCtrl   TunerPresCtrl
CPKeyInputPresCtrl       GlobalSettingsPresCtrl   VideoManagementPresCtrl
                         ...and more
```

## Software Activation System

```
SysInfoPresCtrl.SPHSysInfoSWActivation     → Activation handler
CSPHSysInfoSWActivationResponseEvent       → Response event
/HBpersistence/PagSWAct.002                → Activation code file
ACTIVATION_REQUIRED                         → Status flag
navigation_allowed                          → Nav activation check
checkForInactivation                        → Inactivation check
FeatureLevel                               → Feature level code
```

The RSA activation codes from PCM-Forge's `generate_codes.py` target
this system. The PagSWAct.csv test vectors from the firmware confirm
our algorithm is correct.

## Custom Boot Screen Support

```
/HBpersistence/CustomBootscreen_%03u.bin   → Custom boot images
/mnt/share/bootscreens                     → Boot screen storage
"No unlock code for FeatureLevel present, set empty PathToBootscreen"
```

FeatureLevel activation code controls which boot screen is shown.

## Engineering Access

`EngineeringCANPresCtrl` — Engineering CAN controller exists in
the firmware. The engineering menu is accessed via a key combo on
the PCM touchscreen (documented in Rennlist forums):

1. Go to first home screen
2. Press top-right "V" icon area
3. Touch positions 1 and 2 simultaneously
4. Wait for screen to go black (reboots into engineering mode)

## IOC Firmware Variants

| File | Size | Platform |
|------|------|----------|
| 9600_UPD.bin | 716KB | G1 (997/Panamera) |
| 9608_UPD.bin | 720KB | E2 (Cayenne 958) |
| 9612_UPD.bin | 720KB | 9x1 (newer Panamera) |

IOC version strings: `FR_GET_HW_VERSION`, `FR_GET_SW_VERSION`

## Debug Tools (shipped on HDD)

The firmware ships with 30+ debug tools in `/mnt/data/tools/`:

```
chkqnx6fs    fdisk         hogs          mmecli        ping
df           find          ipgrabber     mmexplore     sqlite_console
dinit        flashinfo     mkqnx6fs      persdump2     taco
du           fpgaInfo      NavigationNdrInfo  rootblk_shle  vi
```

Also: `IPGrab-PCM3Root.sh`, `IPGrab-PCM3Reload.sh`, `debugTools_mm.sh`

## HDD Partitions

From `parkHDD.sh`: 5 partitions (hd0t77 through hd0t81)

## Version Info (PCM31RDW400)

```
System_CD:       Porsche_PCM3.1_MOPF_SOP_STEP9.6_15245AS9
HMIController:   15245AS9
OfficialBuild:   OEKAP3NT_cbuild_PCM3__Fri_2015.06.12__14.32.59
QNX_Version:     RL_qnx_os_632_PSP3_11505A
IFS-Type:        IFS_G1_E2
```

## Implications for PCM-Forge

1. **copie_scr.sh works** — same encoder, same execution path
2. **RSA activation verified** — PagSWAct system confirmed in binary
3. **Engineering mode** exists — EngineeringCANPresCtrl present
4. **Custom boot screens** — writable from persistence
5. **Same IFS tools** — inflate_ifs.py + extract_qnx_ifs.py work
6. **Debug tools accessible** — persdump2, mmecli already on HDD
7. **Diagnosis controller** exists — CDiagnosisPresCtrl

## Feature Name Mapping — PCM-Forge ↔ Firmware

The firmware uses different names than the PagSWAct.csv headers:

| PCM-Forge Name | SWID | Firmware Name | Index |
|----------------|:---:|---------------|:---:|
| ENGINEERING | 0x010b | EngineeringMode | 10 |
| BTH | 0x010a | BT_HPF | 9 |
| KOMP | 0x0106 | Compass | 5 |
| Navigation | 0x0101 | Navigation | 0 |
| UMS | 0x0109 | UMS | 8 |
| FB | 0x0103 | DriversLog | 2 |
| SSS | 0x0104 | SSS | 3 |
| SC | 0x0105 | SportChrono | 4 |
| TVINF | 0x0107 | TVTuner | 6 |
| SDARS | 0x0108 | SDARS | 7 |
| INDMEM | 0x010d | IndividualMem | 20 |
| FeatureLevel | 0x010e | FeatureLevel | 26 |
| HDTuner | 0x010f | HDTuner | 24 |
| DABTuner | 0x0110 | DABTuner | 25 |
| OnlineServices | 0x0111 | OnlineServices | 27 |
| NavDBEurope | 0x2001 | DB_Europe | 11 |
| NavDBNorthAmerica | 0x2002 | DB_NorthAmerica | 12 |
| NavDBSouthAfrica | 0x2003 | DB_SouthAfrica | 13 |
| NavDBMiddleEast | 0x2004 | DB_MiddleEast | 14 |
| NavDBAustralia | 0x2005 | DB_Australia | 15 |
| NavDBAsiaPacific | 0x2006 | DB_Asia | 16 |
| NavDBRussia | 0x2007 | DB_Russia | 17 |
| NavDBSouthAmerica | 0x2008 | DB_LatinAmerica | 18 |
| NavDBChina | 0x2009 | DB_China | 23 |
| NavDBChile | 0x200a | DB_Chile | 28 |
| NavDBArgentina | 0x200b | DB_Argentina | 29 |

**Firmware-only features (no activation code needed?):**
- Offroad (index 1) — offroad navigation
- Speller (index 19) — text input speller
- Telephone (index 21) — phone module
- HandSet (index 22) — Porsche phone handset accessory

## PCM 3.1 Activation Code Flow

```
1. PCM reads /HBpersistence/PagSWAct.002 on boot
2. SysInfoPresCtrl processes activation codes
3. For each feature: "Got activationCode SWID %#x"
4. Unlock code verified: "Got UnlockCode %s"
5. If FeatureLevel missing: "No unlock code for FeatureLevel present"
6. Navigation check: "navigation_allowed" flag set
7. Boot screen selected based on FeatureLevel
```

The activation codes from PCM-Forge's `generate_codes.py` write to
this exact file format. The RSA-1024 algorithm we reversed produces
codes that the firmware accepts.
