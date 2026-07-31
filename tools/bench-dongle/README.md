# PCM-Forge Bench Dongle v2.0.0

Arduino Nano + MCP2515 CAN tool for bench-testing Porsche PCM 3.1 units.

The PCM 3.1's V850 IOC monitors the infotainment CAN bus for activity before powering on the SH4 main board. Without CAN traffic, the unit won't boot — even with 12V applied. This dongle provides the wake signal.

## Hardware

- Arduino Nano (or clone)
- MCP2515 CAN module (with TJA1050 transceiver, ~$3)
- 120Ω resistor (CAN bus termination)
- 12V bench power supply (2A minimum)

## Wiring

### Nano → MCP2515 (SPI)

| Nano | MCP2515 |
|------|---------|
| D10 | CS |
| D11 | MOSI (SI) |
| D12 | MISO (SO) |
| D13 | SCK |
| D2 | INT |
| 5V | VCC |
| GND | GND |

### MCP2515 → PCM Quadlock

| MCP2515 | Quadlock Pin | Function |
|---------|-------------|----------|
| CAN-H | Pin 9 | CAN High |
| CAN-L | Pin 11 | CAN Low |

Add a **120Ω resistor** between CAN-H and CAN-L (bus termination).

### Bench Power → PCM Quadlock

| Supply | Quadlock Pin | Function |
|--------|-------------|----------|
| +12V | Pin 4 | Power (Term 30) |
| GND | Pin 8 | Ground (Term 31) |

## Configuration

Edit the `#define` block at the top of `bench_dongle.ino`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CAN_SPEED` | `CAN_100KBPS` | CAN bus speed. Try `CAN_500KBPS` if PCM doesn't wake |
| `CAN_CRYSTAL` | `MCP_8MHZ` | Crystal on your MCP2515 board (8 or 16 MHz) |
| `ENABLE_VIN_SPOOF` | `0` | Set to `1` to send a fake VIN on the bus |
| `SPOOF_VIN` | `WP0AA2A70BL000000` | 17-char VIN to spoof |
| `ENABLE_SNIFFER` | `1` | Print received CAN frames to serial monitor |

## Dependencies

Install via Arduino Library Manager:
- **mcp_can** by coryjfowler ([GitHub](https://github.com/coryjfowler/MCP_CAN_lib))

## Usage

1. Flash the sketch to your Nano
2. Wire up MCP2515, termination resistor, and PCM power
3. Open serial monitor at **115200 baud**
4. Apply 12V to the PCM
5. Watch for the PCM to boot (screen should light up within 10-15 seconds)
6. Sniffer will print any CAN frames the PCM sends back

## Status LED

Pin D9 blinks on each wake frame sent (D13 can't be used — it's SPI SCK on the Nano).

- **Steady blink** (1Hz) = sending wake frames, normal operation
- **Rapid blink** = MCP2515 init failed, check wiring and crystal

## Features

- **Wake** — periodic CAN frame to boot the V850 IOC
- **Sniffer** — prints all received CAN traffic to serial
- **VIN Spoof** — optional fake gateway VIN broadcast for testing activation code validation after VIN change

## Bench Test Checklist

Once the PCM boots:

- [ ] Insert USB with PCM-Forge diagnostic script — verify VIN, firmware version, PagSWAct.002
- [ ] Test activation codes — generate PagSWAct.002, insert USB, reboot
- [ ] VIN swap — change VIN via Engineering menu, reboot, check if features survive
- [ ] Cycle countdown — reboot repeatedly, monitor feature status
- [ ] Cross-firmware — test v4.76 vs v3.43 vs v2.47 PagSWAct format


## Using it

v1 put every setting behind a `#define`, so each experiment cost a reflash.
v2 takes runtime commands over serial instead, because on a bench where the
bitrate is not yet known and the interesting question is *"does this frame
change the unit's behaviour"*, the reflash loop is the whole cost.

A host script drives it (`pip install pyserial`):

```
python bench_can.py COM4 scan                    find the bitrate
python bench_can.py COM4 sniff 30 bus.log        listen, report the ID map
python bench_can.py COM4 send 710 0102030405060708
python bench_can.py COM4 hold 0 100 710 01020304 repeat every 100ms
python bench_can.py COM4 shell                   type dongle commands directly
```

Or talk to it directly at 115200; `?` lists the commands.

Received frames print one per line, `R <millis> <id> <dlc> <data>`, so a log is
trivial to parse.

## Two settings that waste the most time

**The crystal.** MCP2515 modules ship with 8 MHz or 16 MHz oscillators and look
identical. The wrong setting makes every bitrate wrong by a factor of two, and
it presents as *silence* rather than as an error — so it reads as "CAN is dead"
and sends people to check wiring. If `scan` reports zero frames at every rate,
try `x 16` (or `x 8`), then `o`, and scan again **before** touching the loom.

**Listen-only, in both directions.** The dongle starts silent, because a wrong
bitrate in normal mode floods a live bus with error frames and can stop a
working node transmitting. But the converse bites on a bench: **a lone
transmitter with nobody to ACK retries forever and goes error-passive.** If the
PCM is alone with a silent dongle, it effectively cannot talk — so a quiet bus
does not prove the unit is quiet. Once the bitrate is confirmed, leave
listen-only (`l 0`, `o`) so it has a partner.

**Termination** matters more here than in a car. CAN wants 120 Ω at each end;
a two-node bench usually needs you to add at least one. Under-terminated buses
fail intermittently and look like software problems.

## Why this might matter beyond waking the unit

`/dev/sysregs/IpodPwrEn` — the USB port's power switch — defaults to off, and
`usbPowerMonitor` actively switches it down. On a real car those decisions
follow terminal status arriving over CAN. A bench unit with a dead bus has no
reason to believe the car is on, which is a better explanation for a dim USB
device than any cable fault. Worth testing before rewiring anything.
