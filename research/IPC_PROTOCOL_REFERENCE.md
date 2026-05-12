# IPC Protocol Reference — Message Format and Wire Encoding

> Consolidated from IOC_IPC_PROTOCOL_DECODED.md, IPC_MESSAGE_FORMAT_DECODED.md,
> and IOC_CAN_ARCHITECTURE_CORRECTED.md.

## dev-ipc Protocol

Source: `dev-ipc` binary (74,979 bytes) from PCM 3.1 IFS. Standard QNX resource manager.

### Wire Format (CHBIpcProtocol)

Magic header `0xFADE` with telegram framing (VW Group standard).

### Version Negotiation
Client opens channel, exchanges version info. Protocol version must match for data flow.

### Flow Control
XOFF/XON mechanism prevents buffer overflow. Client must handle flow control frames.

### Client Registration
Raw `cat /dev/ipc/ioc/chN` blocks because reads require proper client registration via devctl(). Without registration, the channel has no data to deliver.

### ACK/NACK
Every telegram gets an acknowledgment. Retry logic handles NACK responses.

## IPC Message Format (from live captures)

Source: Live capture from `/dev/ipc/ch5` on Audi A6 C7 root shell, 5,250 bytes.

### Record Structure

```
[TYPE:1][SUB:1][LEN:2 LE][DATA:N][TICK:2 LE]
```

| Field | Size | Encoding | Description |
|-------|------|----------|-------------|
| TYPE | 1 byte | unsigned | Message type |
| SUB | 1 byte | unsigned | Sub-type |
| LEN | 2 bytes | Little-endian | Data payload length |
| DATA | N bytes | varies | Payload |
| TICK | 2 bytes | Little-endian | Timestamp/sequence |

### Message Types (from A6 ch5 capture)

| Type.Sub | Count | Payload | Purpose |
|----------|-------|---------|---------|
| 0x01.00 | 72 | 6B | Sync/heartbeat |
| 0x02.01 | 115 | 8B zeros | ACK |
| 0x03.01 | 19 | 4B | Control |
| 0x0F.03 | 13 | 16B | BAP SIA STATUS |
| 0x10.00 | 115 | 14B | CAN data frames |

### BAP SIA Messages (Type 0x0F, Sub 0x03)

16-byte payload with BAP header:

```
Byte 0: [LSG_ID:6][FKT_ID_high:2]
Byte 1: [FKT_ID_low:4][OP_CODE:4]
Bytes 2-15: SIA data
```

BAP OpCodes: 0=GET, 1=SET, 2=STATUS, 3=ERROR, 4=SETGET, 5=INCREMENT, 6=ABORT, 7=CHANGED

### Baseline (idle A6)
`12 02 1A 01 00 00 ...` → LSG=4, FKT=32, OpCode=2 (STATUS)

### During oil service reset (A6)
`44 02 06 02 00 00 ...` → LSG=17 (cluster), FKT=0, OpCode=2 (STATUS)

Status byte transitions during reset: `06` → `05` → `08` → `06`

The SET command (MMI → cluster) travels via MOST fiber on the A6, not through IPC ch5. On Porsche, the CDEF path uses CAN instead.

## ch2 Heartbeat Format

120 bytes per 3-second window. Simple periodic keepalive between SH4 and V850.

## Platform Differences

| Platform | SIA Channel | BAP Path | Reset Path |
|----------|------------|----------|------------|
| Audi MMI3G+ | ch5 | MOST fiber | BAP via MOST |
| Porsche PCM 3.1 | ch6 | CAN via IOC | CDEF via CAN |

The IPC message format is identical across platforms. Only the channel number and transport mechanism differ.
