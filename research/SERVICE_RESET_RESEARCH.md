# Service Reset Research — Oil / Inspection / Intermediate

> Consolidated from OIL_SERVICE_RESET_ANALYSIS.md, SIA_SERVICE_RESET_DISCOVERY.md,
> SERVICE_RESET_PATH_FORWARD.md, and SERVICE_LOG_DESIGN.md.

## Status

**Partially working via OBD-II (Mongoose Pro J2534).** Three of four service counters reset successfully. Oil change counter remains — working through gateway routing.

Internal reset from the PCM (no OBD) is not yet achieved. CDEF command injection is the remaining internal path.

## What We Found via OBD-II

### Module Discovery (Cayenne 958)
Porsche uses CAN ID offset 0x6A (not +8 standard ISO-TP). Scanned 0x700–0x73F:

| Module | TX | RX | Part Number | Role |
|--------|-----|-----|-------------|------|
| 0x10 | 0x0710 | 0x077A | J533 Gateway | Gateway |
| 0x29 | 0x0729 | 0x0793 | 7P5919204H | PCM head unit |
| 0x0A–0x23 | various | various | — | Other modules |

### UDS Routine IDs (Module 0x29)

| Routine | Response | Resets |
|---------|----------|--------|
| 0x0203 | 71010203 OK | Service 1/3 (major) |
| 0x0400 | 71010400 OK | Service 2/3 distance (intermediate) |
| 0x0402 | 71010402 OK | Service 2/3 time (intermediate) |
| 0x0404 | 71010404 OK | Oil change — accepted but counter didn't clear |

Session: Extended diagnostic (0x10 0x03) required. No security access needed.

### What Didn't Work
- VCDS cannot communicate with the Cayenne cluster
- Module 0x29 accepts oil reset but may not be the cluster (7P5919204H = infotainment display, not instrument cluster 7P5920xxx)
- The actual cluster (module 0x17) does not respond on the diagnostic bus via standard addressing
- WriteDataByIdentifier (0x2E) for service DIDs returns NRC 0x33 (security access denied)

## SIA System Architecture (from binary analysis)

### Dual-Path Reset (Audi MMI3GApplication)

```
User presses reset in Car → Servicing → Service intervals
  ↓
requestInspectionReset → DSI event queue
  ↓
SPHCarKombi::RQST_InspectionReset
  ↓                              ↓
CCarKombiCDEFHandler          CCarKombiBAPHandler
  ↓ CAN via V850 IOC            ↓ MOST fiber optic
Instrument Cluster            Instrument Cluster
```

- **CDEF path:** Used on PCM 3.1 (CAN-connected cluster). Handler: `CCarKombiCDEFHandler.sendInspectionReset()`
- **BAP path:** Used on Audi MMI3G+ (MOST-connected cluster). Handler: `BAP - sendInspectionReset`

### SIA Data Fields

| Field | Description |
|-------|-------------|
| OilDistance | Distance until oil service (km) |
| OilTime | Time until oil service (days) |
| OilReset | Oil service reset flag |
| InspectionDistance | Distance until inspection |
| InspectionTime | Time until inspection |
| ServiceDistance | Distance until next service |
| ServiceTime | Time until next service |

DSI update IDs: `UPD_ID_SIAOilInspection`, `UPD_ID_SIAServiceData`, `UPD_ID_SIACapabilities`

### CDEF Command Map (CCarKombiCDEFHandler)

All commands sent to instrument cluster (LSG 0x11):
sendInspectionReset, sendSetClockTime, sendSetClockDate, sendSetBCDisplayData, sendResetBCDisplayData, sendSetLanguage, sendSetDistanceUnit, sendSetTemperatureUnit, sendSetConsumptionUnit, sendSetPressureUnit, sendSetVolumeUnit, sendSetClockFormat, sendSetDateFormat, sendIntLightValues, sendSetWarningVelocityData, sendSetShiftUpIndication.

### BAP Protocol (for CAN transport)

CAN IDs: 0x490 (PCM → Cluster), 0x491 (Cluster → PCM)

BAP header (2 bytes):
```
Byte 0: [LSG_ID:6][FKT_ID_high:2]
Byte 1: [FKT_ID_low:4][OP_CODE:4]
```

LSG 0x11 = Cluster, FKT 0x03 = SIA, OpCode 0x01 = SET

### Live IPC Capture (A6 during reset)

Captured 40,954 bytes on ch5 during oil service reset. All 100 SIA messages were OpCode 2 (STATUS) — the SET command travels via MOST on the A6, not through IPC. Status byte transition confirmed: 06 → 05 (transitional) → 08 (acknowledged) → 06 (settled).

## Paths Still Open

### 1. PIWIS via Mongoose Pro J2534
PIWIS VM exists at `D:\Virtual Machines\piwis\`. Mongoose Pro ISO2 is a standard J2534 PassThru device. PIWIS knows the correct cluster addressing and gateway routing. Needs USB passthrough to VM.

### 2. CDEF Command Injection (internal, no OBD)
Write the InspectionReset CDEF frame directly to the IOC CAN channel from inside the PCM. Requires knowing the exact CDEF frame format (LSG, FID, payload). Ghidra analysis of `sendInspectionReset` in PCM3Root is deeply layered through virtual dispatch — exact bytes not yet extracted.

### 3. Direct CAN via Mongoose Pro
Bypass the gateway entirely. Need to find the cluster's CAN ID on the correct bus. The Mongoose Pro only reaches the drivetrain CAN via OBD pins 6+14. The cluster may be on the comfort or infotainment CAN bus (not accessible via OBD without a breakout harness).

## Service Log Design (future)

Glovebox USB concept: insert USB, get a timestamped service log with mileage, written to `service_log.txt`.

Mileage sources (priority order):
1. `LogBookSql.db` (if electronic logbook active)
2. `hmetercounter.bin` (raw mileage counter)
3. `CVALUE00020687` (trip counters)
4. `CombiPresCtrl` (cluster presentation controller)
5. BAP `CURRENT_MILEAGE_FKT` (future, requires BAP channel)

## Files Analyzed

- `MMI3GApplication` (10.7MB SH4 LE, Audi K0821/K0942)
- `PCM3Root` (6.6MB SH4 LE, Porsche PCMS02XX1221)
- `NavigationNdrInfo` (563KB SH4, Porsche)
- `dev-ipc` (74,979B, QNX resource manager)
- Live IPC captures from A6 root shell (ch2, ch4, ch5)
- Live UDS probing via Mongoose Pro J2534 on Cayenne 958
