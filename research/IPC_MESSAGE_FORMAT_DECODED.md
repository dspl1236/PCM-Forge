# IPC Message Format — Decoded from Live A6 Capture

## Date: May 8, 2026
## Source: Live capture from /dev/ipc/ch5 on Audi A6 C7 root shell

---

## THE FORMAT

```
[TYPE:1][SUBTYPE:1][LENGTH:2 LE][DATA:LENGTH bytes][TICK:2 LE]

Total per message: 4 + LENGTH + 2 bytes
```

## Message Types (from 5,250 byte capture on ch5)

| Type | Sub | Len | Count | Purpose |
|------|-----|-----|-------|---------|
| 0x01 | 0x00 | 6 | 7 | Sync/timestamp heartbeat |
| 0x02 | 0x01 | 8 | 10 | ACK (8 zero bytes) |
| 0x03 | 0x01 | 4 | 2 | Control (value=0x00000001) |
| **0x0F** | **0x03** | **16** | **2** | **BAP SIA COMMAND** |
| 0x10 | 0x00 | 14 | 11 | CAN data frame |

## BAP SIA Command (Type 0x0F, Sub 0x03)

**This is live BAP SIA data captured on the Audi A6!**

```
Type: 0x0F
Sub:  0x03  ← FKT ID 0x03 = SIA (Service Interval Adjustment)
Len:  0x0010 (16 bytes)
Data: 12 02 1A 01 00 00 00 00 00 00 00 00 00 00 00 00
Tick: varies (incrementing 16-bit counter)
```

### BAP Payload Decode

```
Byte 0: 0x12 — BAP LSG/FKT packed header
Byte 1: 0x02 — OpCode (STATUS = receive data from cluster)
Byte 2: 0x1A — Data length or subfunction (26 decimal)
Byte 3: 0x01 — Subfunction or flags
Bytes 4-15: All zeros (empty SIA data = no service due)
```

## Channel Map (Audi A6 C7 MMI3G+)

| Channel | Data? | Size | Purpose |
|---------|-------|------|---------|
| ch2 | YES | 380B | Heartbeat (20-byte repeating, counter at byte 17) |
| ch3 | no | 0 | Blocked |
| ch4 | no | 0 | Blocked |
| ch5 | **YES** | **5,250B** | **Main CAN/BAP data** |
| ch6 | no | 0 | Blocked |
| ch7 | no | 0 | Blocked |
| ch8 | no | 0 | Blocked |
| ch9 | no | 0 | Blocked |
| ch10 | no | 0 | Blocked |
| ch11 | no | 0 | Blocked |

Note: A6 uses /dev/ipc/ch5 for CAN data.
Porsche uses /dev/ipc/ioc/ch6 for CAN data.

## ch2 Heartbeat Format

Fixed 20-byte message repeating at ~100ms:
```
22 00 01 00 00 03 2A 27 01 0F 3D 05 00 E1 6F 00 01 [COUNTER] 00 03
```
Counter at byte 17 increments by 1 each message (0xD8, 0xD9, 0xDA...)

## How to Send InspectionReset

To reset the oil service light, write to the IPC channel:

```
TYPE: 0x0F          (BAP command)
SUB:  0x03          (FKT ID = SIA)
LEN:  0x10 0x00     (16 bytes)
DATA: [BAP InspectionReset payload with OpCode SET]
TICK: 0x00 0x00     (or current tick)
```

The BAP payload for InspectionReset needs the SET opcode
instead of the STATUS opcode (0x02) we see in the capture.

### On Audi A6: write to /dev/ipc/ch5
### On Porsche Cayenne: write to /dev/ipc/ioc/ch6

## Verification Method

Captured by connecting to A6 root shell (192.168.0.154:23)
and reading live IPC data:

```bash
cat /dev/ipc/ch5 > /tmp/ch5.bin &
sleep 3
kill $! 2>/dev/null
# Transfer via: cat /tmp/ch5.bin | nc.shle -w 3 192.168.0.91 9999
```
