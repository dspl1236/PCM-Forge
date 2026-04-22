# PCM 3.1 Data Connectivity & LTE Restoration

## Overview

The Porsche PCM 3.1 shares the Harman-Becker HN+ platform with Audi
MMI3G+ and VW RNS-850. All three use the same SH4A QNX 6.3 core. The
connectivity hardware and software are closely related, meaning the
LTE restoration path proven on Audi MMI3G+ applies to PCM3.1 as well.

## Original Connectivity: Cinterion AC75i (3G UMTS)

### Hardware

The PCM 3.1 includes a **Cinterion AC75i** cellular modem (formerly
Siemens Wireless Modules). This is the NAD (Network Access Device):

| Component | Details |
|-----------|---------|
| Modem chip | Cinterion AC75i |
| Bands | GSM 850/900/1800/1900 + UMTS 850/1900/2100 |
| Data | HSDPA 3.6 Mbps down, HSUPA 2.0 Mbps up |
| SIM slot | Mini-SIM (2FF), accessible inside head unit |
| Firmware | `ac75ip_rev01100_a-rev04.001.09.usf` (3.2MB) |
| Alternate FW | `v02-003.usf` (3.6MB, shared with Audi NAD) |
| Signature | `PHON01AC75I1.sig` |

### Software Stack

```
PCM3.1 Modem Software Stack:

  npm-pppmgr.so    — PPP connection manager (QNX network plugin)
  pppd             — PPP daemon (serial-to-IP over modem)
  MuxBtNad         — Multiplexer sharing serial port between
                     Bluetooth and NAD (modem) functions
  SIM management   — PIN handling, SIM state machine
```

The modem connects via PPP (Point-to-Point Protocol) — the QNX system
dials out over the cellular modem's serial interface, establishes a PPP
link, and routes IP traffic through the resulting `ppp0` interface.

### Online Services (Original)

When the 3G modem was functional, PCM 3.1 provided:

| Service | Provider | Status |
|---------|----------|--------|
| AHARadio | Aha / Harman | Streaming radio |
| Weather | Baron Services, Inc. | Current conditions + forecast |
| Traffic | Inrix (probable) | Real-time traffic overlay |
| Google Search | Google | POI/destination search |

**NOT included:** Google Earth, Google StreetView. Porsche chose not
to implement GEMMI (Google Earth for MMI) on the PCM 3.1 platform.

### Current Status: DEAD

The 3G (UMTS/HSPA) cellular networks have been shut down:
- **US**: AT&T 3G sunset February 2022, T-Mobile July 2022
- **EU**: Ongoing phase-out, varies by country (2025-2028)

The Cinterion AC75i cannot connect to any active network. The SIM
card slot is physically present but the modem has no network to
connect to. All online services are permanently offline.

## Restoration Path: USB Ethernet + LTE Router

### Why It Works

The PCM 3.1 IFS contains **`devn-asix.so`** — the same ASIX USB
ethernet driver found in the Audi MMI3G+. This driver loads when a
compatible USB ethernet adapter is connected to the PCM's USB port.

```
PCM3.1 IFS contains:
  devn-asix.so    — ASIX AX88772 USB ethernet driver
  npm-pppmgr.so   — PPP manager (also handles DHCP routing)
  dhcp.cli        — DHCP client
  en5             — Network interface (Ethernet over USB)
```

### Required Hardware

| Part | Model | Notes |
|------|-------|-------|
| **USB Ethernet adapter** | D-Link DUB-E100 (rev A4/B1) | Must use **ASIX AX88772/A/B** chipset. AX88772D is NOT supported |
| **USB extension cable** | USB-A male to USB-A female | Route from PCM's USB port to the trunk/glovebox |
| **LTE router** | TP-Link TL-MR3020 or similar | Any router serving DHCP on 192.168.0.x |
| **LTE SIM card** | Any data-only plan | 1-2 GB/month typical usage |
| **12V→5V converter** | USB car charger / buck converter | Power the router from vehicle 12V |

**Estimated cost:** $100-150 for all parts.

### Compatible USB Ethernet Chipsets

| Chipset | Status | Notes |
|---------|--------|-------|
| ASIX AX88772 | ✅ Works | Original D-Link DUB-E100 |
| ASIX AX88772A | ✅ Works | Updated revision |
| ASIX AX88772B | ✅ Works | Further revision |
| ASIX AX88772D | ❌ Fails | Different USB product ID, driver doesn't recognize it |
| ASIX AX88178 | ✅ Works | Gigabit variant (overkill but compatible) |
| Realtek RTL8152 | ❌ No driver | No QNX driver in PCM3.1 IFS |

### Network Architecture

```
ORIGINAL (dead):
  SIM → Cinterion AC75i → PPP → ppp0 → internet
                                    ↓
                              Online services

RESTORED:
  USB port → AX88772 adapter → LTE router → internet
              ↓                    ↓
         devn-asix.so         4G/LTE cellular
              ↓
         en5 interface
              ↓
         DHCP client
              ↓
         IP connectivity
              ↓
         Online services
```

### PCM3.1 USB Port Location

The PCM 3.1 USB port is typically located in the center console
(Cayenne 958) or center armrest (911 991, Boxster/Cayman 981).
An AMI/MDI-to-USB adapter may be needed depending on the model.

**Note:** Unlike the Audi MMI3G+ which has dedicated AMI ports,
some PCM 3.1 installations expose a standard USB-A port directly.
Check your specific vehicle.

## Differences from Audi MMI3G+ LTE Setup

| Aspect | Audi MMI3G+ | Porsche PCM 3.1 |
|--------|-------------|-----------------|
| Original modem | Telit UC864-AWS-AUTO | Cinterion AC75i |
| USB ethernet driver | `devn-asix.so` ✅ | `devn-asix.so` ✅ |
| Network interface | `en5` | `en5` |
| DHCP client | ✅ Present | ✅ Present |
| USB port | AMI connector | USB-A (model dependent) |
| Online services | Audi Connect (GE, weather, traffic, POI) | AHARadio, weather, traffic |
| Google Earth | GEMMI (can be restored) | Never implemented |
| copie_scr.sh | SD card autorun | USB stick autorun |
| Setup script delivery | SD card | USB stick |
| IFS format | Standard QNX IFS (LZO compressed) | Harman custom IFS (`hbcifs`) |

### Key Implication

The DrGER2 LTE setup method (MMI3GP-LAN-Setup) should work on
PCM 3.1 with minor adaptation. The core mechanism is identical:

1. `devn-asix.so` loads when USB ethernet adapter is connected
2. QNX creates `en5` network interface
3. DHCP client requests IP from LTE router
4. IP traffic routes through the LTE router to the internet
5. Online services detect connectivity and resume

The main adaptation needed is delivery mechanism: USB stick
instead of SD card for the setup script.

## What Gets Restored

With LTE connectivity restored, PCM 3.1 should regain:

| Service | Likely Status | Notes |
|---------|--------------|-------|
| Weather | ⚠️ Depends | Baron Services API may have changed |
| Traffic | ⚠️ Depends | Inrix API endpoints may have changed |
| Google Search | ⚠️ Depends | Google API may require auth updates |
| AHARadio | ❌ Likely dead | Aha service was acquired/shut down |

**Important:** Having internet connectivity doesn't guarantee all
services will work. The service providers may have changed their
APIs, endpoints, or authentication since the 3G era. Testing is
needed to determine which services still function.

## What Will NOT Work

| Feature | Reason |
|---------|--------|
| Google Earth | Never implemented on PCM 3.1 (no GEMMI) |
| Porsche Connect (modern) | Requires PCM 4.0+ / MIB2 platform |
| Apple CarPlay | Hardware doesn't support it (PCM 4.0+) |
| Android Auto | Hardware doesn't support it (PCM 4.0+) |

## Google Earth on PCM 3.1?

### Short Answer: Not Practical

Google Earth was implemented as GEMMI (Google Earth for MMI) on the
Audi/VW variants of the HN+ platform. The PCM 3.1 firmware contains
**zero** GEMMI infrastructure:

- No `gemmi_final` binary
- No `libembeddedearth.so`
- No `drivers.ini` connection config
- No `run_gemmi.sh` launch script
- No `lsd.jxe` with GEMMI integration hooks
- No EOLFLAG_GOOGLE_EARTH
- No `/mnt/nav/gemmi/` deployment path
- No kh.google.com or tile server references

### Theoretical Path (Major Research Project)

The GEMMI binaries from the Audi MMI3G+ are SH4 QNX executables
that would technically run on the PCM 3.1's identical CPU. However:

1. PCM 3.1's main application (`PCM3Root`, 5.8MB native C++ binary)
   is completely different from Audi's `MMI3GApplication` (Java-based)
2. The display/rendering integration hooks don't exist
3. GEMMI expects to be launched by `lsd.jxe` which PCM 3.1 doesn't have
4. The map overlay system is different between Audi and Porsche

Making Google Earth work on PCM 3.1 would require reverse engineering
the PCM3Root application to add GEMMI rendering hooks — a project
orders of magnitude larger than the Audi restoration path.

## Firmware Analysis Details

### PCM 3.1 IFS Structure

The PCM 3.1 uses a different IFS container from the Audi:

```
Audi MMI3G+:  Standard QNX IFS (0x00FF7EEB magic)
              LZO1X compressed at container level
              Our inflate_ifs.py decompresses it

PCM 3.1:     Harman custom IFS ("hbcifs" magic)
              Not compressed (pass-through)
              Our inflate_ifs.py can't extract file tree
              Need custom extractor for "hbcifs" format
```

### PCM 3.1 Update Format

```
Audi:    metainfo2.txt → SWDL system → component sections
PCM 3.1: .def files → HBUPDATE.def → module sections
         DISCID, SYSTEMRELEASEID, MODULETYPE, CRCFILE
```

### Hardware Variants in Firmware

The PCM 3.1 update ISO contains firmware for multiple Porsche models:

| Prefix | Vehicle | Notes |
|--------|---------|-------|
| PCMC | Cayenne (958) | Standard Cayenne |
| PCME | E-Hybrid (958) | Andrew's car |
| PCMG | GTS / GT | Performance variants |
| PCMS | S model | Cayenne S, 911 S, etc. |
| 9x1 | 911/Boxster | 991/981 platform |

All share the same IFS2 (main firmware) but have different IFS1
(startup) and IOC (V850) firmware for hardware-specific configuration.

## Next Steps

1. **Acquire AX88772/A/B USB ethernet adapter** (same one ordered
   for the Audi A6 — works on both cars!)
2. **Test basic connectivity** — plug adapter into PCM USB port,
   connect to LTE router, check if `en5` interface comes up
3. **Verify DHCP** — does the PCM request and receive an IP address?
4. **Test online services** — which services still respond?
5. **Build USB setup script** — adapt MMI3G-Toolkit's `lte-setup`
   module for USB delivery instead of SD card
6. **Research `hbcifs` format** — extract PCM3.1 IFS to find
   network startup scripts and modem configuration
7. **Community sharing** — post findings to Rennlist PCM 3.1 thread

## References

- `research/PCM31_RESEARCH.md` — PCM 3.1 platform architecture
- `research/PCM31_SYSTEM_INFO.md` — Andrew's Cayenne system details
- `research/USB_ENGINEERING_ACCESS.md` — USB autorun mechanism
- MMI3G-Toolkit `research/DATA_CONNECTIVITY_OPTIONS.md` — Audi LTE setup
- MMI3G-Toolkit `research/CUSTOM_DRIVER_INJECTION.md` — Driver loading methods
- [DrGER2/MMI3GP-LAN-Setup](https://github.com/DrGER2/MMI3GP-LAN-Setup) — Original Audi LTE method
