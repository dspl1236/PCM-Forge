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
