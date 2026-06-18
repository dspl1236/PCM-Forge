# PCM-Forge Bench Dongle v0.1.0

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
