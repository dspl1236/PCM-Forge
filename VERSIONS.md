# PCM 3.1 hardware, software versions and features

Which software a PCM 3.1 can run depends on its hardware, and a few activation options depend on the software. This page lists both. The hardware and release tables come from the update definition files (`*.def`) on Porsche's 2015 update disc (`PCM_NA_20150721`). The feature table comes from the firmware itself (`PCM3Root` from each release) and from tests on real units.

## Find your hardware and software

- **Software version:** press **INFO** → **Option** → **Show System Version**. A PCM-Forge diagnostic stick also writes it to the log, under `=== PCM Version ===`.
- **Hardware ID:** the engineering menu's software download page (item 05) shows the unit's hardware ID, for example `PCMS02XX1221`. A diagnostic tester reads the build number (KWP `1A 95`, for example `0114181A`).

## Hardware

The hardware ID reads `PCM` + letter + generation + `XX` + date code, for example `PCMS02XX1221`.

| Part | Values | Meaning |
|------|--------|---------|
| Letter | `G`, `E`, `S`, `C` | Hardware variant. Each newer release accepts more letters: 1.35 takes only `G`; 2.47 takes `G`, `E`; 3.43 takes `G`, `E`, `S`; 4.76 takes `G`, `E`, `S`, `C`. |
| Generation | `01`, `02` | **The part that decides the software line.** `01` = original units, software 1.xx to 3.xx. `02` = facelift ("MOPF") units, software 4.xx. |
| Date code | `0828`/`0829`, `0919`/`0920`, `1220`/`1221` | Design year and week: 2008, 2009, 2012. `1220` is the units without a hard drive (the `LOW` software). |

## Which software each unit can take

The update disc picks the software by hardware ID. If a release has no entry for your ID, the disc has nothing to install on that unit.

| Hardware ID | Newest release on the disc | Version string |
|-------------|----------------------------|----------------|
| `PCMG01XX0828` | 1.35 (`PCM31_G1_V135`) | `Porsche_PCM3.1_128MB_VRam_VR_G1_17.6_14183AGI` |
| `PCMG01XX0829` | 2.47 (`PCM31_V247_RDW`) | `Porsche_PCM3.1_iPod1wire_VR_E2_12.8_14183AEN` |
| `PCMG01XX0919`/`0920`, `PCME01XX0919`/`0920` | 3.43 (`PCM31_V343_RDW`), also offered 2.47 | `Porsche_PCM3.1_iPod1wire_VR_9X1_13.4_14181A9K` |
| `PCMS01XX0919`/`0920` | 3.43 | as above |
| `PCM{C,E,G,S}02XX1221` | 4.76 (`PCM31MOPF_V476_RDW`) | `Porsche_PCM3.1_MOPF_SOP_STEP9.6_15245AS9` |
| `PCM{C,E,G,S}02XX1220` | 4.76 without hard drive (`PCM31MOPF_V476_LOW`) | build `15245B` |

- **No `01` unit can take 4.xx, and no `02` unit is offered 3.xx.** No hardware ID appears on both sides. Whether a `01` unit could physically run 4.xx has never been tested; no Porsche package tries it.
- **Same release, other markets:** China (`CHN`, with its own 1.51, 2.51 and 3.51 releases) and Arabic (`ARB`) have their own builds of each version. The feature tables below were read from the Rest of World builds.
- The version string's last part is the build: `15245A` is 4.76 Rest of World / North America, `15245B` LOW, `15245C` Arabic, `15245D` China.

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

## Activation codes

The activation code itself doesn't depend on the software: it is built from the VIN and the feature number the same way on every version. A code that works on 4.76 works on 3.43 for the same VIN and feature. What changes between versions is which features and options the software acts on.

Tested on real units so far:

| Unit | Software | Tested |
|------|----------|--------|
| 2016 Cayenne (958.2) | 4.76 (`15245A`) | Activation stick (PCM-Forge's main test car); diagnostic activation of Sport Chrono and a map region |
| Bench Cayenne PCM, `01` unit | 3.43 (`14181A`) | Diagnostic activation: Speller (0x010C), Sport Chrono; both kept across a power cycle |

If you run PCM-Forge on another version, please [open an issue](https://github.com/dspl1236/PCM-Forge/issues) with the diagnostic log so this table can grow.
