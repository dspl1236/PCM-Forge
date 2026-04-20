# PCM 3.1 Oil Service Reset — Complete Firmware Analysis

## Date: April 20, 2026

## Executive Summary

**The Porsche PCM 3.1 firmware does NOT contain oil service/inspection reset code.**

The Audi MMI3G+ (same hardware platform) has a full CarKombi service interface with
`InspectionReset` and SIA (Service Interval Anzeige) functions. Porsche compiled their
variant WITHOUT this functionality — it is not hidden or disabled, the code simply
does not exist in the binary. Flipping per3 toggles will not help.

**Oil service reset on the Cayenne 958 requires an external diagnostic tool
communicating directly with the instrument cluster (module 0x17) via OBD-II.**

---

## Firmware Comparison

### Audi MMI3G+ (K0942, MU9411) — MMI3GApplication (11MB)

**228 CarKombi references** including full service interval support:

#### InspectionReset Functions (11 hits)
```
SPHCarKombi::RQST_InspectionReset
SPHCarKombiExt::RQST_InspectionReset
requestInspectionReset
request_InspectionReset
sendInspectionReset
BAP - sendInspectionReset
CDEF - sendInspectionReset
UPD_ID_requestInspectionReset
printInspectionReset
```

#### SIA (Service Interval Anzeige) System
```
SPHCarKombi::ATST_SIACapabilities      — cluster capabilities
SPHCarKombi::ATST_SIAOilInspection     — oil inspection data
SPHCarKombi::ATST_SIAServiceData       — service interval data
SPHCarKombiExt::ATST_SIAOilInspection  — extended oil data
SPHCarKombiExt::ATST_SIAServiceData    — extended service data
SPHCarKombiExt::ATST_SIAViewOptions    — display options

[Car][SIA] OilDistance %d              — km until oil change
[Car][SIA] OilTime %d                  — days until oil change
[Car][SIA] InspectionDistance %d        — km until inspection
[Car][SIA] InspectionTime %d           — days until inspection
processStatusSIAReset                  — reset confirmation
processStatusSIAOilDistanceTime        — oil distance/time parser
processStatusSIAInspectionDistanceTime — inspection parser
```

#### CarKombi Architecture
```
CCarKombiPresCtrl         — main presentation controller
CCarKombiBAPHandler       — BAP protocol (older clusters)
CCarKombiCDEFHandler      — CDEF protocol (newer clusters)
CarKombiExtPresCtrl       — extended controller (in all modules)
SPHCarKombi v4.4          — service proxy (BAP)
SPHCarKombiExt v19.0      — service proxy (CDEF)
```

#### Per3 Toggles Read by Code
```
DEVICE_LIST_SERVICE_INTERVALL, value %d         — per3 0x0010001F
PROTOCOLL_SWITCH_SERVICE_INTERVALL_CHOISE       — per3 0x0014004E
```

### Porsche PCM 3.1 (E2, RDW400) — PCM3Root (6.6MB)

**0 CarKombi references.** Zero InspectionReset. Zero SIA.

The Porsche has a simpler `CombiPresCtrl` that only handles:
- Cluster display content (navigation map, station names)
- Button inputs from cluster (COMBI_UP/DOWN/ENTER/ESCAPE)
- Settings persistence (CCombiSettingsSettings)
- Sport Chrono stopwatch data (SPORTCHRONO_STOPWATCH_KOMBI13/14/15)

The Porsche DOES have:
- `RESETBC_ENCODER_BLOCK_ID` — but this is for trip computer reset only
- `RESET_TRIPDATA_CONTINUOUS` / `RESET_TRIPDATA_SINCE` — trip data
- `VEHICLE1_ENGINE_RPM/TEMP/SPEED` etc. — CAN data decoding
- `CombiPresCtrl.SGCANConnectionClient` — CAN connection to cluster
- `per3 0x0010001F` exists in GEM CarDeviceList — but no code reads it

---

## How the Audi Does It

The Audi's oil/inspection reset flow:

```
User: Car menu → Service → Reset

HMI Layer
  ↓ UPD_ID_requestInspectionReset
CarKombiPresCtrl / CarKombiExtPresCtrl
  ↓ RQST_InspectionReset
SPHCarKombi / SPHCarKombiExt (DSI service proxy)
  ↓ BAP or CDEF protocol
CCarKombiBAPHandler::sendInspectionReset()
  — or —
CCarKombiCDEFHandler::sendInspectionReset()
  ↓ CAN TP (Transport Protocol)
IOC → CAN bus → Instrument Cluster (module 0x17)
  ↓
Cluster resets internal counters
  ↓ Status response
processStatusSIAReset — "No error"
```

Two protocol variants exist:
- **BAP** (Bedien- und Anzeigeprotokoll) — older VAG clusters
- **CDEF** — newer VAG clusters (Cayenne 958 likely uses this)

The SIA data received FROM the cluster includes:
- Oil distance remaining (km)
- Oil time remaining (days)
- Inspection distance remaining (km)
- Inspection time remaining (days)

---

## Why the Porsche Doesn't Have It

Porsche deliberately removed the Car → Service menu from their PCM variant.
This forces owners to visit a dealer or independent shop with PIWIS/Durametric
for a 5-minute, $25-$150 service reset.

The per3 toggle at `0x0010001F` ("Service intervall") exists in the GEM
engineering screen definition, but no code in PCM3Root reads or acts on it.
Enabling it would have no effect.

---

## Viable Reset Approaches

Since the PCM firmware can't do it, the reset must come via OBD-II:

### 1. VCDS (if compatible with Cayenne cluster)
- Module [17 - Instruments]
- Adaptation: "Distance covered since last mileage-dependent inspection" → 0
- Adaptation: "Time since last time-dependent inspection" → 0
- Note: VCDS has limited Porsche support — may not work

### 2. ESP32 + MCP2515 CAN Tool (recommended for PCM-Forge)
- ESP32 dev board + MCP2515 CAN transceiver (~$15 total)
- Connect to OBD-II port
- Send UDS commands to cluster (diagnostic address 0x714/0x77E)
- DiagnosticSessionControl → SecurityAccess (if needed) → WriteDataByIdentifier
- Could be a dedicated PCM-Forge hardware accessory

### 3. ODIS Engineering (when VNCI 6154a is working)
- Connect as Touareg 7P (same cluster)
- Module 17 → Adaptation → Reset service intervals

### 4. Durametric / iCarScan / Launch
- Commercial tools that support Cayenne 958
- $100-$400 one-time purchase

---

## CAN Protocol Details (from Audi firmware)

The cluster communication uses two possible protocols:

### BAP (Bedien- und Anzeigeprotokoll)
- VW Group proprietary CAN application protocol
- Used on older MMI3G clusters
- Function IDs mapped to SIA attributes

### CDEF (newer protocol)
- Enhanced version used on newer clusters
- Same functionality as BAP but different framing

### UDS DIDs for Touareg 7P / Cayenne 958 Cluster
(from Ross-Tech wiki, VCDS adaptation channels)
- "Distance covered since last mileage-dependent inspection"
- "Time since last time-dependent inspection"
- Oil change counter (separate from inspection)

### Key CAN Addresses (standard VAG)
- Cluster diagnostic request:  0x714
- Cluster diagnostic response: 0x77E
- UDS services needed: 0x10 (DiagSession), 0x27 (SecAccess), 0x2E (WriteDID)

---

## Files Analyzed

| File | Size | Source |
|------|------|--------|
| PCM3Root (Porsche) | 6.6MB | PCM3_IFS1.ifs from PCM31RDW400 |
| MMI3GApplication (Audi) | 11MB | ifs-root.ifs from MU9411/41 |
| MMI3GMedia (Audi) | 8.0MB | same |
| MMI3GMisc (Audi) | 3.8MB | same |
| MMI3GNavigation (Audi) | 9.1MB | same |
| MMI3GTelephone (Audi) | 5.6MB | same |
| CarDeviceList.esd | 2KB | EFS engdefs |
| CarProtocollSwitch.esd | 2KB | EFS engdefs |
