# IOC IPC Protocol — Decoded from dev-ipc Binary

## Date: May 7, 2026
## Source: dev-ipc binary (74,979 bytes) from PCM 3.1 IFS

---

## Key Discovery: Standard QNX Resource Manager

dev-ipc uses the QNX standard resource manager framework:
- `iofunc_open_default` — standard open() handling
- `iofunc_read_verify` — standard read() support
- `iofunc_write_verify` — standard write() support
- `iofunc_devctl_default` — standard devctl() with custom extensions

**This means standard POSIX I/O works on IOC channels!**

```c
int fd = open("/dev/ipc/ioc/ch6", O_RDWR);
write(fd, bap_frame, frame_length);   // send message
read(fd, response, sizeof(response));  // receive response
```

No special devctl() registration needed. dev-ipc auto-registers
clients on open() and tracks them internally.

## Protocol Details

### Version Negotiation
```
"dev-ipc: Version conflict (required: %02X, received: %02X"
```
Automatic on channel open. Two protocol versions supported:
- v1.0 (default)
- v2.0 (selectable via -p flag)

### Flow Control
- XON/XOFF per channel
- "dev-ipc: XOFF for channel %u received" — pause transmit
- "dev-ipc: XON for channel %u received" — resume transmit

### Message Format
```
"dev-ipc: Msg [TX, ch: %02u, len: %03u]: %s"
"dev-ipc: Msg [RX, ch: %02u, len: %03u]: %s"
```
Messages have: channel number + length + data bytes.
dev-ipc handles HPIPC framing (0xFADE headers) internally.

### Client Tracking
```
"dev-ipc: Client count changed (ch:%u, old:%u, new:%u)"
```
Clients are tracked per channel. Registration is automatic on open().

### ACK/NACK
```
"dev-ipc: ACK timeout"
"dev-ipc: NACK received"
"dev-ipc: Repeat message (ch: %u)"
```
Reliability layer handled by dev-ipc, not the application.

### Error Handling
```
"dev-ipc: Receive error detected (%u)"
"dev-ipc: Message for unknown channel received"
"dev-ipc: Block error"
```

## dev-ipc Configuration (from probe)

```
/proc/boot/dev-ipc -V 0x10ee -D 0x9600 -A 0xB0000 -I 0x0A -c 9 -n ipc/ioc -vvv
```

| Parameter | Value |
|-----------|-------|
| Vendor | 0x10EE (Xilinx FPGA) |
| Device | 0x9600 |
| Base addr | 0xB0000 |
| Interrupt | 0x0A (10) |
| Channels | 9 (ch2-ch10) |
| Namespace | ipc/ioc |

## BAP Channel Discovery Plan

We know CAN IDs 0x490/0x491. We need to find which IOC channel
(ch2-ch10) carries this traffic. Simple probe:

```bash
#!/bin/sh
# bap_channel_scan.sh — find which IOC channel carries BAP traffic
for ch in 2 3 4 5 6 7 8 9 10; do
    echo -n "ch${ch}: "
    # Open channel, write BAP A0 handshake, check for A1 response
    # A0 = Open Request: A0 0F 8A FF 4A FF (6 bytes)
    echo -ne '\xA0\x0F\x8A\xFF\x4A\xFF' > /dev/ipc/ioc/ch${ch}
    # Read response with 2-second timeout
    timeout 2 dd if=/dev/ipc/ioc/ch${ch} bs=8 count=1 2>/dev/null | xxd
done
```

The channel that responds with `A1 0F 8A FF 4A FF` is the BAP cluster channel.

## Why Reads Blocked in IOC Probe

The probe's `dd if=/dev/ipc/ioc/chN` blocked because:
1. No incoming data on that channel (read waits for data)
2. NOT because of missing client registration

dev-ipc auto-registers clients. The read simply has nothing to return
until someone sends data TO us on that channel.

---

## Update: May 8, 2026 — On-Car BAP Scan Results

### Channel Map (from PCM3Root firmware analysis)

| Channel | Module | Purpose |
|---------|--------|---------|
| ch2 | CGOnOffDevCtrlWorker | Power management (ONOF) |
| ch6 | **CGCANConnectionImpl** | **CAN bus communication** |
| ch8 | Data receiver | General data (hex dump log) |
| ch3-5, 7, 9-10 | Unknown | Unmapped, likely MOST/other |

Source: String references to `/dev/ipc/ioc/chN` in PCM3Root binary.

### BAP Scan Results

All 9 channel writes succeeded (exit=0) but no responses.
Raw BAP A0 bytes don't reach the cluster because:

1. **IOC channels carry V850 telegrams, not raw CAN frames**
2. CGCANConnectionImpl constructs messages with service type
   headers (IOC_CAN_DRIVER / IOC_CAN_MATRIX / IOC_CAN_TP1)
3. The V850 uses these service types to route to the correct
   CAN bus with the correct arbitration ID

### IOC Service Types (from PCM3Root)

| Service | Purpose |
|---------|---------|
| IOC_CAN_DRIVER | Low-level CAN driver access |
| IOC_CAN_MATRIX | CAN signal/message matrix (BAP likely here) |
| IOC_CAN_TP1 | CAN Transport Protocol (UDS diagnostics) |
| IOC_GW_POOL | Gateway pool |
| IOC_GW_CFGVER | Gateway config version |
| IOC_GW_iRTAB | Internal routing table |
| IOC_GW_eRTAB | External routing table |
| IOC_GW_eRTABDATE | External routing table date |
| IOC_DIAG | Diagnostic service |

### showScreen slay+restart Test

- `slay layermanager` returned exit=1 (FAILED to kill)
- showScreen still got `lmgrHMIConnect failed`
- Layermanager was restarted (PID 1298436)
- System eventually rebooted (likely V850 watchdog from IOC writes)

### Next Steps for BAP Sender

The CGCANConnectionImpl message format needs to be decoded.
Options:

1. **Root shell approach** — Connect ethernet adapter, get root shell,
   use GDB (qconn available) to trace CGCANConnectionImpl::write
   while triggering a known CAN event

2. **V850 protocol decode** — Reverse engineer the HPIPC telegram
   format from V850app.bin to understand service type headers

3. **External approach** — Use VNCI 6154a to send the BAP reset
   directly on CAN 0x490 via OBD-II, bypassing the PCM entirely.
   This is the fastest path to a working reset.
