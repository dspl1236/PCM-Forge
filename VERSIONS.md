# PCM 3.1 hardware, software versions and features

Which software a PCM 3.1 can run depends on its hardware, and which features work depends on the software. This page covers hardware IDs, software limits, hard drives, the phone and activations. The hardware and release tables come from the update definition files (`*.def`) on Porsche's 2015 update disc (`PCM_NA_20150721`). The feature table comes from the firmware itself (`PCM3Root` from each release) and from tests on real units.

## Find your hardware and software

- **Software version:** press **INFO** → **Option** → **Show System Version**. A PCM-Forge diagnostic stick also writes it to the log, under `=== PCM Version ===`.
- **Hardware ID:** the engineering menu's software download page (item 05) shows the unit's hardware ID, for example `PCMS02XX1221`. A diagnostic tester reads the build number (KWP `1A 95`, for example `0114181A`).

## Hardware

The hardware ID reads `PCM` + letter + generation + `XX` + date code, for example `PCMS02XX1221`.

| Part | Values | Meaning |
|------|--------|---------|
| Generation | `01`, `02` | **This decides the software line.** `01` = original units, software 1.xx to 3.xx. `02` = later ("MOPF") units, software 4.xx. |
| Letter | `G`, `E`, `S`, `C` | Hardware variant: which I/O controller chip and which firmware build the unit gets (table below). |
| Date code | `0828`/`0829`, `0919`/`0920`, `1220`/`1221` | Design year and week: 2008, 2009, 2012. On `02` units, `1220` = no hard drive, `1221` = with hard drive. |

What the update disc installs for each letter:

| Hardware | I/O controller | Firmware build |
|----------|----------------|----------------|
| `G01` | 9600 | standard |
| `E01` | 9608 | standard |
| `S01` | 9612 | `9x1` |
| `G02` | 9600 | MOPF |
| `E02` | 9612 | MOPF |
| `S02` | 9612 | MOPF `9x1` |
| `C02` | 9612 | MOPF `Macan` |

The firmware file names suggest the models: `Macan` for the Macan, and `9x1` most likely for the 991 and 981 (911, Boxster, Cayman). The disc doesn't say which car uses `G` or `E`.

## Which software each unit can take

The update disc picks the software by hardware ID. If a release has no entry for your ID, the disc has nothing to install on that unit, so these are hard limits.

| Hardware ID | 1.35 | 1.51 (China) | 2.47 | 2.51 (China) | 3.43 | 3.51 (China) | 4.76 | Newest |
|-------------|:----:|:----:|:----:|:----:|:----:|:----:|:----:|--------|
| `PCMG01XX0828` | China build | yes | | | | | | **1.35 / 1.51** |
| `PCMG01XX0829` | yes | yes | | | | | | **1.35** |
| `PCMG01XX0919` / `0920` | | | yes | yes | yes | yes | | **3.43** |
| `PCME01XX0919` / `0920` | | | yes | yes | yes | yes | | **3.43** |
| `PCMS01XX0919` / `0920` | | | | | yes | yes | | **3.43** |
| `PCM{G,E,S,C}02XX1221` | | | | | | | yes | **4.76** |
| `PCM{G,E,S,C}02XX1220` | | | | | | | LOW build | **4.76** (no hard drive) |

- **The 2008 units stop at 1.35.** `PCMG01XX0828` installs from the disc's China folder and `0829` from the Rest of World folder.
- **No `01` unit can take 4.xx, and no `02` unit is offered anything older.** No hardware ID appears on both sides. Besides the hardware ID, 4.76 also dropped the older FPGA board revision and the 64 MB video-RAM units that 1.xx to 3.xx still supported.
- **Earlier releases exist in each line** (4.63, for example); the 2015 disc carries only the last one of each.
- **Other markets:** China (`CHN`) and Arabic (`ARB`) get their own builds of each version. The feature tables below were read from the Rest of World builds.
- **Version strings:** `Porsche_PCM3.1_MOPF_SOP_STEP9.6_15245AS9` is 4.76. The build is the `15245A` part: `A` Rest of World / North America, `B` LOW, `C` Arabic, `D` China. 3.43 is build `14181`.

## Hard drive

| | 40 GB drive | 100 GB drive |
|-|-------------|--------------|
| Found in | early units (about 2011-2012) | later units (about 2013-2016) |
| Partitions | 3: system, data, maps | 4: system, data, maps, and a 42 GB jukebox |
| Jukebox (music on the PCM) | no | yes, needs 4.xx |

- **The jukebox needs 4.xx software.** Versions 1.xx to 3.xx have no code to use a media partition, so a bigger drive in a `01` unit won't add one.
- **Filesystems:** 1.xx and 2.xx use only QNX4 filesystems; QNX6 support starts with 3.xx. A drive from a newer unit may not read on an older one.
- **Units ending `1220`** have no hard drive at all: the `LOW` software keeps everything in flash.
- **Maps are not on the software update disc.** They come from a separate navigation disc. 4.76 expects map data version 4 to 6. If you put in a blank drive or SSD and run only the software update, everything works except navigation ("loading maps"). Install the maps from the navigation disc too.

**Swapping in an SSD:**
- The drive runs as the **slave** on its IDE channel (the DVD drive is the master). The SATA-to-IDE adapter must be set to slave. A master-only adapter just isn't found; nothing breaks.
- The PCM runs the channel at MDMA2 / PIO4, not UDMA, so the adapter has to work in those modes.
- **Stay at 128 GB or below.** Nothing larger than the stock 100 GB has been checked. Above 137 GB, the old 28-bit addressing limit would make writes wrap round to the start of the disk without warning.

## Features by software version

Which activations each version's firmware acts on, read from its `PCM3Root` (the activation handler's SWID list). "yes" means the software handles the activation. It doesn't mean every car has the hardware for it (DAB, HD Radio and satellite radio need their tuners).

| Feature (SWID) | 1.35 | 2.47 | 3.43 | 4.76 |
|----------------|:----:|:----:|:----:|:----:|
| Navigation, Off-road navigation, Logbook, Voice control, Sport Chrono, Compass, Video in Motion, Satellite radio, USB media, Bluetooth phone, Engineering menu, Speller, Individual memory, Feature level (0x0101-0x010E) | yes | yes | yes | yes |
| HD Radio tuner (0x010F) | no | no | yes | yes |
| DAB digital radio (0x0110) | no | no | no | yes |
| Online services (0x0111) | no | no | no | yes |
| Maps: Europe, North America, South Africa, Middle East, Australia, Asia Pacific, Russia, South America, China (0x2001-0x2009) | yes | yes | yes | yes |
| Maps: Chile, Argentina (0x200A, 0x200B) | no | no | no | yes |
| **Total** | **23** | **23** | **24** | **28** |

A version that doesn't know an activation skips its record and logs "no valid SWID found". So a stick with all 28 works on an older unit too: the ones that version doesn't know just stay inactive.

### Feature options by version

| Option | 1.35 | 2.47 | 3.43 | 4.76 |
|--------|:----:|:----:|:----:|:----:|
| Video in Motion speed limit (never / 9 / 5 / 0 km/h / handbrake) | yes | yes | yes | yes |
| Speller speed limit (same choices) | yes | yes | yes | yes |
| Voice control: Siri on/off | no | no | no | yes |
| Online services: Google/Bing search | no | no | no | yes |

On 1.xx-3.xx the Siri option has no effect: voice control activates the same either way. The speed-limit values are the same in every version.

Evidence: the activation dispatch in each `PCM3Root` (1.35 at `0x822c4fc`, 2.47 `0x823e9ea`, 3.43 `0x8248ac6`, 4.76 `0x826b090`) and the handlers' own log strings. The 2.47 speed-limit handling is read from the same compare values as 1.35 and 3.43, not traced step by step.

## Phone (hands-free)

The phone needs more than an activation. All of these have to be in place:

1. **Activation: BTH (0x010A), "Bluetooth Handyvorbereitung"** (Bluetooth phone). It exists on every version. The entry PCM-Forge used to call "TEL" (0x0102) is Off-road Navigation and does nothing for the phone.
2. **Coding**, set with PIWIS or another diagnostic tool. In Porsche's diagnostic data:
   - **Bluetooth:** `On`
   - **Telefon Einstellungen → Telefonmodulaktivierung** (phone module): `Yes`
   - **Mikrofon → Anzahl** (number of microphones): not `keines` (none)
3. **A microphone wired to the PCM.** Without one, calls can't work even when everything else is set.

On a used PCM from another car, a phone screen that says "unavailable" most likely means one of these is missing. Voice control (SSS, 0x0104) is a separate activation and also uses the microphone.

## Activation codes

The activation code itself doesn't depend on the software: it is built from the VIN and the feature number the same way on every version. A code that works on 4.76 works on 3.43 for the same VIN and feature. What changes between versions is which features and options the software acts on.

Tested on real units so far:

| Unit | Software | Tested |
|------|----------|--------|
| 2016 Cayenne (958.2) | 4.76 (`15245A`) | Activation stick (PCM-Forge's main test car); diagnostic activation of Sport Chrono and a map region |
| Bench Cayenne PCM, `01` unit | 3.43 (`14181A`) | Diagnostic activation: Speller (0x010C), Sport Chrono; both kept across a power cycle |

If you run PCM-Forge on another version, please [open an issue](https://github.com/dspl1236/PCM-Forge/issues) with the diagnostic log so this table can grow.
