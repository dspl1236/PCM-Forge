# IOC Probe Results — On-Car Test May 7, 2026
## Vehicle: 2016 Porsche Cayenne 958 S E-Hybrid (WP1AE2A28GLA64179)
## Firmware: PCM3.1 MOPF SOP STEP9.6 (15245AS9), QNX 6.3.2, built June 2015

---

## IOC Channels (12 confirmed)

| Channel | Permissions | Type |
|---------|-------------|------|
| ch2-ch10 | nrw-rw-rw- | Named, world read-write (9 channels) |
| debug | nr--r--r-- | Named, read-only |
| onoff | nr--r--r-- | Named, read-only |
| watchdog | nr--r--r-- | Named, read-only |

All data channels (ch2-ch10) block on raw read — CHBIpcProtocol
client registration via devctl() required before data flows.

## Display Stack — Exclusivity CONFIRMED

- `/dev/layermanager` EXISTS (Theory 2 confirmed, not timing)
- `lmgrHMIConnect` fails — PCM3Root holds exclusive HMI lock
- No `/dev/gf*` devices — all graphics via layermanager only
- Carmine GPU (VID 0x10CF, DID 0x202B)
- Display 0: 800×480 @ 60Hz, ARGB1555 (main screen)
- Display 1: 240×257 @ 60Hz, ARGB1555 (instrument cluster insert)
- 128MB VRAM, DMA channel 10

## Image Codec Support

PNG, BMP, GIF, JPG — all natively supported via img.conf

## Boot Screen Storage

- 78 factory screens on HDD (`/mnt/share/bootscreens/`)
- Sizes: 13,092 bytes (smallest, #086) to 64,200 bytes (largest, #099/crest)
- Active: `CustomBootscreen_067.bin` (35,394 bytes) = Cayenne S E-Hybrid
- `/HBpersistence/` free space: 21,150 blocks (~10MB)
- Slot 100: CLEAR — no conflicts
- IFS fallback: `PCM31_bootScreenPorscheLogo.jpg` (64,200 bytes)

## Persistence Model (differs from Audi!)

Porsche PCM uses **CVALUE flat files**, NOT QDB DataPST.db.
Filenames are hex namespace addresses: `CVALUE{address}.CVA`

### CVALUE Files Captured (13)

| File | Size | Notes |
|------|------|-------|
| CVALUE0002021b.CVA | 9 | Factory Dec 2013 |
| CVALUE00020226.CVA | 12 | Written Jan 2007 |
| CVALUE0002032d.CVA | 12 | Written Jan 1970 (epoch) |
| CVALUE000203b3.CVA | 172 | Factory Dec 2013 |
| CVALUE0002064d.CVA | 13 | Factory Dec 2013 |
| CVALUE00020685.CVA | 170 | Written Jan 1970 |
| CVALUE00020686.CVA | 4,114 | Written Mar 2016 (largest) |
| CVALUE00020687.CVA | 488 | Written Jan 1970 |
| CVALUE0002068c.CVA | 12 | Factory Dec 2013 |
| CVALUE0002068d.CVA | 12 | Factory Dec 2013 |
| CVALUE0002068e.CVA | 10 | Written Feb 2016 |
| CVALUE0002068f.CVA | 5,755 | Written Feb 2016 |
| CVALUE010b0006.CVA | 12 | 0x010b = ENGINEERING namespace |

### persdump2 Syntax (PCM version)

```
Usage: persdump2 <PersFile> [v][s]
```

Takes a CVALUE file path, NOT `type address` like the Audi version.

## Key Persistence Files for Service Reset

### /HBpersistence/NormalPersistencyFiles/

| File | Size | Updated | Notes |
|------|------|---------|-------|
| generalPersistencyData_CombiPresCtrl | 162 | Jan 1970 | **CLUSTER INTERFACE** |
| generalPersistencyData_DiagnosisPresCtrl | 174 | Apr 2022 | Diagnosis |
| generalPersistencyData_PSportChronoPresCtrl | 189 | Apr 2018 | Sport Chrono |
| generalPersistencyData_PTripPresCtrl | 164 | May 2019 | **TRIP COMPUTER** |
| generalPersistencyData_PLogBookPresCtrl | 171 | Apr 2022 | Logbook |
| generalPersistencyData_FSCSysCtrl | 159 | Apr 2019 | Feature activation |

### /HBpersistence/EarlyPersistencyFiles/

| File | Size | Updated | Notes |
|------|------|---------|-------|
| generalPersistencyData_GlobalSettingsPresCtrl | 176 | Apr 2018 | Units, language |
| generalPersistencyData_OnOffPresCtrl | 160 | Apr 2026 | Power state |
| generalPersistencyData_SwdlPresCtrl | 483 | May 2026 | SWDL state (today!) |

### Other Key Files

| File | Size | Notes |
|------|------|-------|
| hybrid.bin | 159 | Updated today — live hybrid data |
| vin | 17 | VIN string |
| PagSWAct.002 | 420 | Activation codes |
| ndr_probe.core | 544,768 | Core dump from NDR probe crashes |
| SCP.dbf | 7,168 | Security Control Protocol database |

## Running Processes (key ones)

| PID | Process | Notes |
|-----|---------|-------|
| 24607 | PCM3Root | Main application |
| 4106 | dev-ipc | IOC resource manager (-c 9 channels) |
| 4108 | layermanager | Display (exclusive lock) |
| 147495 | qdb | QNX database engine |
| 147498 | dev-i2c-hbfpga | I2C/EEPROM access |
| 196661 | qconn | Remote GDB available |
| 176178 | proc_scriptlauncher | USB script handler |
| 16414 | servicebroker | DSI service broker |
| 16408 | ndr | Navigation data router |
