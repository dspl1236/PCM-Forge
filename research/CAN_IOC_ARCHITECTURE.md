# CAN / IOC Architecture — PCM 3.1 Harman HN+ Platform

> Consolidated from 8 research documents. Covers the complete CAN communication
> path from application to physical bus, IOC channel map, NDR devctl interface,
> V850 hardware, and cross-platform notes.

## The Complete CAN Path

```
PCM3Root / MMI3GApplication (SH4 application)
   ↓ CGCANConnectionImpl
   ↓ CLibResMgr (devctl() calls)
/dev/ndr/cmd (QNX resource manager)
   ↓ CTransTel telegram framing
   ↓ CHBIpcProtocol (0xFADE magic header)
/dev/ipc/ioc/ch* (dev-ipc resource manager)
   ↓ PCI bus
Xilinx FPGA (PCI 0x10EE:0x9411)
   ↓ Internal bus
Renesas V850ES/SJ3 IO Controller
   ↓ On-chip CAN controller (CAN0 @ 0x03FEC000)
   ↓ CAN transceiver
Physical CAN bus (ISO 11898)
```

## NDR devctl Interface

Source: `NavigationNdrInfo` binary (563KB SH4 ELF). All use QNX `__DIOTF(class=0x05, cmd, size=4)`.

| DCMD | Cmd | Function | Description |
|------|-----|----------|-------------|
| 0xC004050B | 0x0B | ndrOpen | Register client (pid/tid) |
| 0xC004050A | 0x0A | checkVersion | Expects v3.0.0 (0x3000000) |
| 0xC0040507 | 0x07 | ndrWrite | Send CTransTel telegram |
| 0xC0040508 | 0x08 | ndrRead | Receive telegram (16,100B max) |

Usage pattern:
```c
fd = open("/dev/ndr/cmd", O_RDWR);
devctl(fd, 0xC004050B, &pid_tid_tel, ...);   // register
devctl(fd, 0xC004050A, &version_tel, ...);    // version check
devctl(fd, 0xC0040507, &write_tel, ...);      // send CAN frame
devctl(fd, 0xC0040508, &read_tel, ...);       // read response
```

CTransTel format: `CTransTel(functionId=4, classId, ndrId, value)` where classId 0=read, 1=write.

## IOC Channel Map

### Porsche Cayenne 958 (`/dev/ipc/ioc/`)

| Channel | Permissions | Purpose |
|---------|------------|---------|
| ch2 | rw-rw-rw- | CAN/IOC messages |
| ch3–ch4 | rw-rw-rw- | Shared access (symlinks) |
| ch5 | rw-rw-rw- | Sensor data (gyro, accel) |
| ch6 | rw-rw-rw- | CAN/IOC messages (BAP/SIA on Porsche) |
| ch7–ch10 | rw-rw-rw- | Available |
| debug | r--r--r-- | Traffic monitoring |
| onoff | r--r--r-- | Power state |
| watchdog | r--r--r-- | Watchdog timer |

### Audi A6 C7 MMI3G+ (`/dev/ipc/`)

| Channel | Data Size | Purpose |
|---------|----------|---------|
| ch2 | 380B | Heartbeat (120B/3s window) |
| ch5 | 5,250B | BAP SIA messages (main data) |
| ch4 | 360B | SiriusXM display data |
| ch3,ch6–ch11 | 0B | Blocked (no client registration) |

Key difference: Audi uses `/dev/ipc/chN`, Porsche uses `/dev/ipc/ioc/chN`.

## IOC Service Types (19 confirmed)

**CAN:** IOC_CAN_DRIVER, IOC_CAN_MATRIX, IOC_CAN_TP1 (UDS transport protocol)

**Diagnostics:** IOC_DIAGX, IOC_DIAG_SWNO

**MOST Network:** IOC_MOST_NETSVCREV, IOC_MOST_NETSVCVER, IOC_MOST_TRANSX

**Gateway:** IOC_GW_CFGVER, IOC_GW_POOL, IOC_GW_eRTAB, IOC_GW_iRTAB

**System:** IOC_BOLO, IOC_FRONT, IOC_POWERCONTROL, IOC_SWVERSION, IOC_SWRevision, IOC_PC_FUSEBYTES

`IOC_CAN_TP1` is the key service for UDS diagnostic commands to the instrument cluster.

## V850 IO Controller Hardware

**Chip:** Renesas V850ES/SJ3 (uPD70F3344–3368 series), 32-bit RISC, CMX-RTX RTOS.

CAN controller: 1–2 channels, 32 message buffers per channel, standard + extended IDs.
Registers at CAN0 base 0x03FEC000 (CnMDATA, CnMDLC, CnMCONF, CnMID, CnMCTRL).

The NDR resource manager abstracts all V850 register access — application code never touches hardware registers directly.

## CAN Bus Topology (Cayenne 958)

The PCM sits on the **Infotainment CAN** bus. The J533 gateway bridges to other buses:

| Bus | Access | Notes |
|-----|--------|-------|
| Infotainment CAN | Direct | BAP, media, phone |
| Diagnostic CAN | Via OBD-II | UDS to all modules via gateway |
| Comfort CAN | Via gateway | Body, doors, windows |
| Powertrain CAN | Via gateway | Engine, transmission |

**Gateway filtering:** The J533 gateway may block certain UDS requests from the infotainment bus. Direct OBD-II access bypasses this limitation.

## Cross-Platform Compatibility

All three platforms share the same CAN hardware stack:

| Platform | Application | IPC Path | IOC Path |
|----------|------------|----------|----------|
| Porsche PCM 3.1 | PCM3Root (6.6MB) | /dev/ipc/ioc/ | ch2, ch6 for CAN |
| Audi MMI3G+ | MMI3GApplication (10.7MB) | /dev/ipc/ | ch5 for BAP SIA |
| VW RNS-850 | MMI3GApplication (variant) | /dev/ipc/ | Similar to Audi |

The NDR devctl codes (0xC004050x) are identical across platforms. A CAN utility built for one platform should work on all three with path adjustments.

## Safety Notes

**Safe (read-only):** Reading IOC channels, reading devctl responses, pidin, sloginfo.

**Use caution (write):** UDS RoutineControl, WriteDataByIdentifier to cluster. Always test in extended diagnostic session first.

**Never from the head unit:** ECU flashing, gateway coding, key programming, immobilizer operations. These require proper diagnostic tools via OBD-II.
