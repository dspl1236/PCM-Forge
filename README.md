# PCM-Forge

**Open-source activation code generator and toolkit for Porsche PCM 3.1 infotainment systems.**

🔓 **Algorithm fully cracked** — 64-bit RSA modular exponentiation, reverse-engineered from QNX firmware via Ghidra SH4 decompilation. Generate activation codes for any VIN, for free.

🌐 **Web tool:** [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/) — activation codes, USB stick builder, and modular diagnostic toolkit.

📋 **What can I activate?** → See [FEATURES.md](FEATURES.md) for the full list of 26 features with descriptions, retail costs, and hardware requirements.

## Supported Vehicles

All Porsche models with **PCM 3.1** (Harman Becker, SH4A QNX 6.3):

| Model | Years | Notes |
|-------|-------|-------|
| Cayenne (958) | 2011–2018 | Primary development target |
| Panamera (970) | 2011–2016 | Compatible |
| 911 (991.1) | 2012–2016 | Compatible |
| Boxster/Cayman (981) | 2013–2016 | Compatible |
| Macan (95B) | 2014–2018 | Compatible (pre-refresh) |

**Not compatible with:** PCM 3.0 (Cayenne 957, 997, 987 — older hardware, different activation algorithm), PCM 4 / MIB2 (991.2+, 718, Panamera 971, refreshed Macan — ARM platform, different architecture).

### Hardware Revisions & Firmware

PCM 3.1 has three hardware revisions. The update disc auto-detects your hardware and installs the correct version — it will not flash the wrong firmware.

| Hardware | Code | Max Firmware | Era | IOC |
|----------|------|-------------|-----|-----|
| Gen 1 "9600" | PCMG01XX | v2.47 | 2010–2012 | 9600 |
| Series 1 "9612" | PCMS01XX | v3.43 | 2012–2013 | 9612 |
| Series 2 "9633" | PCMS02XX | v4.76 | 2013–2018 | 9612 |

Check your version: press **INFO** → **Option** → **Show System Version**.

**Firmware update ISO (v4.76 / v3.43 / v2.47 — all in one):** [hausofdub.com/iso/PCM_NA_20150721.ISO](https://hausofdub.com/iso/PCM_NA_20150721.ISO) — burn to DVD-R (Verbatim recommended, 4x speed). North America region, also confirmed working on ROW units.

**PCM-Forge activation compatibility:** Tested and verified on PCMS02XX (v4.76). The RSA-64 algorithm is firmware-independent, but v2.47 and v3.43 are untested — if you're on older firmware and have issues, run the diagnostic USB and [open an issue](https://github.com/dspl1236/PCM-Forge/issues).

## Web App

The web app at [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/) has four tabs:

### Tab 1: Activation Codes
Enter your VIN → generates all 26 activation codes instantly. No server, no account, runs entirely in your browser.

### Tab 2: USB Stick Builder
Builds a ready-to-use USB stick with activation codes and optional diagnostic probe. The USB stick uses the same `copie_scr.sh` autorun mechanism as Audi MMI3G — `proc_scriptlauncher` runs the script automatically when the USB stick is inserted.

Includes an enhanced diagnostic mode that dumps 29+ system tests to the USB stick without modifying the car.

### Tab 3: Toolkit
Modular USB toolkit for PCM 3.1 diagnostics and utilities. Select modules and build a USB stick — each module is fetched from `modules/` at build time, so the list stays in sync with the repo:

| Module | Status | Description |
|--------|--------|-------------|
| **System Info** | ✅ Ready | Full PCM dump: version, VIN, mounts, processes, network, partitions, IPC, engineering screens |
| **Telnet Enabler** | ✅ Tested | Root shell — telnet (port 23) + raw ksh (2323). Session-only, re-run after reboot |
| **USB Ethernet** | ✅ Tested | Universal ASIX driver (AX88772 / 772A / 772B / 772C) with DHCP / static / LTE. Loads from USB, never touches flash |
| **IOC Probe** | ✅ Ready | Map IPC/CAN channels and discover the BAP instrument-cluster interface. Read-only |
| **BT / AUX Fix** | 🧪 Experimental | Stops the PCM defaulting to FM at startup — routes a connected phone to Bluetooth (A2DP). Self-locating runtime patch, reboot-reverts |
| **Service Reset** | 🧪 Alpha | Oil / service interval reset via UDS/BAP CAN. No PIWIS needed |
| **LTE Setup** | ⚠️ Deprecated | Superseded by USB Ethernet (which includes an LTE mode) |

### Tab 4: Backup
Upload the `PagSWAct_backup.002` that Diagnostic mode pulls off the PCM to see exactly what's currently activated, then add features on top and download a **merged** `PagSWAct.002` — so you keep every existing activation instead of overwriting them.

## Data Connectivity & LTE Restoration

The PCM 3.1's built-in **Cinterion AC75i** modem (2G GPRS/EDGE) is dead after the 2G/3G network shutdown (US 2022, EU ongoing). Internet can be restored via USB ethernet:

```
USB port → AX88772 adapter → LTE router → internet
Driver: devn-asix.so (already in PCM firmware)
Interface: en5 (same as Audi MMI3G+)
```

**Compatible chipsets:** ASIX AX88772, AX88772A, AX88772B. The AX88772D is not auto-detected but works with a device ID override: `io-pkt-v4-hc -d asix did=0x772D,vid=0x0B95` ([QNX documentation](https://qnx.com/developers/docs/6.4.0/neutrino/utilities/d/devn-asix.so.html)).

See [research/PCM31_CONNECTIVITY.md](research/PCM31_CONNECTIVITY.md) for the full LTE restoration guide including hardware list, network architecture, and what online services may still work.

## ⚡ Quick Start

> **Important:** Always use the [web app](https://dspl1236.github.io/PCM-Forge/) to build your USB stick. Do NOT download `copie_scr.sh` directly from GitHub — the PCM requires a special XOR-encoded version that only the web app generates. Raw files from the repo will not trigger the autorun.

### Step 1: Run Diagnostics First
1. Open [dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/)
2. Go to the **USB Stick** tab
3. Enter your 17-digit VIN
4. Leave **Diagnostic mode** checked (default)
5. Click **Save to folder** → select your FAT32 USB drive
6. Insert USB **after the PCM has fully booted** (wait for the home screen — do NOT insert before starting the car), wait 60–90 seconds
7. Remove USB — check for `pcm_debug.log` and `pcm_dump/` folder on the drive

### Step 2: Activate Features
1. Review your diagnostic results to see what's currently active
2. Go back to the **USB Stick** tab
3. Uncheck Diagnostic mode
4. Click **Select all** to keep all existing features (or pick individual ones)
5. Click **Save to folder** → select your FAT32 USB drive
6. Insert USB after PCM has booted, wait 60–90 seconds, remove, hard reboot (hold **INFO + CAR** until screen goes black)

⚠️ The activation file (`PagSWAct.002`) **replaces all existing activations**. Only the features you select will be active — anything not selected gets deactivated. Always use **Select all** and then add new features on top.

### Step 3: Verify
Press **SOURCE + SOUND** simultaneously — if the ENGINEERING feature is activated, the hidden engineering menu will appear. This confirms your activation codes are working.

### Just Need Codes? (for PIWIS / manual entry)
Use the **Codes** tab — enter your VIN, get all 26 activation codes instantly. No USB stick needed — enter codes manually via PIWIS or the engineering menu.

## Replacement / Used PCMs

If you installed a used PCM from another car, activation codes won't work because the PCM validates against its internally stored VIN (the donor car's VIN). Fix this with PCM-Forge alone — no dealer needed:

1. Run **Diagnostic Mode** via USB to pull the donor VIN from the PCM
2. Enter the donor VIN in PCM-Forge and activate **ENGINEERING** (GEM)
3. In the Engineering menu, update the VIN to your car's VIN (under SW Activations)
4. Re-run PCM-Forge with your real VIN to activate all features

## How It Works

### Activation Algorithm
The PCM 3.1 uses a 64-bit RSA scheme to validate activation codes:

```
VIN → 8-position extraction → weighted sum → mod 2^16
Feature SWID + SubID → 4-byte record key
Record key → RSA encrypt with private key → 8-byte activation code
PCM verifies: RSA decrypt with public key → matches record key
```

The RSA keys (N, E, D) were extracted from `CPPorscheEncrypter::verify` in the QNX firmware binary via Ghidra SH4 decompilation. The 64-bit key size makes factorization trivial — the private exponent was recovered in seconds.

### Script Execution
The PCM 3.1 uses the same autorun mechanism as Audi MMI3G: `proc_scriptlauncher` monitors the USB port for `copie_scr.sh`, which is XOR-encoded with a known PRNG seed. The web app handles encoding automatically.

## Platform Architecture

PCM 3.1 shares the Harman Becker HN+ platform with Audi MMI3G+ and VW RNS-850:

| Component | Details |
|-----------|---------|
| CPU | Renesas SH4A (SH7786/SH7785) |
| OS | QNX 6.3.2 (PSP3) |
| Application | `PCM3Root` (native C++ binary, ~6MB) |
| IOC | Renesas V850 with CMX-RTX RTOS |
| Display | 7" touchscreen, 800×480 |
| Storage | Internal SATA HDD |
| Modem | Cinterion AC75i (2G, dead after network shutdown) |
| USB ethernet | `devn-asix.so` (ASIX AX88772) in firmware |
| Autorun | `proc_scriptlauncher` + `copie_scr.sh` via USB |

Note: Unlike Audi MMI3G+ which uses Java/J9 for the UI, PCM 3.1 uses a native C++ application (`PCM3Root`). The IFS images use LZO1X compression inside Harman's `hbcifs` container — decompressible back to a standard QNX IFS with the repo's tooling.

## Project Structure

```
PCM-Forge/
├── docs/                        # GitHub Pages site
│   ├── index.html               #   Web app (Activation, USB Stick, Toolkit, Backup)
│   └── app/manifest.json        #   Auto-generated module index (built from modules/)
├── modules/                     # Toolkit modules — each a self-contained USB tool
│   ├── bt-aux-fix/              #   FM->A2DP boot fix (module.json + scripts/ + bin/)
│   ├── usb-net/                 #   universal ASIX USB-ethernet
│   └── sysinfo/ telnet/ ioc-probe/ service-reset/ lte-setup/
├── builder/generate_manifest.py # Regenerates docs/app/manifest.json from modules/
├── core/                        # Shared assets (copie_scr.sh, showScreen, status PNGs)
├── research/                    # 30+ reverse engineering docs (+ firmware/ Ghidra output)
│   ├── ALGORITHM_CRACKED.md     #   RSA-64 key recovery
│   ├── DISCOVERY_NARRATIVE.md   #   Full RE story
│   └── PCM31_CONNECTIVITY.md    #   LTE restoration guide
├── tools/                       # Firmware analysis utilities
├── generate_codes.py            # CLI activation-code generator
└── FEATURES.md                  # Feature quick reference
```

## Research Highlights

- **64-bit RSA cracked** from QNX SH4 firmware via Ghidra decompilation
- **26 features mapped** with retail costs ($150–$3,500 each)
- **USB autorun mechanism** identical to Audi MMI3G+ (`proc_scriptlauncher`)
- **V850 IOC** reverse engineered (CMX-RTX RTOS, CAN gateway)
- **LTE restoration path** confirmed — `devn-asix.so` driver present in firmware
- **AX88772D workaround** — QNX driver supports USB device ID override
- **Universal BT/AUX boot fix** — a single signature-located byte patch to live `PCM3Root` routes Bluetooth to A2DP instead of FM; **validated across 31 firmware builds** (every region/model, v2.00+). Builds on [WillCoder's research](https://github.com/WillCoder/PCM_31_AUX-BT); full writeup in [research/BT_AUX_BOOT_FIX.md](research/BT_AUX_BOOT_FIX.md)
- **PCM 3.0 vs 3.1** — different hardware generations, tools are PCM 3.1 only

## Related Projects

- **[MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit)** — Sister project for Audi MMI 3G/3G+ and VW RNS-850. Same Harman Becker platform, SD card delivery. Includes Google Earth restoration, 20+ modules, complete firmware reverse engineering.
- **[DrGER2/MMI3GP-LAN-Setup](https://github.com/DrGER2/MMI3GP-LAN-Setup)** — Original Audi LTE setup method (same adapter works on PCM 3.1)
- **[WillCoder/PCM_31_AUX-BT](https://github.com/WillCoder/PCM_31_AUX-BT)** — Found the BT/AUX boot fix and the `/proc/as` runtime-patch method that the **BT / AUX Fix** module builds on

## Disclaimer

PCM-Forge modifies your PCM 3.1 head unit. The activation tool rewrites `PagSWAct.002` (the original is backed up automatically). The toolkit modules go further — for example **BT / AUX Fix** patches the running `PCM3Root` in memory, **Telnet** opens a root shell, and **USB Ethernet** loads a network driver. All of it is designed to be **brick-safe**: everything runs from USB or a live `/proc` / `/HBpersistence` patch, nothing modifies the read-only firmware, and a reboot reverts runtime changes. Still, **use at your own risk**. This project is not affiliated with Porsche, Volkswagen Group, or Harman Becker.

## License

MIT
