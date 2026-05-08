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
