# GEM (Green Engineering Menu) — Deep Dive

## Overview
GEM is Harman's built-in engineering/diagnostic menu for PCM head units.
It renders ESD (Engineering Screen Definition) files as interactive
screens with buttons, sliders, key-value displays, and script execution.

## PCM 3.1 GEM Access (Andrew's Cayenne 958)

### Prerequisites
1. ENGINEERING activation code installed (SWID 0x010b)
2. `/HBpersistence/DBGModeActive` file exists
3. Both are handled by PCM-Forge USB activation

### Button Combo
- **Hold both rotary knobs** simultaneously for ~5 seconds
- OR **Tuner + Info** button combination
- OR **Source + Sound** combo (firmware-dependent)
- Some FW: **CAR + TUNER** for 5 seconds (PCM4 style)
- GEM shows green text "starting up" when activating

### Navigation
- Rotary knob scrolls through menu items
- Press knob to select/execute
- Roll to `..` and press to go back
- Back button also works

## ESD File Format

### Location
```
/HBpersistence/engdefs/    ← WRITABLE — custom screens go here
/mnt/ifs1/engdefs/          ← Read-only IFS (factory screens)
/mnt/flash/efs1/engdefs/    ← Flash filesystem
```

PCM3Root scans these directories on GEM launch and builds the menu.
Custom ESDs in `/HBpersistence/engdefs/` appear alongside factory ones.

### Syntax
```
# Comment lines start with #
screen <ScreenName> <Category>

# Categories: Car, Nav, System, Media, Phone, etc.
# Category determines which submenu the screen appears in

# === Widget Types ===

# Button — toggles a persistence value
button
   value    per 3 <address> "<value>"
   label    "Button Label"

# Choice — checkbox/toggle for persistence
choice
   value    per 3 <address>
   label    "Choice Label"

# Key-Value — displays a live value
keyValue
   value    int per 3 <address>
   label    "Display Label:"
   poll     <milliseconds>     # refresh interval

# Script — executes a shell command
script
   value    sys 1 0x0100 "<command>"
   label    "Button Label"

# Slider — adjusts a numeric value
slider
   value    int per 3 <address>
   label    "Slider Label"
   min      <min_value>
   max      <max_value>
```

### Command Types

#### `per 3 <address>` — Persistence Read/Write
- `per` = persistence storage access
- `3` = data type (3 = integer, 30 = other format on PCM4)
- `<address>` = hex persistence address (e.g., `0x0010001F`)
- PCM3Root maps these to internal CVALUE/persistence storage
- Some addresses map to CAN data (cluster, gateway, etc.)

#### `sys 1 0x0100 "<command>"` — Shell Script Execution
- `sys 1` = system command type
- `0x0100` = command class (script execution)
- `<command>` = full path to shell script
- Script runs as root on the PCM
- Output may be captured (firmware-dependent)

### Known PCM 3.1 Persistence Addresses
| Address | Purpose | Source |
|---------|---------|--------|
| 0x0010001F | Service interval coded | CarDeviceList.esd |
| 0x0014004E | Service protocol coded | CarDeviceList.esd |
| 0x00100033 | Oil level gauge coded | CarDeviceList.esd |
| 0x0014007D | Oil level protocol | CarDeviceList.esd |
| 0x00150000-3 | Cluster CAN data probes | Investigation needed |
| 0x00160000-1 | Cluster CAN data probes | Investigation needed |

### Factory ESD Files (from earlier research)
| File | Size | Location |
|------|------|----------|
| CarDeviceList.esd | ~2KB | EFS engdefs |
| CarProtocollSwitch.esd | ~2KB | EFS engdefs |
| (others TBD) | | Needs ls /mnt/ifs1/engdefs/ |

## Creating Custom GEM Screens

### Deployment
1. Create `.esd` file following the syntax above
2. Copy to `/HBpersistence/engdefs/` via USB or telnet
3. Restart GEM (exit and re-enter)
4. Custom screen appears in the appropriate category

### Our Service Reset Screens
- `ServiceReset.esd` — Buttons to trigger oil/inspection reset
- `ServiceStatus.esd` — Live display of service interval data

### Deployment Script
```bash
# Deploy ESD screens from USB
cp /fs/usb0/engdefs/*.esd /HBpersistence/engdefs/
chmod 644 /HBpersistence/engdefs/*.esd
```

## PCM 3.1 vs PCM 4/MHI2 GEM Differences

| Feature | PCM 3.1 (QNX) | PCM 4/MHI2 (Linux) |
|---------|---------------|-------------------|
| OS | QNX 6.3.2 | Linux |
| ESD location | /HBpersistence/engdefs/ | /eso/hmi/engdefs/ |
| Persistence | `per 3 <addr>` | `per 30 <addr>` |
| Script exec | `sys 1 0x0100 "cmd"` | Similar |
| Button combo | Rotary knobs / Tuner+Info | CAR + TUNER |
| MIB tool | Not applicable | SD card based |
| FEC system | PagSWAct.002 + VIN codes | FecContainer.fec + RSA |

## Key Questions for Investigation

### From PuTTY (when car is on):
```bash
# List all factory ESD files
ls -la /mnt/ifs1/engdefs/ /mnt/flash/efs1/engdefs/ 2>/dev/null

# List custom ESD files
ls -la /HBpersistence/engdefs/ 2>/dev/null

# Read factory CarDeviceList.esd
cat /mnt/ifs1/engdefs/CarDeviceList.esd 2>/dev/null
cat /mnt/flash/efs1/engdefs/CarDeviceList.esd 2>/dev/null

# Check if DBGModeActive exists
ls -la /HBpersistence/DBGModeActive

# Find ALL esd files
/mnt/data/tools/find / -name "*.esd" 2>/dev/null
```

### Critical: Can GEM scripts run uds_send?
If `sys 1 0x0100` can execute our `/tmp/uds_send`, we can add
oil reset buttons to GEM that work from the touchscreen:
```
screen ServiceReset Car

script
   value    sys 1 0x0100 "/tmp/uds_send_reset.sh"
   label    ">> RESET OIL SERVICE <<"
```

This would be the ultimate goal: oil reset from the PCM touchscreen
via the engineering menu, no PIWIS needed.

## Display Architecture Connection
The GEM is rendered by PCM3Root itself — it's not a separate process.
When GEM is active, PCM3Root draws the green engineering screens
using its own display connection (via layermanagerV2). This means:
1. GEM has full display access (no showScreen needed)
2. GEM scripts run with PCM3Root's permissions (root)
3. GEM can access all CAN/IOC/NDR interfaces
4. `per 3` reads happen through PCM3Root's internal data path

The `showScreen` binary is a SEPARATE tool for displaying PNGs
during USB script execution (outside of GEM context). For GEM
screens, the display is handled entirely by PCM3Root's GUI engine.
