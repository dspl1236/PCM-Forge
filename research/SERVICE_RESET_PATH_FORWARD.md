# Service Reset — Path Forward

## Date: May 7, 2026
## Status: CDEF command injection is the only viable internal path

---

## What We Ruled Out

### PCM Persistence (CVALUE files) — NOT the source
IOC probe captured all 13 CVALUE files from /HBpersistence/.
None contain service interval data. The files store:
- `CVALUE0002032d` — Region code ("USA")
- `CVALUE000203b3` — Nav database versions
- `CVALUE0002064d` — Link status
- `CVALUE00020685` — Vehicle telemetry (GPS, sensors)
- `CVALUE00020686` — Route/trip log (4,114 bytes, GPS coordinates)
- `CVALUE00020687` — Trip counters/consumption (488 bytes)
- `CVALUE0002068f` — Full trip history (5,755 bytes)
- `CVALUE010b0006` — Engineering state (0x010b namespace)

Service interval counters live in the **instrument cluster**, not the PCM.
The PCM receives SIA data FROM the cluster via CDEF, displays it, but
does not store it or have authority to modify it.

### per 3 Persistence Addresses — Wrong tool syntax
persdump2 on PCM takes `persdump2 <PersFile> [v][s]` (CVALUE file path),
not `persdump2 <type> <address>` like the Audi version. The `per 3`
addresses used in ESD files (e.g., `int per 3 0x0010001F`) are read
by PCM3Root internally through a different mechanism — not through
persdump2.

### NDR / devctl — Wrong device entirely
NDR is the Navigation Data Router for GPS/sensor data.
CAN bus goes through IOC channels with CHBIpcProtocol.
All 5 NDR probe versions crashed because they targeted the wrong device.

### showScreen — Exclusive lock, cannot bypass
layermanager exists but PCM3Root holds exclusive HMI lock.
`lmgrHMIConnect` fails every time. No display overlay possible
without killing PCM3Root's connection first (risky).

---

## The Only Internal Path: CDEF Command Injection

### Why CDEF (not BAP)
- 2016 Cayenne 958 = MY2015+ = CDEF cluster (CAN-direct)
- BAP runs over MOST (fiber optic) — the Cayenne uses CAN for cluster
- MMI3GApplication has both handlers; PCM3Root has neither
- The cluster doesn't care who sends the command — it validates
  message format, not source identity

### What We Need

1. **CDEF frame format** — the exact CAN arbitration ID and payload
   structure for the InspectionReset command

2. **CAN channel mapping** — which IOC channel (ch2-ch10) carries
   CDEF traffic to the instrument cluster

3. **A sender** — either a shell script using IOC devctl(), or a
   cross-compiled QNX SH4 binary

### How To Get the CDEF Frame Format

**Option A: Capture from ODIS/PIWIS**
1. Connect VNCI 6154a to OBD-II
2. Run the oil service reset via ODIS (Touareg 7P platform)
3. Simultaneously capture IOC traffic on the PCM (via USB script)
4. Correlate: the CDEF frame that appears on IOC during the reset
   IS the command we need to replicate

**Option B: Reverse engineer from PCM3Root**
The Audi MMI3GApplication has `CCarKombiCDEFHandler::sendInspectionReset`.
PCM3Root doesn't have it, but the underlying CDEF transport layer is
the same Harman code. We can:
1. Find CCarKombiCDEFHandler in MMI3GApplication (already extracted)
2. Disassemble sendInspectionReset to get the CDEF FKT ID and payload
3. Find the CAN arbitration ID from the CDEF config
4. Replicate on Porsche

**Option C: Decode from VW BAP 3.0 specification**
The BAP/CDEF protocol is documented in VW internal specs. The
FKT ID for InspectionReset is standardized across the VW Group.
Community resources (Ross-Tech forums, BAP documentation leaks)
may have the exact values.

### Implementation Plan

**Phase 1: Get the CDEF command (any of Options A/B/C above)**
- FKT ID for InspectionReset
- LSG ID for the instrument cluster
- CAN arbitration ID for CDEF to cluster
- Payload format (if any — reset might be a simple set command)

**Phase 2: Identify the IOC channel**
From probe results: ch2-ch10 are all CAN channels (world-writable).
We need to know which one reaches the cluster. Options:
- Correlate channel timestamps with known CAN traffic
- Try each channel systematically (safe — cluster ignores unknown senders)
- Check PCM3Root config for channel assignments

**Phase 3: Build the sender**
Two approaches, both deployed via USB stick:

**Approach A: Shell script with devctl (preferred)**
```bash
#!/bin/sh
# service_reset_cdef.sh — Send CDEF InspectionReset via IOC
# Requires: correct channel, arbitration ID, FKT ID

CHANNEL="/dev/ipc/ioc/ch6"  # TBD: correct channel
# devctl() call to send CDEF frame
# Format: CHBIpcProtocol 0xFADE framing + CAN telegram
```

**Approach B: Cross-compiled SH4 binary**
Uses dlopen() for devctl() (same approach as NDR probe, but
targeting the correct device this time). Implements the minimal
CHBIpcProtocol client registration handshake then sends the
CDEF InspectionReset frame.

**Phase 4: ESD Engineering Menu Button (permanent)**
Once the sender works, deploy as a GEM engineering screen:
```
screen ServiceReset Car
script
   value    sys 1 0x0100 "/scripts/service_reset_cdef.sh"
   label    ">> RESET OIL SERVICE <<"
```

DBGModeActive is already set. SOURCE+SOUND → Car → ServiceReset.
No USB needed after first install.

---

## What We Confirmed Today (IOC Probe Results)

### PCM Hardware & Software
- Firmware: Porsche PCM3.1 MOPF SOP STEP9.6 (15245AS9)
- QNX 6.3.2, PSP3, built June 12, 2015
- Carmine GPU: 800×480 + 240×257 dual display, ARGB1555, 128MB VRAM
- Image codecs: PNG, BMP, GIF, JPG all supported

### IOC Channels
- 12 channels: ch2-ch10 (rw), debug/onoff/watchdog (ro)
- All data channels block on raw read (client registration required)
- dev-ipc configured with 9 channels: `-c 9 -n ipc/ioc`
- FPGA: Xilinx vendor 0x10EE, device 0x9600

### Boot Screen (custom screen feature CONFIRMED ready)
- 78 factory screens on HDD (13-64KB each)
- Active: CustomBootscreen_067.bin (35,394 bytes) = Cayenne S E-Hybrid
- /HBpersistence/ free: 21,150 blocks (~10MB)
- Slot 100 clear, JPEG natively supported
- IFS fallback: PCM31_bootScreenPorscheLogo.jpg (64,200 bytes)

### Display Stack
- layermanager exists, PCM3Root holds exclusive HMI lock
- showScreen cannot display (lmgrHMIConnect fails)
- No /dev/gf* devices — all graphics via layermanager only

### Persistence Model
- Porsche uses CVALUE flat files (not QDB DataPST.db like Audi)
- persdump2 syntax: `persdump2 <PersFile> [v][s]`
- 13 CVALUE files captured, none contain service interval data
- Service counters live in instrument cluster, not PCM

### Key Running Processes
- PCM3Root (PID 24607) — main application
- qconn (PID 196661) — remote GDB available
- qdb (PID 147495) — QNX database engine
- dev-i2c-hbfpga (PID 147498) — I2C/EEPROM access
- servicebroker (PID 16414) — DSI service broker
- proc_scriptlauncher (PID 176178) — USB script handler

---

## Priority Next Steps

1. **Disassemble sendInspectionReset in MMI3GApplication**
   Get the CDEF FKT ID, LSG ID, and payload format.
   File: `D:\MMI\ifs_extract\MMI3GApplication` (10.7MB, K0821)

2. **Find CDEF CAN arbitration IDs**
   Either from MMI3GApplication config tables or from VW BAP docs.

3. **Test external UDS reset via VNCI + ODIS**
   Quick validation that the cluster accepts a reset command at all.
   Module 0x17, RoutineControl or WriteDataByIdentifier.

4. **Build CDEF sender for IOC channel**
   Once we have the frame format, build and test.
