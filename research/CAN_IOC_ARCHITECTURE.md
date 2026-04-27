# PCM 3.1 CAN Bus / IOC Architecture

## Discovery Date: April 19, 2026

## The Complete CAN Path

```
PCM3Root (SH4 application)
   ↓ CGCANConnectionImpl
   ↓ CLibResMgr (devctl() calls)
/dev/ndr (QNX resource manager)
   ↓ CHBIpcProtocol (0xFADE header)
/dev/ipc/ioc/ch* (dev-ipc resource manager)
   ↓ PCI bus
Xilinx FPGA (0x10EE:0x7007)
   ↓ Internal bus
V850 IO Controller
   ↓ CAN transceiver
Physical CAN bus
```

## IOC Channel Map (from live Cayenne 958)

| Channel | Permissions | Used By | Purpose |
|---------|------------|---------|---------|
| ch2 | nrw-rw-rw- | PCM3Root | CAN/IOC messages |
| ch3 | nrw-rw-rw- | symlink | Shared access |
| ch4 | nrw-rw-rw- | symlink | Shared access |
| ch5 | nrw-rw-rw- | ndr | Sensor data (gyro, accel) |
| ch6 | nrw-rw-rw- | PCM3Root | CAN/IOC messages |
| ch7 | nrw-rw-rw- | available | - |
| ch8 | nrw-rw-rw- | PCM3Root | CAN/IOC messages |
| ch9 | nrw-rw-rw- | available | - |
| ch10 | nrw-rw-rw- | available | - |
| debug | nr--r--r-- | monitoring | Traffic sniffing |
| onoff | nr--r--r-- | system | Power state |
| watchdog | nr--r--r-- | system | Watchdog timer |

## IOC Service Types (19 total)

### CAN Services
- `IOC_CAN_DRIVER` — Low-level CAN driver control
- `IOC_CAN_MATRIX` — CAN signal/message matrix
- `IOC_CAN_TP1` — **CAN Transport Protocol (UDS diagnostics)**

### Diagnostics
- `IOC_DIAGX` — Extended diagnostics
- `IOC_DIAG_SWNO` — Diagnostic SW number

### MOST Network
- `IOC_MOST_NETSVCREV/VER` — MOST service info
- `IOC_MOST_TRANSX` — MOST transport

### Gateway
- `IOC_GW_CFGVER` — Config version
- `IOC_GW_POOL` — Message pool
- `IOC_GW_eRTAB/iRTAB` — Routing tables

### System
- `IOC_BOLO/FRONT/POWERCONTROL/SWVERSION/SWRevision/PC_FUSEBYTES`

## IPC Message Protocol

- **Magic header**: `0xFADE`
- **Frame counter** for sequencing
- **Telegram format** (VW Group standard)
- **Flow control**: XOFF/XON
- **ACK/NACK** with retry logic

## Key Findings

1. All IOC channels are **world-writable** (nrw-rw-rw-)
2. CAN access requires going through `/dev/ndr` via `devctl()` calls
3. `IOC_CAN_TP1` is the UDS transport protocol service
4. FTP + telnet are configured in inetd.conf but no network interface is up
5. Network interfaces `/dev/io-net/en1` and `/dev/io-net/en5` exist in firmware

## Oil Service Reset Path

To reset the oil service interval:
1. Open `/dev/ndr` resource manager
2. Use `devctl()` to send IOC_CAN_TP1 message
3. Message contains UDS RoutineControl or WriteDataByIdentifier
4. Target: Instrument cluster (Kombi) diagnostic address
5. V850 IOC routes the frame to the CAN bus

---

## V850ES/SJ3 IOC Hardware (Renesas Datasheet)

### Chip: Renesas V850ES/SJ3 (μPD70F3344-3368 series)
- 32-bit RISC CPU
- On-chip CAN controller (1 or 2 channels)
- IEBus controller (automotive LAN)
- Used as IOC (IO Controller) in Harman PCM 3.1

### CAN Controller Registers (Chapter 19)
- Base address: 0x03FEC000 (CAN0), 0x03FED000 (CAN1)
- 32 message buffers per channel (CnMDATA, CnMDLC, CnMCONF, CnMID, CnMCTRL)
- Standard (11-bit) and Extended (29-bit) CAN IDs supported
- Baud rate configurable via prescaler + bit timing
- Error states: Error Active → Error Passive → Bus-Off

### Full CAN Communication Path (PCM 3.1)
```
Application (PCM3Root/uds_send)
    │
    ├─ open("/dev/ndr/cmd")
    │  devctl(fd, 0xC0040507, data)  ← class=5, cmd=7 WRITE
    │  devctl(fd, 0xC0040508, data)  ← class=5, cmd=8 READ
    │
    ▼
NDR Resource Manager (/proc/boot/ndr)
    │  CLibResMgr → devctl → CTransTel telegram
    │
    ▼
dev-ipc (/dev/ipc/ioc/ch*)
    │  CHBIpcProtocol (0xFADE magic, telegram framing)
    │  IOC service channels ch2-ch10
    │
    ▼
Xilinx FPGA (IPC bridge, PCI device 0x10EE:0x9411)
    │  Hardware bridge between SH4 bus and V850
    │
    ▼
V850ES/SJ3 IO Controller
    │  On-chip CAN controller
    │  32 message buffers
    │  CAN0 registers at 0x03FEC000
    │
    ▼
Physical CAN Bus (ISO 11898)
    │  CAN-H / CAN-L via transceiver
    │
    ▼
Instrument Cluster (CAN ID 0x0717 for UDS)
```

### IOC Service Types (19 identified)
From our CAN architecture research, dev-ipc registers IOC channels:
- ch2-ch6: CAN transport (IOC_CAN_TP1 = UDS diagnostic)
- ch7-ch8: Display/media IPC
- ch9-ch10: Misc services
- debug, onoff, watchdog: System control

### Implications for Oil Service Reset
The UDS path: uds_send → NDR devctl (class=5, cmd=7) → NDR process
→ dev-ipc → FPGA → V850 CAN controller → CAN bus → cluster

The devctl codes (0xC0040507/0xC0040508) go to NDR, which handles
the CAN transport protocol internally. We don't need to understand
the V850 register layout — NDR abstracts it. But the V850 datasheet
confirms the hardware supports standard CAN messaging.

### Reference
Renesas V850ES/SJ3 User's Manual: Hardware
Rev.5.00, Feb 2012 (REN_r01uh0248ej0500)
Chapter 19: CAN Controller (pages 728-886)
