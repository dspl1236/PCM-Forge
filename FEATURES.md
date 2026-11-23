# What PCM-Forge Can Activate

All 28 features the Porsche PCM 3.1 can unlock and what each one actually does in the car.

**TL;DR:** If your PCM is PCM 3.1 hardware (Cayenne 958, 911 991.1, Panamera 970, Boxster/Cayman 981, Macan 95B), PCM-Forge can generate a permanent activation code for any of these features. Whether the feature then works depends on whether the physical hardware is present in the car — see the "Hardware required" column.

## Quick Reference

| # | Feature | SWID | Hardware needed? |
|---|---------|------|------------------|
| 1 | FeatureLevel | 0x010e | None — software-only |
| 2 | Navigation | 0x0101 | GPS antenna usually already present |
| 3 | Voice Control (SSS) | 0x0104 | Microphone already in car |
| 4 | Sport Chrono | 0x0105 | Dashboard button + cluster firmware |
| 5 | Bluetooth Telephony (BTH) | 0x010a | Bluetooth module present stock |
| 6 | USB Media Support (UMS) | 0x0109 | USB port present stock |
| 7 | Video in Motion (TVINF) | 0x0107 | Unofficial — dealer won't sell |
| 8 | Satellite Radio (SDARS) | 0x0108 | SiriusXM tuner (US-spec cars) |
| 9 | HD Radio Tuner | 0x010f | HD Radio tuner (US-spec cars) |
| 10 | DAB Digital Radio | 0x0110 | DAB tuner (EU-spec cars) |
| 11 | Online Services | 0x0111 | Telematics module + SIM |
| 12 | Individual Memory (INDMEM) | 0x010d | Memory-seat hardware |
| 13 | Compass (KOMP) | 0x0106 | None — software-only |
| 14 | Electronic Logbook (FB) | 0x0103 | None — software-only |
| 15 | Engineering Menu | 0x010b | None |
| 16 | Off-road Navigation (OFFROADNAV) | 0x0102 | Navigation already activated |
| 17 | Speller in motion (SPELLER) | 0x010c | None — software-only |
| 18-28 | Navigation map databases | 0x2001-0x200b | Navigation already activated |

## Feature options

For four features the PCM reads the SubID as a setting, not just as part of the code. The web app and the offline app show a dropdown for each; on the command line it is `--subid NAME=HEX`. The first value is the default.

| Feature | SubID | Setting |
|---------|-------|---------|
| Video in Motion (TVINF) | `0x0166` / `0x0109` / `0x0105` / `0x0100` / `0x0000` | Video never locks / locks above 9 km/h / above 5 km/h / when moving / unless the handbrake is on |
| Speller (SPELLER) | same as TVINF | The same limits, for text entry |
| Voice control (SSS) | `0x0000` / `0x0001` | Siri off / Siri on (Siri Eyes Free) |
| Online Services | `0x0001` / `0x0002` | Search with Google / with Bing |

These come from the firmware (PCM3Root's activation handlers), not from car tests. The Backup tab shows which setting a car's own record carries.

## 1. FeatureLevel — Boot logo / model identity

**SWID/SubID:** `0x010e` / model-specific (see `--list-models`)

Porsche's "which car am I?" code. Determines the boot animation, main menu branding, and some UI colors. This is the single most-likely-to-be-needed code after a PCM swap or used-PCM retrofit — without it, the unit shows wrong model branding or "No Vehicle Identification" errors.


**What breaks without it:** Boot logo wrong. Main menu shows wrong car silhouette. Sometimes causes issues with Drive Select mode naming (Comfort/Sport/Sport+ vs 911's Normal/Sport). FeatureLevel also gates other features on some firmwares.

**SubID matters for this one:** Cayenne 958 Turbo uses `0x003b`, Cayenne 958 base uses `0x0039`, 911 991 Carrera uses `0x0003`, 991 Cabriolet uses `0x0007`, etc. If you pass the wrong model to `--model`, you'll get a code the PCM rejects. See `python generate_codes.py --list-models`.

## 2. Navigation — Core nav system

**SWID/SubID:** `0x0101` / `0x0000`

Enables the GPS navigation UI, route planning, turn-by-turn directions. Does NOT include map data (that's activated separately, see #18-28 below).


**What breaks without it:** The Nav button does nothing or shows "Feature not available." No route guidance, no GPS display.

**Hardware check:** Most PCM 3.1-equipped cars have the GPS antenna wired up even on nav-disabled trims. Check `/mnt/persist/gps_status` or the Engineering Menu GPS screen to see if the antenna sees satellites.

## 3. Voice Control (SSS — Sprachsteuerung)

**SWID/SubID:** `0x0104` / `0x0000` (Siri off) or `0x0001` (Siri on)

"Sag's Porsche" / "Speak a command" button. Voice dialing, address entry, media commands.

**Siri:** the SubID decides whether the PCM passes Bluetooth voice recognition through to an iPhone (Siri Eyes Free). With `0x0001` the PCM uses its Siri-enabled phone configuration (`/HBbin/pss.siri-enabled.cfg`); any other value uses the Siri-disabled one. 4 of the 27 factory records carry `0x0001`. PCM-Forge defaults to `0x0000`, the factory's most common value; pick Siri in the web app's dropdown or with `--subid SSS=0x0001`. Not yet confirmed on a car.


**Hardware check:** The overhead microphone is standard on every PCM 3.1 car — it's used for Bluetooth calls. Voice control just enables the speech-recognition software stack.

## 4. Sport Chrono

**SWID/SubID:** `0x0105` / `0x0000`

Activates the Sport Chrono package features in the PCM: lap timer UI, G-meter display, performance data recording, launch control status display.


**Hardware check:** The physical Sport Chrono dashboard clock (mounted on the top-center dash) needs to be present for the full package. Without the clock, the PCM lap-timer UI still works but the visual "Sport Chrono" package branding will look incomplete. Some Drive Select coding may also need to be adjusted.

## 5. Bluetooth Telephony (BTH)

**SWID/SubID:** `0x010a` / `0x0000`

Phone pairing, call handling, phonebook sync, SMS read-aloud on cars that support it.


**Hardware check:** Every PCM 3.1 has the Bluetooth module integrated. Stock from factory.

## 6. USB Media Support (UMS)

**SWID/SubID:** `0x0109` / `0x0000`

Plays audio files (MP3/AAC/FLAC depending on firmware) from USB stick. Without this, the USB port is only used for iPod-mode devices or firmware updates.


**Hardware check:** USB port present stock. This is purely a software unlock.

## 7. Video in Motion (TVINF)

**SWID/SubID:** `0x0107` / `0x0166` (default — some records vary)

Sets the speed lockout on video. PCM3Root calls this package `TVTunerSpeedLimits`, and the SubID is the limit itself:

| SubID | Video locks |
|-------|-------------|
| `0x0000` (or unknown) | unless the handbrake is on |
| `0x0100` | from 1 km/h |
| `0x0105` | from 5 km/h |
| `0x0109` | from 9 km/h |
| `0x0166` | never (PCM-Forge's default) |

The lock is read from vehicle speed and the handbrake signal; it releases 2 s after the car drops below the limit. No coding change is needed for it: activation alone sets the limit. Text entry while driving is a separate lock, #17 SPELLER.


**Note:** The factory records in `research/firmware/PagSWAct.csv` hold 19× `0x0166`, 4× `0x0109` and 1× `0x0000`: the variance is the market's speed limit, not the model. Pick another with `--subid TVINF=0x0109`.

## 8. Satellite Radio (SDARS)

**SWID/SubID:** `0x0108` / `0x0000`

SiriusXM satellite radio receiver on US-spec cars. Only 15 of 27 records in our test data have this (US-only market).


**Hardware check:** Requires the SiriusXM tuner module. Cars sold outside the US typically lack this hardware entirely.

## 9. HD Radio Tuner

**SWID/SubID:** `0x010f` / `0x0000`

HD Radio digital terrestrial broadcasts (US only).


**Hardware check:** HD Radio tuner module required. US-spec cars only.

## 10. DAB Digital Radio

**SWID/SubID:** `0x0110` / `0x0000`

DAB+/DAB digital radio for EU and select Asia-Pacific markets.


**Hardware check:** DAB tuner module required. EU-spec cars typically have this.

## 11. Online Services

**SWID/SubID:** `0x0111` / `0x0001` (Google) or `0x0002` (Bing)

Porsche Connect / Car Connect services: remote door lock, remote start (where legal), POI search, traffic overlays on nav.

**Search provider:** activating it also turns on the Aha app link over the iPhone connection (`/HBpersistence/ipod/eaf-aha-enabled.cfg`), and the SubID picks the provider its search uses: `0x0001` Google, `0x0002` Bing. Any other value falls back to Google (5 factory records carry `0x0000`).


**Hardware check:** Requires telematics control unit (TCU) with cellular modem + SIM. Most PCM 3.1 cars have hardware; SIM provisioning is the hard part now that 3G networks are sunset in the US.

## 12. Individual Memory (INDMEM)

**SWID/SubID:** `0x010d` / `0x0000`

Links driver profile to memory seat/mirror/steering column positions. Without this, seats don't auto-adjust when a different key fob is used.


**Hardware check:** Requires memory-capable seats (electric with memory buttons). Manual or non-memory seats can't use this.

## 13. Compass (KOMP)

**SWID/SubID:** `0x0106` / `0x0000`

KOMP is short for *Kompass*. It enables the digital compass: the widget on the CAR → My Screen page, the cardinal-direction indicator, the compass overlay on the navigation map, and — model-dependent — the heading readout in the instrument cluster. On some cars without navigation (the Macan in particular) the compass appears only once this is activated.

**Not component protection.** The similar-looking *Komponentenschutz* is a separate anti-theft mechanism handled at the gateway/ECU level and is not touched by PCM activation codes. Earlier versions of this file described KOMP that way; that was wrong. See [research/FEATURE_REFERENCE.md](research/FEATURE_REFERENCE.md).

## 14. Electronic Logbook (FB)

**SWID/SubID:** `0x0103` / `0x0000`

FB is short for *Fahrtenbuch*, the Porsche Electronic Logbook. Once activated the PCM records every trip — start and end point, distance, duration — and lets you classify journeys as business or private. It is one of the most obscure features on the unit and mainly of interest in Germany, where company-car drivers must keep a logbook for tax purposes.

The firmware's own engineering menu calls it *DriversLog*. Earlier versions of this file described FB as a "boot image / feature-enable baseline"; that was wrong.


## 15. Engineering Menu

**SWID/SubID:** `0x010b` / `0x0000`

Unlocks access to the Porsche-internal engineering/diagnostic menu. Similar to Audi's "Green Menu" on MMI. Contains voltage readings, software version info, per-module status, GPS diagnostics, CAN bus scopes.


**Access: SOUND + SOURCE together.** Confirmed on a real car (2026-11-14), and it
is the pair the HMI's key mapper checks (PCM3Reload, `CHBKey2MSMEventMapper`, from
0x08634b64): with SOURCE held, SOUND raises `EVENT_ENGINEERING`, but only once the
engineering menu has been enabled. Until then SOUND just opens the SOUND menu.

The SOURCE + OPTION entry of 2026-08-07 was wrong: the HMI ignores that pair (both
keys are swallowed, no event). SOURCE + MAP is a separate one, the PAG engineering
menu, which the unit enables only through diagnosis. (This also supersedes the
earlier "MENU + TUNER, varies by firmware" guess.)

Entry is **two-step**, and the firmware names every part of the gate:

```
UPD_ID_SWAct_engineeringmenu_step2_allowed      <- SWAct grants step 2
UPD_ID_engineeringmenu_step2_allowed
UPD_ID_engineeringmenu_step2UnlockCodeEngMode   <- alternative code path
UPD_ID_engineeringmenu_step2_RestCycles         <- limited attempts
```

The `SWAct_` prefix is the point: **software activation is what sets
`step2_allowed`.** So the combo gets you to step 1, and activating SWID `0x010b`
is what lets step 2 through. Menu construction is
`Engineering::MenuCreatorMediator` ("Activate EM: %d", "Creating H/B
Engineering menus", "Creating PAG Engineering menus").

99 engineering screens exist, including `GlobalSettings_GlobalSettings` (the
Ignition Mode setting below), `FaultMemory`, `Diagnosis`, `PAGVariantCoding`,
`SystemHarddisk`, `Trace`, and `SWActivationActivateSpecificCar`.

Note `step2UnlockCodeEngMode` looks like a second route in, but it is a DSI
property rather than a constant in the binary -- the 185 `UnlockCode` symbols in
the firmware are SIM/phone PIN handling (`SEC_SetUnlockCode`, NADPHONE), not
this. No shortcut found there.

### ★ THE BENCH REASON TO WANT THIS: `03 Ignition Mode`

Decoded from `PCM3Reload` 2026-08-07. The menu class is
`project_hmi_engineering_GlobalSettings`, and its Global Settings page carries
an **EEPROM** configuration list:

```
01 E2P-Structure          (Load E2Prom-File -> /HBpersistence/96xx.txt)
02 IPC Watchdog           0x22 inactive / 0xFF active (default)
03 Ignition Mode          0x00 Ignition from CAN (default)
                          0x01 Ignition ALWAYS ON
06 Store   07 Load
08 ST10 Module Mask       + 'Save changes to E2P'
```

Strings at `09683C28`-`09683CC4`; the E2P loader path at `09683768`/`0968377C`.

**`03 Ignition Mode = 0x01` makes the unit stop waiting for ignition on CAN.**
On a bench with no BCM the unit reports no-contact and never reaches a state
where the OnOff FSM will request `RELOAD_MODE_MEDIA` — which is the only safe
mode carrying package 11 `USB` (see `research/BOOT_ORDER_AND_STARTER.md`). So a
bench unit with no BCM cannot start USB no matter what you press, and
`Ignition always on` is the documented way out. It saves to E2P, so it
persists, and it is reversible by setting it back to `0x00`.

This makes the Engineering Menu the highest-value activation for bench work,
not a curiosity: it needs **no hardware** (see the table above), and it is the
route to a setting that unblocks media, USB, and — because pkg 22 `NETWORK`
requires 12 requires 11 — telnet/qconn as well.

**Not yet proven on hardware.** That ignition gating is what stops the MEDIA
request is a strong inference from `'IgnitionStatus is not valid'` plus the
observed BCM no-contact error, not something read end-to-end from the FSM.

## 16. Off-road Navigation (OFFROADNAV)

**SWID/SubID:** `0x0102` / `0x0000`

PCM3Root's activation dispatch names SWID `0x0102` Off-road Navigation. Until that table was read, PCM-Forge listed it as "TEL" (a telephone module); the PCM has no such package, and the phone is #5 BTH. The old name `TEL` is still accepted by `--add`, `--remove` and `--subid`.

**Caveat:** no factory record in `research/firmware/PagSWAct.csv` carries `0x0102` (the CSV has no column for it), so its effect has not been observed on a car.

## 17. Speller in motion (SPELLER)

**SWID/SubID:** `0x010c` / `0x0166` (default)

The lock on text entry (the speller: destinations, contacts) while driving. PCM3Root calls it `SpellerSpeedLimits`; it takes the same SubIDs as #7 TVINF, and `0x0166` means it never locks:

| SubID | Text entry locks |
|-------|-------------|
| `0x0000` (or unknown) | unless the handbrake is on |
| `0x0100` | from 1 km/h |
| `0x0105` | from 5 km/h |
| `0x0109` | from 9 km/h |
| `0x0166` | never (PCM-Forge's default) |

**Tested:** activated on a bench PCM with `0x0166` (state 7 straight away, kept across a power cycle). No factory record carries `0x010c`, and the lock itself has not yet been checked in a moving car. Pick another limit with `--subid SPELLER=0x0105`.

## 18-28. Navigation Map Databases (11 regions)

**SWID/SubID range:** `0x2001-0x200b` / `0x00ff`

Each region is a separately-activated map database:

| Code | Region |
|------|--------|
| NavDBEurope (`0x2001`) | All of Europe including Russia border zones |
| NavDBNorthAmerica (`0x2002`) | US, Canada, Mexico |
| NavDBSouthAfrica (`0x2003`) | SA + neighbors |
| NavDBMiddleEast (`0x2004`) | GCC countries + Israel |
| NavDBAustralia (`0x2005`) | Australia + NZ |
| NavDBAsiaPacific (`0x2006`) | Japan, Korea, SE Asia |
| NavDBRussia (`0x2007`) | Russia + CIS |
| NavDBSouthAmerica (`0x2008`) | Brazil, Argentina, Chile etc. |
| NavDBChina (`0x2009`) | China-only (uses restricted map data) |
| NavDBChile (`0x200a`) | Chile — separate from South America variant |
| NavDBArgentina (`0x200b`) | Argentina — separate from South America |


**Hardware check:** Requires #2 Navigation to be activated first. Map DB activation alone doesn't give you maps — you also need the actual map data files on the nav HDD/SSD.

## What this list does NOT include

PCM-Forge only handles features the PCM itself controls via the `PagSWAct.002` activation mechanism. The following are common retrofit desires that are **outside** PCM-Forge's scope:

- **CarPlay / Android Auto** — PCM 3.1 doesn't support these at all, regardless of activation codes. That's a PCM 4 / MIB2 feature. No amount of PCM 3.1 hacking will add CarPlay.
- **Apple CarPlay retrofit modules** (aftermarket boxes that intercept video) — hardware add-ons, not PCM features
- **Drive Select / Sport+ modes** — coded in the transmission control unit, not the PCM
- **Cluster retrofits** (analog-to-digital gauge cluster swaps) — separate cluster module programming, not PCM
- **Adaptive cruise / PASM / Porsche Torque Vectoring** — coded in the relevant control module (engine, suspension, differential), not the PCM
- **Keyless entry / Porsche Entry & Drive** — BCM-level coding, not PCM

## Real-world usage notes

**If you swapped a used PCM into your car:** Regenerate `FeatureLevel` for your VIN first — it carries the model identity. Then add whatever the donor unit had active, plus `Navigation` and the appropriate regional NavDB if it didn't have nav. `KOMP` and `FB` are the compass and the trip logbook; they play no part in matching a PCM to a car, contrary to what earlier versions of this file claimed.

**If you want features your car wasn't spec'd with:** Check which SWIDs are currently active (engineering menu will show this) and generate codes for the ones you want. Hardware-gated features (SDARS, HD Radio, DAB) won't work without the physical tuner regardless of activation.

**If you're doing model-variant coding** (e.g. converting a Cayenne 958 base's PCM to present as Turbo): just activate the FeatureLevel with `--model cayenne-958t`. That changes the boot logo and some UI elements. It does NOT convert your base Cayenne into a Turbo — that's a very different hardware discussion.

## How to generate codes

```bash
# See what's available
python generate_codes.py --list-models

# Generate all codes for your VIN (default: 991 Carrera)
python generate_codes.py WP0AA2A91CS106069

# Specific model
python generate_codes.py WP1AE2A28GLA64179 --model cayenne-958

# Write directly to USB stick for PCM delivery
python generate_codes.py WP1AE2A28GLA64179 E:\ --model cayenne-958

# Unknown model? Pass raw SubID
python generate_codes.py <VIN> --featlevel-subid 0x00XX
```

Or use the web tool at **[dspl1236.github.io/PCM-Forge](https://dspl1236.github.io/PCM-Forge/)** for the graphical version.
