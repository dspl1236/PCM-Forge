# PCM 3.1 System Information — Andrew's Cayenne 958

## System Info Screen (INFO + SOURCE)

| Field | Value |
|-------|-------|
| System Version | V4.76 |
| Platform | PCM3.1 |
| Serial Number | BE9632G5671071 |
| XM Radio | Active (Ch 52 BPM) |

## Current System Details

| Component | ID | Status |
|-----------|-----|--------|
| HWID_PCM3 | PCME02XX1221 | — |
| SWID_PCM31APP | PCM31APP0115245A | VALID |
| SWID_PCM31EMR | PCM31EMR0113155E | VALID |

## Hardware ID Decoded

- `PCME` = PCM variant E (matches PCME01XX firmware in update ISO)
- `02` = Hardware revision 2
- `XX` = Wildcard/generic
- `1221` = Board revision

## Software ID Decoded

- `PCM31APP0115245A` = PCM 3.1 Application, version 01-15245A
  - ISO has PCM31APP0114183A (older)
  - Car has newer firmware than the update disc!

- `PCM31EMR0113155E` = PCM 3.1 Emergency/Recovery, version 01-13155E

## IOC Firmware from Update ISO

Multiple IOC variants for different hardware revisions:

| Directory | File | Size | For HW Rev |
|-----------|------|------|------------|
| IOC_B1 | (TBD) | — | Early hardware |
| IOC_B3 | (TBD) | — | Rev B3 |
| IOC_C0 | (TBD) | — | Rev C0 |
| IOC_D1 | 9600_UPD.bin | 703 KB | Rev D1 |
| IOC_E2_B3 | (TBD) | — | E2 variant B3 |
| IOC_E2_C0 | (TBD) | — | E2 variant C0 |
| IOC_E2_D1 | 9608_UPD.bin | 703 KB | E2 variant D1 |
| IOC_9x1_B3 | (TBD) | — | 9x1 (911/Boxster) B3 |
| IOC_9x1_C0 | (TBD) | — | 9x1 (911/Boxster) C0 |
| IOC_9x1_D1 | (TBD) | — | 9x1 (911/Boxster) D1 |

## IOC Firmware String Analysis

Key strings found in 9600_UPD.bin:

```
9600_App                          — App identifier
Copyright (c) 1993-1997 CMX-RTX   — CMX RTOS on the V850!
Gateway                            — CAN gateway function
CfIpc                              — IPC (Inter-Processor Communication)
CfMost                             — MOST bus interface
CfPowerM                           — Power management
Diag                               — Diagnostic handler
AMFMTuner                          — FM/AM tuner control
TunerMost                          — Tuner via MOST bus
TunerProcess                       — Tuner processing
MOST_MO / MOST_ST                  — MOST bus states
cfDiagMost                         — Diagnostics over MOST

WUR_DIAGNOSIS_SESSION              — Wake-Up Reason: Diag session
WUR_DOOR                           — Wake-Up Reason: Door open
WUR_DWA_INACTIVE                   — Wake-Up Reason: Alarm inactive
WUR_ECU_RESET                      — Wake-Up Reason: ECU reset
WUR_HU_ON_REQ                      — Wake-Up Reason: Head Unit on
WUR_IGNITION                       — Wake-Up Reason: Ignition
WUR_ON_BUTTON                      — Wake-Up Reason: Button press
WUR_PRODUCTIONMODE                 — Production mode
WUR_START_IN_FLASHMODE             — Flash mode boot

FR_GET_HW_VERSION                  — Framework: Get HW version
FR_GET_SW_VERSION                  — Framework: Get SW version
FR_GET_STATUS                      — Framework: Get status
FR_GETTEMP                         — Framework: Get temperature
FR_GETLSENS                        — Framework: Get light sensor
FR_GETPWM1                         — Framework: Get PWM channel
FR_SET_IOC_INFO                    — Framework: Set IOC info

Version %x.%02x.%02x              — Version format string
E2PVer A:%05d C:%05d              — EEPROM version

TskHandlHigh / TskHandlLow        — Task handlers (RTOS tasks)
Jul 08 2009                        — Compile date
```

## Key Differences from MMI3G V850app.bin

| Aspect | MMI3G V850app.bin | PCM 9600_UPD.bin |
|--------|-------------------|-------------------|
| Size | 589,760 bytes | 720,334 bytes |
| RTOS | Custom/bare-metal | CMX-RTX RTOS |
| Bus names | Antrieb, Dashboard, etc. | Not found (different naming) |
| MOST support | No | Yes (AMFMTuner, TunerMost) |
| Compile date | Unknown | Jul 08 2009 |
| Gateway string | cfappgateway | Gateway |
| IPC | HPIPC references | CfIpc |
| Diagnostics | PERS subsystem | Diag, cfDiagMost |

## Notable Findings

1. **CMX-RTX RTOS** — The PCM's V850 uses a commercial RTOS (CMX-RTX by
   CMX Company), unlike the MMI3G which appears to use a custom scheduler.
   This means the V850 has proper task management, priorities, and scheduling.

2. **MOST bus integration** — The PCM's IOC handles the MOST (Media Oriented
   Systems Transport) fiber optic bus for audio, which the MMI3G doesn't have
   in its V850. This is used for Bose/Burmester amplifier communication.

3. **Wake-Up Reasons (WUR)** — The IOC manages vehicle wake-up, including
   a diagnostic session wake (WUR_DIAGNOSIS_SESSION) which means the PCM
   can be woken up by a PIWIS diagnostic request.

4. **Flash mode** — WUR_START_IN_FLASHMODE confirms the IOC can boot into
   a flash/update mode, which is how the firmware gets updated.

5. **Production mode** — WUR_PRODUCTIONMODE suggests a factory/test mode
   exists, potentially useful for debugging.
