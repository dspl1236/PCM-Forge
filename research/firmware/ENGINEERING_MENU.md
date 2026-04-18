# PCM 3.1 Engineering Menu — Complete Map

> Reverse-engineered from `PCM3Root` (6.6MB SH4 ELF, June 2015 build)
> Firmware: `Porsche_PCM3.1_MOPF_SOP_STEP9.6_15245AS9`
> Requires ENGINEERING activation code (SW 0x010b) in PagSWAct.002

## Overview

The Engineering menu is a full built-in PIWIS replacement inside the PCM head unit.
It's controlled by `CGEngineeringFSM` with states `EngineeringTop_0`, `EngineeringOn_11`, `EngineeringOff_10`.
Three worker threads handle background operations (`SystemEngineeringWorkerThread1-3`).

---

## Menu Structure

### 1. SW Activation
Enter 16-digit hex activation codes via on-screen keyboard.
Same codes as PagSWAct.002 — no USB needed if you know the code.

- `requestSetActivationCodeEngineeringMode` — enter code for a feature
- `requestSetRestCyclesEngineeringMode` — set how many boot cycles engineering stays active
- VIN selection (⚠️ demo VINs from PagSWAct.csv are listed — don't change!)

**Available activation SW IDs:**
| SW ID | Feature |
|-------|---------|
| 0x010b | ENGINEERING |
| 0x010a | BTH (Bluetooth) |
| 0x0106 | KOMP (Component Protection) |
| 0x0101 | Navigation |
| 0x0109 | UMS (USB Media) |
| 0x0103 | FB (Feature Base / Boot Image) |
| 0x0104 | SSS (Voice Control) |
| 0x0105 | SC (Sport Chrono) |
| 0x0107 | TVINF (Video in Motion) |
| 0x0108 | SDARS (Satellite Radio) |
| 0x010c | INDMEM (Individual Memory) |
| 0x010d | HDTuner |
| 0x010e | FeatureLevel (model variant) |
| 0x010f | HDTuner (alt) |
| 0x0110 | DABTuner |
| 0x0111 | OnlineServices |
| 0x2001-0x200b | Navigation databases (11 regions) |

### 2. Variant Coding
Configure vehicle hardware identity.

- `requestSetVariantCoding(VehicleType, RoofType, SteeringPos, ModelType)`
- VehicleType: determines Cayenne/911/Boxster/Panamera behavior
- RoofType: Cabrio detection (Boxster identification)
- SteeringPos: LHD/RHD
- ModelType: affects boot screen and feature availability

### 3. Factory Reset / Vehicle Handover
- `requestFactorySettings` — reset PCM to factory defaults (PV_ACTIVE or PV_ALL)
- `requestSetToFactoryDefaults` — full factory reset
- `requestVehicleHandover` / `requestVehicleHandoverDefaults` — customer delivery mode
- `requestPrepareForCustomerHandover` — dealer pre-delivery setup
- `CustomerServiceBit` — service counter (0x%04X CDC1)

### 4. ECU Reset
- `requestReset` — full PCM reboot
- `requestSetCopyAddressbookOnECUReset` — preserve address book during reset
- `setECUResetInProgress(true)` — signals reset to all components
- Copies `addressbookSql.db` during reset

### 5. HDD Engineering
Background worker: `HarddiskEngineeringWorkerThread`

- `requestHDDSize(blocksize)` — raw block size
- `requestHDDSize(capacity)` — total capacity (partition 1-5)
- `requestHDDSize(freespace)` — free space per partition
- HDD temperature monitoring (threshold: -27°C for read-only mode)
- HDD SMART data (`HBProdSMARTData`)

### 6. Sound Diagnosis
Speaker and amplifier testing.

- `Sound_Diagnosis_LoudspeakerTestMode` — individual speaker test
- `Sound_Diagnosis_setLoudspeakerTestBalance` — balance adjustment test
- `Sound_Diagnosis_setLoudspeakerTestFader` — fader adjustment test
- `Sound_Diagnosis_setSMSVolumeLevel` — SMS notification volume
- `Sound_Diagnosis_setSenderStoreVolume` — station store volume
- `Sound_Diagnosis_setVolumeLimitStartStop` — volume limiter test
- `Sound_Diagnosis_verifyDTCPKey` — DTCP content protection verify
- Audio amp types: ASK, BOSE, BURMESTER (auto-detected from `audioAmpBOSE` file)

### 7. Antenna Diagnostics
AM/FM/DAB signal testing with diversity antenna.

- `userStartAntennaDiagnostics(duration, configDCScenarios)` — start test
- `userAbortAntennaDiagnostics()` — cancel test
- ADIV (Antenna Diversity) self-test
- Reports: field strength, antenna state, diversity mode, tuner frequency
- `requestSetAntennaOutput` — select antenna output

### 8. CAN Engineering
Live CAN bus data viewer.

- `EngineeringCANPresCtrl.SPHEngineeringCAN` — CAN data display
- `CAN Decoder Block` — register for specific CAN message IDs
- CAN IPC channel for real-time monitoring
- Vehicle data: speed, steering angle, acceleration, temperature

### 9. MOST Network Diagnostics
Fiber optic network (Media Oriented Systems Transport).

- `CHBMOSTDiagnostics` — full MOST ring diagnostics
- Ring break detection and reporting
- Device enumeration and status
- Configuration status reporting
- `requestStoreDefaultRegistry` — save default MOST config
- `requestResetRegistryConflict` — resolve device conflicts
- `requestResetErrorCounters` — clear error counts
- Net on/off event monitoring

### 10. Video Management
Display and video testing.

- `requestStartVideoSelftest` — video self-test
- `SELFTEST_TV` — TV tuner test sequence
- `SELFTEST_RVC` — rear view camera test
- DisplayMode control (21 modes available)
- `requestSetSplitScreenDisplayMode` — split-screen configuration
- DTCP (Digital Transmission Content Protection) debug
- `requestVideoInActivityDetection` — VIM source detection

### 11. Version Info
Complete software/hardware version reporting.

- All module versions (PCM3Root, PCM3Reload, NavCore, etc.)
- DSP version info
- HDD firmware, serial, model
- IFS type (IFS_G1_E2)
- MOST device versions
- SIS-IDs
- `sendVersionResponse()` — comprehensive version list

### 12. Component Status
Hardware module presence and state.

- `requestSetInternalComponentPresent`:
  - headunit
  - navigation
  - phone (NAD module)
  - DVDChanger
  - SDS (Speech Dialog System)
  - digitalradio (DAB)
  - iPod
- Diagnosis state per component (OK/Error/Busy)

### 13. Diagnosis Self-Tests
Individual component testing.

| Test | What it tests |
|------|--------------|
| ADIV-Selftest | Antenna diversity |
| Mic-Selftest | Microphone |
| Video-Selftest | Display/video chain |
| BTPhoneReceiver | Bluetooth phone |
| Bluetooth | BT module |
| DVD | DVD drive |
| NADPhone | NAD telephone module |
| SDARS | Satellite radio |
| SysInfo-SWActivation | Activation system |

### 14. Trace / Debug Logging
Development trace system.

- `TraceGuard` — trace profile management
- Active trace profiles stored in `/HBpersistence/TraceProfiles/`
- Known profiles: `SportChronoTraces.hbtc`
- `CHBTraceHelper_storePersistent` / `_loadPersistent` / `_killPersistent`
- GAU (Generic Application Unit) log trace
- Slog reader integration
- Per-scope trace filtering

### 15. Network Configuration
Ethernet/IP setup for development access.

- `checkDBGModeFile` — reads `/HBpersistence/DBGModeActive`
- When DBGModeActive exists: `qconn` starts (QNX remote debug agent)
- `inetd` service (telnet, ftp)
- Default ping target: `192.168.0.231`
- PCM IP: `192.168.0.90` (when network active)
- `ifconfig` — network interface configuration

### 16. Boot Screens
Custom startup splash screens.

- Factory screens: `/mnt/share/bootscreens/` (40+ .bin files)
- Custom screen: `/HBpersistence/CustomBootscreen_%03u.bin`
- Screen selection tied to FeatureLevel activation
- `rm -f /HBpersistence/CustomBootscreen_*` — remove custom screens
- Copies from HDD to flash on selection change

### 17. Screensaver
- Empty directory found at `/HBpersistence/` (needs files populated)
- Display mode states available (1-21)

### 18. TouchScreen
- `requestSetTouchDisabled` — enable/disable touch input
- `requestTouchScreenActionAvailable` — check touch status
- `CheckTouchscreenCalibration` — calibration check
- Calibration data: `/HBpersistence/TouchCalib.bin`

---

## Processes Running (from diagnostic log)

| PID | Process | Description |
|-----|---------|-------------|
| 1 | procnto | QNX microkernel |
| 24607 | PCM3Root | Main HMI application (51 threads) |
| 73737 | PCM3Reload | Hot-reload companion (119 threads) |
| 73767 | NavCore | Navigation engine |
| 172084 | qconn | QNX remote debug agent |
| 172085 | proc_scriptlauncher | USB/SD script autorun |
| 188471 | inetd | Network services (telnet) |
| 229436 | PSSBSSProcess | PSS/BSS persistence |
| 282687 | SSSProcess | Speech system |
| 135211 | vdev-medialaunch | Media launcher (USB detect) |
| 36869 | vdev-flexgps | GPS receiver |
| 36898 | io-audio | Audio subsystem |

---

## Debug Tools on HDD (`/mnt/data/tools/`)

| Tool | Size | Purpose |
|------|------|---------|
| taco | 5.3MB | Full diagnostic trace tool |
| persdump2 | 278KB | Persistence data dumper |
| mmecli | 232KB | MME command-line interface |
| showmetadata | 613KB | Media metadata viewer |
| fdisk | 119KB | Partition management |
| vi | 122KB | Text editor |
| find | 79KB | File search |
| ping | 39KB | Network diagnostic |
| sqlite_console | 60KB | SQLite database tool |
| chkqnx6fs | 44KB | QNX filesystem checker |
| mkqnx6fs | 99KB | QNX filesystem creator |
| mmexplore | 85KB | MME explorer |
| qdbc | 45KB | QDB client |
| dinit | 19KB | Device init |
| ipgrabber | 21KB | IP grabber |
| hbhogs | 202KB | Resource hog monitor |

---

## TODO — Needs Car Verification

- [ ] Screenshot all Engineering menu screens
- [ ] Document exact menu tree navigation path
- [ ] List all activation entries shown in SW Activation screen
- [ ] Check if screensaver accepts image files and what format
- [ ] Test network access via telnet 192.168.0.90 (DBGModeActive is set)
- [ ] Explore boot screen selection menu
- [ ] Document CAN Engineering data display fields
- [ ] Test Sound Diagnosis speaker test sequence
