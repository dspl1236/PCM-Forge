# PCM 3.1 Feature Activation Reference

Every feature on the Porsche PCM 3.1 is controlled by a **Software ID (SWID)** stored in the `PagSWAct.002` activation file on the PCM's internal HDD. Each SWID has a unique activation code generated from your vehicle's VIN.

This document explains what each feature does, how to access it, and what to expect when activated.

---

## Core Features

### ENGINEERING (SWID 0x010b)
**Internal name:** EngineeringMode  
**Porsche option:** Not a factory option — dealer/development tool  

Unlocks the hidden engineering and diagnostic menu on the PCM. This is the most powerful activation — it provides access to system internals that are normally only available to Porsche technicians via PIWIS.

**What it enables:**
- Engineering Settings Display (ESD) screens with system diagnostics
- DBGModeActive flag for CAN bus engineering menus
- GEM (Google Earth Module) diagnostic screens
- HDD partition and SMART health data
- Variant coding (CVALUE) viewer
- SWDL (software download) state information
- Flash status and firmware version details

**How to access:** Press **SOURCE + SOUND** buttons simultaneously (both physical buttons below the screen). The engineering menu appears only if the ENGINEERING activation code is present in PagSWAct.002.

**Note:** Without the activation code, pressing SOURCE + SOUND does nothing — the feature must be activated first.

---

### Navigation (SWID 0x0101)
**Internal name:** Navigation  
**Porsche option:** Standard on PCM 3.1 with navigation  

Enables the full navigation system including turn-by-turn directions, map display, route calculation, and destination entry. Without this activation, the NAV button on the PCM does nothing.

**What it enables:**
- Full map display with satellite/hybrid views
- Route planning and turn-by-turn guidance
- Address and POI search
- Traffic message channel (TMC) integration
- Personal destination memory
- Google Earth integration (when available)

**How to access:** Press the NAV button on the PCM

**Note:** Requires a compatible navigation database (NavDB) to be activated and installed on the HDD.

---

### TEL (SWID 0x0102)
**Internal name:** Telephone  
**Porsche option:** Standard equipment  

Enables the built-in telephone module for making and receiving calls through the PCM. This controls the base telephony functions independent of Bluetooth.

**What it enables:**
- PCM phone interface
- Contact management
- Call history
- Phone settings menu

**How to access:** Press the PHONE button on the PCM

---

### BTH (SWID 0x010a)
**Internal name:** BT_HPF (Bluetooth Hands-Free Profile)  
**Porsche option:** Standard equipment  

Enables Bluetooth connectivity for hands-free calling and audio streaming. This is separate from the base TEL module — BTH adds wireless connectivity.

**What it enables:**
- Bluetooth device pairing and management
- Hands-free calling via car speakers and microphone
- A2DP audio streaming (music from phone)
- AVRCP media controls (skip, pause, play via PCM buttons)
- Bluetooth contact/phonebook sync
- Up to 5 paired devices

**How to access:** PHONE → Bluetooth Settings

---

### FB (SWID 0x0103)
**Internal name:** DriversLog  
**Porsche option:** 9NY Electronic Logbook (~$600 factory option)  

Enables the Porsche Electronic Logbook (Fahrtenbuch). This is one of the most obscure PCM features — it automatically records every trip you take with detailed logging.

**What it enables:**
- Automatic recording of every trip over 100 meters
- Logs date/time of departure and arrival
- Records mileage at start and end of each trip
- Captures start and destination addresses (with navigation active)
- Trip type classification (business, personal, commute)
- Fuel stop recording
- Driver identification via key fob (assigns trips to Key 1 or Key 2)
- Storage for up to 1,500 trips
- Export via Bluetooth or USB to PC software
- Registration renewal and emissions test reminders

**How to access:** CAR → OPTION → SET-CAR → SET Logbook → Activate Logbook

**Use case:** Business expense tracking, tax deductions for mileage. Very popular in Germany where company car drivers must maintain a Fahrtenbuch for tax purposes.

---

### SSS (SWID 0x0104)
**Internal name:** SSS (Sprachsteuerungssystem)  
**Porsche option:** Voice control system  

Enables the PCM's built-in voice control system for hands-free operation of navigation, phone, and media functions.

**What it enables:**
- Voice-activated navigation destination entry
- Voice dialing from contacts
- Voice control of media playback
- Radio station selection by voice
- "Say what you see" menu navigation

**How to access:** Press the voice control button on the steering column stalk, or press and hold the PHONE button

**Note:** Voice recognition quality is typical of 2010-era systems. Works best with clear pronunciation and low background noise.

---

### SC (SWID 0x0105)
**Internal name:** SportChrono  
**Porsche option:** Sport Chrono Package  

Enables the Sport Chrono display and performance measurement features on the PCM screen. Works in conjunction with the physical Sport Chrono stopwatch on the dashboard (if equipped).

**What it enables:**
- Performance timer (0-60, 0-100, quarter mile)
- Lap timer with split times
- Sport display with g-force meter
- Real-time performance data overlay
- Sport and Sport Plus mode indicators on screen

**How to access:** CAR → Sport Display, or via the Sport Chrono button on the steering wheel

**Note:** Full Sport Chrono functionality requires the physical Sport Chrono hardware (clock on dash, Sport/Sport+ buttons). The PCM activation enables the software display features.

---

### KOMP (SWID 0x0106)
**Internal name:** Compass  
**Porsche option:** Compass display  

Enables the digital compass display on the PCM screen, showing the vehicle's current heading direction.

**What it enables:**
- Digital compass overlay on map display
- Cardinal direction indicator (N, NE, E, SE, S, SW, W, NW)
- Heading display in navigation mode

**How to access:** Appears as an overlay on the navigation map display

---

### TVINF (SWID 0x0107)
**Internal name:** TVTuner  
**Porsche option:** TV tuner module  
**SubID:** 0x0166 (specific to tuner variant)  

Enables the TV tuner functionality. When activated, a "TV" menu icon appears on the PCM home screen. This is also the menu used by aftermarket CarPlay/Android Auto modules (like the Mr12Volt) which masquerade as TV tuner devices on the MOST bus.

**What it enables:**
- TV menu icon on PCM home screen
- Analog/digital TV reception (where supported)
- Video input display

**How to access:** TV icon on PCM home screen

**Note:** Video playback is speed-restricted in most markets — screen blanks above ~5 km/h unless Video in Motion (VIM) coding is applied via PIWIS.

---

### SDARS (SWID 0x0108)
**Internal name:** SDARS (Satellite Digital Audio Radio Service)  
**Porsche option:** SiriusXM satellite radio  

Enables SiriusXM satellite radio reception. Requires an active SiriusXM subscription and the satellite radio antenna (standard on North American models).

**What it enables:**
- SiriusXM satellite radio channels
- Channel guide and favorites
- Artist/title display
- Category browsing
- Traffic overlay (requires SiriusXM Traffic add-on, ~$5/month via 1-800)

**How to access:** MEDIA → Source → Satellite Radio

**Note:** Traffic overlay comes via SiriusXM satellite — it's independent of internet connectivity. Displays crude segment-based coloring (red/yellow/green, ~1 mile segments).

---

### UMS (SWID 0x0109)
**Internal name:** UMS (USB Media Support)  
**Porsche option:** Standard on most configurations  

Enables USB media playback. Without this activation, the USB port under the armrest only charges devices — no media browsing or playback.

**What it enables:**
- USB flash drive music playback (MP3, WMA, AAC)
- iPod/iPhone media integration
- Album art display
- Folder/artist/album browsing
- Playlist support

**How to access:** MEDIA → Source → USB

---

### INDMEM (SWID 0x010d)
**Internal name:** IndividualMem  
**Porsche option:** Included with memory seats  

Enables individual memory settings that persist per driver. Associates seat position, mirror angles, and PCM preferences with each key fob.

**What it enables:**
- Per-driver seat position memory (linked to key fob)
- Per-driver mirror position memory
- Per-driver PCM preferences (radio presets, display settings)
- Automatic recall when unlocking with assigned key

**How to access:** Automatic — settings follow the key fob used to unlock the vehicle

---

### FeatureLevel (SWID 0x010e)
**Internal name:** FeatureLevel  
**SubID:** Varies by model (this is what the Boot Screen dropdown controls)  

Controls the PCM's hardware feature level identifier, which determines the boot screen logo displayed on startup. The SubID must match your vehicle model — using the wrong SubID shows the wrong logo but doesn't affect functionality.

**What it controls:**
- Boot screen logo (Porsche model crest/badge on startup)
- Hardware capability flags read by PCM firmware

**SubID examples:**
- 0x0043 = Cayenne S E-Hybrid
- 0x003e = Cayenne S
- 0x0039 = Cayenne base
- 0x0057 = 911 Carrera

**How to access:** Visible on every PCM boot — the splash screen you see when starting the car

---

### HDTuner (SWID 0x010f)
**Internal name:** HDTuner  
**Porsche option:** HD Radio  

Enables HD Radio (iBiquity) reception for higher-quality FM broadcasts and additional digital subchannels. North America only.

**What it enables:**
- HD Radio digital FM reception
- HD2/HD3 subchannel access
- Artist Experience (album art on supporting stations)
- Improved audio quality on HD-capable stations

**How to access:** MEDIA → Source → FM → HD indicator appears on compatible stations

---

### DABTuner (SWID 0x0110)
**Internal name:** DABTuner  
**Porsche option:** DAB+ digital radio (European markets)  

Enables DAB/DAB+ digital radio reception. European market equivalent of HD Radio.

**What it enables:**
- DAB/DAB+ digital radio reception
- Ensemble and service browsing
- Dynamic label segment (DLS) text display
- Slideshow images (on supporting stations)
- Automatic FM fallback when DAB signal is lost

**How to access:** MEDIA → Source → DAB

---

### OnlineServices (SWID 0x0111)
**Internal name:** OnlineServices  
**SubID:** 0x0001  

Enables internet-connected services on the PCM. This originally supported Porsche-branded online features via the built-in cellular modem or tethered phone.

**What it enables:**
- Online POI search
- Weather information display
- News feeds
- Online destination entry
- Google Street View (when available)
- Google local search

**How to access:** Various — integrated into NAV and INFO menus

**Note:** Many original online services have been discontinued. The LTE restoration project (PCM-Forge) aims to bring internet connectivity back to these units.

---

## Navigation Databases

Navigation database activations control which regional map data the PCM will load. You must have the corresponding map data files on the HDD for the activation to have any effect.

| SWID | Name | Region |
|------|------|--------|
| 0x2001 | NavDBEurope | Europe (all countries) |
| 0x2002 | NavDBNorthAmerica | USA, Canada, Mexico |
| 0x2003 | NavDBSouthAfrica | South Africa |
| 0x2004 | NavDBMiddleEast | Middle East |
| 0x2005 | NavDBAustralia | Australia, New Zealand |
| 0x2006 | NavDBAsiaPacific | Asia Pacific region |
| 0x2007 | NavDBRussia | Russia |
| 0x2008 | NavDBSouthAmerica | South America |
| 0x2009 | NavDBChina | China |

**Note:** NavDB activations use SubID 0x00FF (wildcard).

---

## How Activation Works

Each activation code is a 16-character hexadecimal string generated from:
1. Your 17-digit VIN
2. The feature's SWID + SubID (4 bytes)
3. A proprietary algorithm involving CRC32 and byte transformations

The activation file `PagSWAct.002` stores all active features as 28-byte records. When the PCM boots, it reads this file and enables/disables features based on which valid codes are present.

**Important:** `PagSWAct.002` is a **complete replacement** — only features with valid codes in the file will be active. If you generate a file with only one feature, all other features will be deactivated. Always include all features you want to keep active.

---

## PCM 3.1 Button Combinations

### Engineering Menu
**Buttons:** Press **SOURCE + SOUND** simultaneously  
**Requirement:** ENGINEERING (SWID 0x010b) must be activated  
**Result:** Opens the hidden engineering diagnostics menu with ESD screens, variant coding, CAN data, and system info.

### Soft Reboot (PCM restart)
**Buttons:** Press and hold **INFO** for ~10 seconds  
**Result:** PCM reboots and shows Porsche logo. All settings preserved. Use this when the PCM freezes or misbehaves.

### Hard Reboot (full restart)
**Buttons:** Press and hold **INFO + CAR** simultaneously  
**Result:** Forces a complete QNX restart. More thorough than the soft reboot — equivalent to pulling the fuse and reinserting it.

### Vehicle Handover / Factory Reset
**Sequence:** After a soft reboot, immediately navigate:  
CAR → OPTION → Set PCM System → Reset PCM → Vehicle Handover → Yes → Yes  
**Warning:** This deletes ALL personal settings, paired phones, radio stations, and saved destinations.

---

## Compatibility Notes

- **CarPlay/Android Auto modules** (Mr12Volt, GTA, Carlinkkit, etc.): These are HARDWARE devices that sit on the MOST fiber optic bus. They are completely independent of software activations and are not affected by PCM-Forge.
- **PIWIS coding:** Some features require both activation AND variant coding via PIWIS. For example, Video in Motion (VIM) requires TVINF activation plus a PIWIS coding change to disable the speed restriction.
- **Firmware version:** All activations work across PCM 3.1 firmware versions (tested on v4.66 through v4.76).
