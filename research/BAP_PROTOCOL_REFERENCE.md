# BAP Protocol Reference — Porsche PCM 3.1 Service Reset

## Date: May 7, 2026
## Status: All parameters extracted, building sender

---

## Credits & Sources

### korni92 / FIS-Writer-A6-A8-Q7
**GitHub:** github.com/korni92/FIS-Writer-A6-A8-Q7
**License:** GPL-3.0

Complete BAP DIS protocol documentation for Audi A6 4F / A8 D3 / Q7 4L.
Provided the BAP transport layer specification that enabled our work:
- CAN IDs 0x490/0x491 (confirmed identical on Porsche Cayenne 958)
- Packet structure (Byte 0 = type nibble + sequence counter)
- Handshake sequence (A0 open, A1 pong, A3 keepalive)
- ACK mechanism (0xBN where N = next expected sequence)
- Multi-frame protocol (0x20 body, 0x10 end)
- Error handling (0x9X busy, 0x09 fatal, 0xA8 reset)

### DrGER2 (Gary Rafe)
Prolific MMI3G researcher. Foundational knowledge of the HN+ platform
that made the firmware extraction and analysis possible.

### dspl1236 (Andrew)
All firmware binary analysis, on-car testing, and tool development:
- MMI3GApplication disassembly → FKT ID 0x03, LSG ID 0x11
- V850app.bin analysis → CAN IDs 0x490/0x491 from config table
- PCM3Root analysis → per 3 address mapping, IOC architecture
- IOC probe development and 3 on-car test iterations
- Web app and USB toolkit development

### daredoole
MMI3G-Toolkit contributor. PR #7 (release ZIP) and PR #8 (Pages fix).

---

## Complete BAP Command: Oil Service Reset

### Wire Format

```
CAN Bus: Cluster bus, 500 kbps
CAN ID:  0x490 (PCM → Cluster)
         0x491 (Cluster → PCM)

BAP Frame:
  LSG ID:  0x11 (Instrument Cluster / Kombi)
  FKT ID:  0x03 (SIA — Service Interval Adjustment)
  OpCode:  SET  (write/reset command)
```

### BAP Packet Structure (from FIS-Writer / korni92)

Every CAN frame is 8 bytes:
- Byte 0: Protocol header (high nibble = type, low nibble = sequence)
- Bytes 1-7: Payload

| Type | Name | Description |
|------|------|-------------|
| 0x10 | DATA END | Single/last frame, expects ACK |
| 0x20 | DATA BODY | Intermediate frame |
| 0xB0 | ACK | Acknowledge, low nibble = next expected seq |
| 0xA0 | OPEN | Channel open request |
| 0xA1 | PONG | Channel alive response |
| 0xA3 | PING | Channel alive check |
| 0xA8 | RESET | Channel disconnect |
| 0x90 | BUSY | Hardware busy (retry) |
| 0x09 | ERROR | Fatal protocol error |

### Handshake Sequence

```
1. MMI → Cluster:  A0 0F 8A FF 4A FF    (Open Request)
2. Cluster → MMI:  A1 0F 8A FF 4A FF    (Open Acknowledge)
3. Cluster → MMI:  A3                    (Ping)
4. MMI → Cluster:  A1 0F 8A FF 4A FF    (Pong)
   ... repeat ping/pong until stable (~1 second)
5. Parameter exchange (sequential, ACK after each)
6. Channel is OPEN — ready for commands
```

### InspectionReset Command (to be verified on-car)

After handshake, send FKT 0x03 with SET opcode:
```
CAN ID 0x490, 8 bytes:
  Byte 0: 0x10 | seq        (DATA END + sequence counter)
  Byte 1: LSG=0x11, FKT=0x03, OpCode=SET packed into BAP header
  Bytes 2-7: payload (may be empty for reset)
```

The exact byte packing of LSG/FKT/OpCode into the BAP header needs
verification. BAP 3.0 packs these into the first 19 bits:
- Bits 0-5: LSG ID (6 bits) → 0x11 = 10001
- Bits 6-11: FKT ID (6 bits) → 0x03 = 000011
- Bits 12-14: OpCode (3 bits) → SET
- Bits 15-18: Data length (4 bits)

---

## IOC Channel Handshake (CHBIpcProtocol)

### The Problem

IOC channels (ch2-ch10) are world-writable but raw reads block.
The V850 IO Controller requires CHBIpcProtocol client registration
via devctl() before CAN data flows.

### The 0xFADE Protocol

From PCM3Root string analysis:
```
CHBIpcProtocol — 0xFADE magic header
"telegram" framing
Xon/Xoff flow control
Resync via FPGA
```

### dev-ipc Configuration (from probe)

```
/proc/boot/dev-ipc -V 0x10ee -D 0x9600 -A 0xB0000 -I 0x0A -c 9 -n ipc/ioc -vvv
```

- Vendor: 0x10EE (Xilinx)
- Device: 0x9600
- Base address: 0xB0000
- Interrupt: 0x0A
- Channels: 9 (ch2-ch10)
- Namespace: ipc/ioc

### What We Need

The devctl() command sequence to register as a CHBIpcProtocol client
on an IOC channel, enabling CAN frame send/receive.

---

## V850 BAP Gateway Architecture — May 8, 2026

### BREAKTHROUGH: V850 is a BAP-Aware Gateway

The V850 firmware (576KB) contains explicit BAP/CDEF/SIA device routing.
It's not just a dumb CAN proxy — it's a protocol-aware gateway that
routes BAP frames to the correct CAN bus and device.

### V850 Device Registry (from string analysis)

**BAP Devices:**
ACC, DRC, RDK, OPS, **SIA**, Wiper, Clock, Seat, Standheater,
Seatheater, Interior light, Exterior light, Door locking, RVC/VPS,
ISafety, HUD, ZEM, LDW, SWA, AWV, VZA, SVC, RSE, MKE, TAD,
UGDO, Hybrid, Nightvision, AC Slave, Charisma, Seat V02

**CAN Bus Names:**
Komfort, Antrieb, Flexray, Clamp15, **Dashboard**, Infotainment,
Extended, Fahrwerk

**Protocol Support:** BAP + CDEF (both explicitly named)

### Key V850 Modules

| Offset | 4-char Code | Purpose |
|--------|-------------|---------|
| 0x0342E | GBAP | **BAP Gateway** — routes BAP frames |
| 0x00CB4 | KWPS | KWP2000 sub-bus |
| 0x00C44 | TP20 | Transport Protocol 2.0 |
| 0x00CFC | ONOF | Power management |
| 0x014C4 | PERS | Persistence |
| 0x00CAC | GATW | Main gateway |
| 0x01630 | DISS | Display service |

### IPC Channel Types

| Code | Purpose |
|------|---------|
| IPCN | IPC Normal (priority) |
| IPCP | IPC Priority |
| CfIpc | IPC Configuration |

### What This Means

The V850's GBAP module handles BAP routing. When PCM3Root sends a
message on ch6, it doesn't need to specify the CAN arbitration ID.
The V850 looks up the target device (SIA) and routes to the correct
CAN bus (Dashboard) with the correct CAN ID (0x490).

The message format on ch6 is likely:
```
[GBAP header] [Target device: SIA] [FKT: 0x03] [OpCode: SET]
```

The V850 translates this to:
```
CAN ID 0x490, Dashboard bus, BAP frame with LSG 0x11 FKT 0x03
```

### Next: Decode GBAP Message Format

The GBAP module at 0x0342E is the key. Need to:
1. Disassemble the GBAP message handler
2. Find the device ID table (SIA = which numeric ID?)
3. Determine the gateway command byte format
4. Build a test message to write to ch6
