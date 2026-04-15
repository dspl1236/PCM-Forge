# PCM 3.1 Research Notes

## Hardware

### Confirmed
- Manufacturer: Harman Becker Automotive Systems (FCC ID: T8G-BE96XX)
- Display: 7" touchscreen, 800×480 resolution
- Storage: Internal SATA HDD (some models have 100GB "Jukebox" version)
- USB: Single USB port (engineering boot capable)
- Audio: MOST bus to Bose/Burmester amplifier
- Firmware versions: v3.x through v4.76+

### Probable (based on Harman Becker platform sharing with MMI3G)
- OS: QNX RTOS
- CAN: Renesas V850 IOC gateway
- Application: Java on IBM J9 JVM
- IPC: HPIPC shared memory between main CPU and V850

### To Confirm
- Exact CPU (SH4 like MMI3G, or different?)
- QNX version (6.3 or 6.5?)
- J9 JVM presence and version
- V850 IOC firmware format
- USB boot mechanism details

## Engineering Menu

### Access Methods (reported)
1. **USB boot stick** — Primary method. Prepared USB stick triggers
   engineering mode on boot. File structure TBD.
2. **Source + Sound** — Some users report this button combo works
   on certain firmware versions. May require engineering mode to
   be previously enabled via PIWIS or USB stick.
3. **PIWIS** — Porsche dealer tool can enable engineering features.

### Engineering Menu Features (confirmed by Rennlist users)
- SWActivation — Software activation codes
- NavDB switching — Toggle between regional map databases
- UnlockCode — License key management
- Firmware version display
- Feature enable/disable

## Firmware Update Mechanism

### Map Updates
- Delivered on 5 DVDs + license key package
- License key is VIN-specific
- Loaded via PCM's disc drive
- Requires PIWIS activation in some cases
- Some versions require firmware downgrade (4.76 → 4.52) before map update

### PCM Software Updates
- Available on CD/DVD
- Multiple versions for different hardware revisions
- Can be self-installed (burn CD, insert, follow prompts)
- PIWIS required for some configuration after update

## CAN Bus Architecture (Cayenne 958)

The 958 Cayenne uses VAG Group CAN architecture:
- Powertrain CAN (500kbps): Engine, Transmission, ABS/ESP
- Comfort CAN (500kbps): Doors, Seats, Climate, Windows
- Infotainment CAN: PCM, Amplifier, Phone, Telematics
- Diagnostic CAN: OBD-II port access

Gateway module (similar to Audi J533) routes between buses.

## Diagnostic Addressing

Porsche uses standard VAG diagnostic addressing (same as Audi/VW):
- Module 01: Engine (DME)
- Module 02: Transmission
- Module 03: ABS/PSM
- Module 08: HVAC
- Module 09: Central Electrics
- Module 17: Instrument Cluster
- Module 19: Gateway
- Module 5F: PCM (head unit)
- Plus Porsche-specific modules (PASM, PDCC, Sport Chrono, etc.)

UDS protocol (ISO 14229) is used for diagnostic communication.
The same UDS stack from MMI3G-Toolkit's diag-tool works here.

## Key Differences from Audi MMI3G

| Aspect | MMI3G | PCM 3.1 |
|--------|-------|---------|
| Code execution entry | SD card (copie_scr.sh) | USB stick (eng. boot) |
| SD card slots | 2x SDHC | None (USB only) |
| Touchscreen | Touchpad on knob (3G+) | Full touchscreen |
| Engineering button | CAR + BACK (hold 5s) | Source + Sound (?) |
| Dealer tool | VCDS / ODIS | PIWIS |
| Map format | HDD + FSC activation | HDD + DVD + license key |

## References

- Rennlist PCM 3.1 Navigation thread (pages 1-4)
- FCC filing T8G-BE96XX (Harman Becker)
- PCM Repairs UK (confirms Harman Becker for all PCM generations)
- IOActive V850 paper (V850 IOC methodology)
- MMI3G-Toolkit research (sister platform architecture)
