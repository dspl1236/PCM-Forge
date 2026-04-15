# PCM 3.1 USB Engineering Access

## Overview

The PCM 3.1 has a well-established USB-based activation mechanism that
bypasses the need for PIWIS (Porsche's dealer diagnostic tool). Multiple
vendors sell VIN-specific activation files that are loaded from a USB stick.

This is the PCM 3.1's equivalent of the MMI3G's SD card `copie_scr.sh`
mechanism — the entry point for custom code execution.

## How It Works

1. A VIN-specific activation file is generated
2. File is copied to a USB memory stick (4GB-32GB, FAT32)
3. USB stick is inserted into the PCM's USB port
4. PCM detects the activation file and processes it automatically
5. Activation completes in 30-60 seconds
6. PCM reboots with the new feature enabled

## Features Activatable via USB (No PIWIS Required)

All of these have been confirmed working by multiple vendors and users:

| Feature | Description |
|---------|-------------|
| Engineering Menu | Full service/debug menu access |
| Navigation | Enable nav on non-nav units or re-activate |
| Map Update Activation | Accept new map DVD data |
| Bluetooth | Enable BT audio/phone |
| Sport Chrono | Enable Sport Chrono display in PCM |
| DAB / Satellite Radio | Enable digital radio |
| USB/AUX | Enable USB and auxiliary input |
| Video in Motion (TV Free) | Remove speed lockout on video |
| Cruise Control | Enable cruise control display |
| Multi-function Steering Wheel | Enable MFSW controls |
| Heated Steering Wheel | Enable heated wheel controls |
| Voice Control | Enable speech recognition |
| On-board Computer | Enable trip computer features |
| Custom Boot Image | Change startup splash screen |
| Online Service | Enable Porsche online features |
| Logbook | Enable digital logbook |

## Vendors Selling USB Activations

- euronavmaps.com — Engineering menu, all activations (~$30-80 each)
- code-porsche.com — Enabling codes ($100 each, needs PIWIS)
- autosvs.com — Enabling codes (PIWIS required for most)
- MHH Auto forum — Community-sourced activations
- Various sellers on Rennlist forums

## VIN-Specific Code Generation

The activation files are VIN-specific. The PCM validates the VIN before
accepting activation commands. This means:

1. The PCM has a VIN stored internally
2. The activation file contains a cryptographic hash or code derived from the VIN
3. The PCM verifies the code matches its stored VIN before applying

This is similar to the MMI3G's FSC (Freischaltcode) system used for
navigation activation. The algorithm is known to the vendors who sell
these activations.

## PagSWAct.csv — Software Activation Table

Found in the firmware update ISO at:
`PCM31RDW100/HEADUNIT/FIL/HBpersistence/PagSWAct.csv`

This file likely contains the master table of activatable features,
their current status (enabled/disabled), and the activation codes.
This is the PCM's equivalent of the MMI3G's FSC activation system.

## Engineering Menu — What's Inside

Once activated, the engineering menu provides access to (based on Rennlist reports):

- **SWActivation** — Software feature activation codes
  - NavDB switching (USA/Europe/etc.)
  - UnlockCode entry fields
  - Feature enable/disable toggles
- **System Information** — Detailed hardware/software version info
- **Configuration** — System settings not available in normal mode
- **Debug/Diagnostics** — Potentially log files, test modes

## USB Stick File Structure (To Be Determined)

The exact file structure on the USB stick that triggers activation
is not yet documented in this project. Key questions:

1. What files/folders must be present on the USB stick?
2. What format is the activation file? (Binary? Text? XML?)
3. How is the VIN encoded into the activation data?
4. Is there a signature/checksum validation?
5. Can we create our own activation files?

## Relation to the Firmware Update Mechanism

The firmware update ISO (`PCM_NA_20150721.ISO`) shows that the PCM
uses a well-defined update structure:

```
pcm_update.disc          — Disc type identifier ("This is a PCM3.x update disc.")
HBUPDATE.def             — Master update definition with checksums
PCM31RDW100/HEADUNIT/    — Regional variant (RDW = Rest of World)
  IOC_D1/9600_UPD.bin    — V850 IOC firmware
  ADR01C0000/PCM3_IFS1.ifs  — QNX IFS image 1
  ADR0FC0000/PCM3_IFS2.ifs  — QNX IFS image 2
  FIL/HBpersistence/     — Persistence configs
  SCR/                   — Update scripts
```

The USB activation likely uses a simpler version of this structure —
possibly just a single activation file rather than the full firmware
update package.

## Next Steps

1. **Buy an engineering menu USB activation** — ~$30 from euronavmaps
   to see what file they provide and reverse engineer the format
2. **Activate engineering menu on Andrew's Cayenne** — Gain access
   to the service menu for further exploration
3. **Document the engineering menu screens** — Screenshot every option
4. **Analyze the activation file** — Determine format and VIN encoding
5. **Check for script execution** — Can the engineering menu run
   custom scripts like the MMI3G's GEM?
6. **Look for QNX shell access** — The `debugTools.sh` in the firmware
   references `/mnt/data/tools/` with chmod 777 — this directory
   might be writable and executable from USB

## The /mnt/data/tools/ Discovery

From `debugTools.sh` in the firmware:
```bash
chmod 777 /mnt/data/tools/*
```

This line makes everything in `/mnt/data/tools/` executable. If this
directory is accessible from USB (e.g., if the USB mounts at `/mnt/data/`
or similar), we could potentially place custom scripts there and have
them auto-execute. This needs verification on the actual car.

## Comparison with MMI3G Entry Point

| Aspect | MMI3G | PCM 3.1 |
|--------|-------|---------|
| Media | SD card (SDHC) | USB stick (FAT32) |
| Trigger file | copie_scr.sh | TBD (activation file) |
| Auto-execute | Yes (proc_scriptlauncher) | Yes (30-60s processing) |
| VIN check | No | Yes (VIN-specific codes) |
| Engineering menu | CAR+BACK (5s hold) | USB activation required |
| Cost to unlock | Free (DrGER2 method) | ~$30 (vendor) or DIY |
| Script execution | Shell scripts via GEM | TBD |
