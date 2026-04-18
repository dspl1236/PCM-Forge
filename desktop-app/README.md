# PCM-Forge Desktop App

Electron desktop application for Porsche PCM 3.1 activation code generation
and ESP32-CAN device programming.

## Features

### Tab 1: Generate Codes
- Enter VIN (17 digits)
- Select vehicle model (Cayenne/911/Panamera/Boxster)
- Generate all 26 activation codes instantly
- Copy individual codes or all at once
- Download PagSWAct.002 file for USB stick deployment

### Tab 2: Device Programmer
- Connect to ESP32-CAN dongle via COM port
- Auto-read VIN from vehicle over OBD-II
- Auto-detect vehicle model from VIN prefix
- Select features with checkbox toggles
- Apply activations directly to the car

## Setup

```bash
cd desktop-app
npm install
npm start
```

## Build Distributable

```bash
# Windows installer
npm run build:win

# macOS DMG
npm run build:mac

# Linux AppImage
npm run build:linux
```

## Hardware Requirements (Tab 2)

ESP32 with CAN transceiver (e.g., Macchina A0 or ESP32 + MCP2515)
running the [esp32-isotp-ble-bridge](https://github.com/dspl1236/esp32-isotp-ble-bridge-c7vag)
firmware, connected to the vehicle's OBD-II port.

## Architecture

```
Desktop App (Electron)
  ├── index.html    — UI with RSA code generator (BigInt)
  ├── main.js       — Electron main process + serial port IPC
  ├── preload.js    — Context bridge for serial API
  └── package.json  — Electron + serialport dependencies
```

The RSA math runs entirely client-side using JavaScript BigInt.
No server, no API calls, no internet required.
