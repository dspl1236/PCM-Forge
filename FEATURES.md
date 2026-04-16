# What PCM-Forge Can Activate

All 26 features the Porsche PCM 3.1 can unlock, with retail context and what each one actually does in the car.

**TL;DR:** If your PCM is PCM 3.1 hardware (Cayenne 958, 911 991.1, Panamera 970, Boxster/Cayman 981, Macan 95B), PCM-Forge can generate a permanent activation code for any of these features. Whether the feature then works depends on whether the physical hardware is present in the car — see the "Hardware required" column.

## Quick Reference

| # | Feature | SWID | Dealer $ | Hardware needed? |
|---|---------|------|----------|------------------|
| 1 | FeatureLevel | 0x010e | ~$3,500 | None — software-only |
| 2 | Navigation | 0x0101 | ~$2,500 | GPS antenna usually already present |
| 3 | Voice Control (SSS) | 0x0104 | ~$800 | Microphone already in car |
| 4 | Sport Chrono | 0x0105 | ~$1,400 | Dashboard button + cluster firmware |
| 5 | Bluetooth Telephony (BTH) | 0x010a | ~$500 | Bluetooth module present stock |
| 6 | USB Media Support (UMS) | 0x0109 | ~$300 | USB port present stock |
| 7 | Video in Motion (TVINF) | 0x0107 | — | Unofficial — dealer won't sell |
| 8 | Satellite Radio (SDARS) | 0x0108 | ~$750 | SiriusXM tuner (US-spec cars) |
| 9 | HD Radio Tuner | 0x010f | ~$500 | HD Radio tuner (US-spec cars) |
| 10 | DAB Digital Radio | 0x0110 | ~$500 | DAB tuner (EU-spec cars) |
| 11 | Online Services | 0x0111 | ~$250/yr | Telematics module + SIM |
| 12 | Individual Memory (INDMEM) | 0x010d | ~$200 | Memory-seat hardware |
| 13 | Component Activation (KOMP) | 0x0106 | internal | None |
| 14 | Feature Base (FB) | 0x0103 | internal | None |
| 15 | Engineering Menu | 0x010b | not sold | None |
| 16-26 | Navigation map databases | 0x2001-0x200b | $200-800/region | Navigation already activated |

## 1. FeatureLevel — Boot logo / model identity

**SWID/SubID:** `0x010e` / model-specific (see `--list-models`)

Porsche's "which car am I?" code. Determines the boot animation, main menu branding, and some UI colors. This is the single most-likely-to-be-needed code after a PCM swap or used-PCM retrofit — without it, the unit shows wrong model branding or "No Vehicle Identification" errors.

**Retail cost:** ~$3,500 at a Porsche dealer. This is what motivated most of the PCM-Forge research.

**What breaks without it:** Boot logo wrong. Main menu shows wrong car silhouette. Sometimes causes issues with Drive Select mode naming (Comfort/Sport/Sport+ vs 911's Normal/Sport). FeatureLevel also gates other features on some firmwares.

**SubID matters for this one:** Cayenne 958 Turbo uses `0x003b`, Cayenne 958 base uses `0x0039`, 911 991 Carrera uses `0x0003`, 991 Cabriolet uses `0x0007`, etc. If you pass the wrong model to `--model`, you'll get a code the PCM rejects. See `python generate_codes.py --list-models`.

## 2. Navigation — Core nav system

**SWID/SubID:** `0x0101` / `0x0000`

Enables the GPS navigation UI, route planning, turn-by-turn directions. Does NOT include map data (that's activated separately, see #16-26 below).

**Retail cost:** ~$2,500 on cars that came without nav from factory.

**What breaks without it:** The Nav button does nothing or shows "Feature not available." No route guidance, no GPS display.

**Hardware check:** Most PCM 3.1-equipped cars have the GPS antenna wired up even on nav-disabled trims. Check `/mnt/persist/gps_status` or the Engineering Menu GPS screen to see if the antenna sees satellites.

## 3. Voice Control (SSS — Sprachsteuerung)

**SWID/SubID:** `0x0104` / `0x0000`

"Sag's Porsche" / "Speak a command" button. Voice dialing, address entry, media commands.

**Retail cost:** ~$800.

**Hardware check:** The overhead microphone is standard on every PCM 3.1 car — it's used for Bluetooth calls. Voice control just enables the speech-recognition software stack.

## 4. Sport Chrono

**SWID/SubID:** `0x0105` / `0x0000`

Activates the Sport Chrono package features in the PCM: lap timer UI, G-meter display, performance data recording, launch control status display.

**Retail cost:** ~$1,400 for the full hardware package. PCM activation alone is ~$400-500.

**Hardware check:** The physical Sport Chrono dashboard clock (mounted on the top-center dash) needs to be present for the full package. Without the clock, the PCM lap-timer UI still works but the visual "Sport Chrono" package branding will look incomplete. Some Drive Select coding may also need to be adjusted.

## 5. Bluetooth Telephony (BTH)

**SWID/SubID:** `0x010a` / `0x0000`

Phone pairing, call handling, phonebook sync, SMS read-aloud on cars that support it.

**Retail cost:** ~$500 if deactivated at factory.

**Hardware check:** Every PCM 3.1 has the Bluetooth module integrated. Stock from factory.

## 6. USB Media Support (UMS)

**SWID/SubID:** `0x0109` / `0x0000`

Plays audio files (MP3/AAC/FLAC depending on firmware) from USB stick. Without this, the USB port is only used for iPod-mode devices or firmware updates.

**Retail cost:** ~$300.

**Hardware check:** USB port present stock. This is purely a software unlock.

## 7. Video in Motion (TVINF)

**SWID/SubID:** `0x0107` / `0x0166` (default — some records vary)

Removes the speed lockout on video playback and — depending on firmware — on some navigation interactions. On stock PCMs, DVDs/video sources stop displaying above ~5 mph. With TVINF active, video plays at any speed.

**Retail cost:** Porsche does NOT sell this as a retail option. It's a code that exists in firmware for markets (primarily some Asian export) where video-in-motion is legal. In most US/EU markets, activating this is legal for passengers but not drivers — check local laws.

**Note:** This is the feature with the most SubID variance across our test data — appears to be model-keyed similar to FeatureLevel. Default value works for most cars.

## 8. Satellite Radio (SDARS)

**SWID/SubID:** `0x0108` / `0x0000`

SiriusXM satellite radio receiver on US-spec cars. Only 15 of 27 records in our test data have this (US-only market).

**Retail cost:** ~$750 + ongoing subscription.

**Hardware check:** Requires the SiriusXM tuner module. Cars sold outside the US typically lack this hardware entirely.

## 9. HD Radio Tuner

**SWID/SubID:** `0x010f` / `0x0000`

HD Radio digital terrestrial broadcasts (US only).

**Retail cost:** ~$500.

**Hardware check:** HD Radio tuner module required. US-spec cars only.

## 10. DAB Digital Radio

**SWID/SubID:** `0x0110` / `0x0000`

DAB+/DAB digital radio for EU and select Asia-Pacific markets.

**Retail cost:** ~$500.

**Hardware check:** DAB tuner module required. EU-spec cars typically have this.

## 11. Online Services

**SWID/SubID:** `0x0111` / `0x0001`

Porsche Connect / Car Connect services: remote door lock, remote start (where legal), POI search, traffic overlays on nav.

**Retail cost:** ~$250/year subscription after initial hardware cost.

**Hardware check:** Requires telematics control unit (TCU) with cellular modem + SIM. Most PCM 3.1 cars have hardware; SIM provisioning is the hard part now that 3G networks are sunset in the US.

## 12. Individual Memory (INDMEM)

**SWID/SubID:** `0x010d` / `0x0000`

Links driver profile to memory seat/mirror/steering column positions. Without this, seats don't auto-adjust when a different key fob is used.

**Retail cost:** ~$200 if memory seats are fitted but not activated.

**Hardware check:** Requires memory-capable seats (electric with memory buttons). Manual or non-memory seats can't use this.

## 13. Component Activation (KOMP)

**SWID/SubID:** `0x0106` / `0x0000`

Internal Porsche field-service code for component protection / theft deterrent matching. Required for the PCM to accept data from other modules in the car (cluster, CAN gateway, BCM).

**Retail cost:** Internal service item, not sold to customers. Normally written when PCM is matched to a VIN at the factory or dealer.

**What breaks without it:** PCM may show "Component protection active" errors, refuse to communicate with other modules, or go into limp-home UI.

## 14. Feature Base (FB)

**SWID/SubID:** `0x0103` / `0x0000`

Internal: boot image / feature-enable baseline. Usually written together with FeatureLevel as part of the first-time PCM matching process.

**Retail cost:** Internal. Not sold separately.

## 15. Engineering Menu

**SWID/SubID:** `0x010b` / `0x0000`

Unlocks access to the Porsche-internal engineering/diagnostic menu. Similar to Audi's "Green Menu" on MMI. Contains voltage readings, software version info, per-module status, GPS diagnostics, CAN bus scopes.

**Retail cost:** Not sold. This is a factory engineer / field-service feature.

**Access:** After activation, hold MENU + TUNER (or some variant; varies by firmware) on the PCM to enter.

## 16-26. Navigation Map Databases (11 regions)

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

**Retail cost:** $200-800 per region. Cheaper regions are smaller market areas; Europe and North America are the expensive ones. Porsche typically includes one region with the car and charges for additional regions or yearly map data refreshes.

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

**If you swapped a used PCM into your car:** You likely need at minimum `FeatureLevel`, `KOMP`, and `FB` regenerated for your VIN. Add `Navigation` + the appropriate regional NavDB if the donor unit didn't have nav active.

**If you bought a car that was spec'd without some features:** Check which SWIDs are currently active (engineering menu will show this) and generate codes for the ones you want. Hardware-gated features (SDARS, HD Radio, DAB) won't work without the physical tuner regardless.

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
