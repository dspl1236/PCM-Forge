# PCM 3.1 Boot Screen Format

> Reverse-engineered from firmware `PCM31RDW400` (June 2015 build)

## Format

**It's just a PNG.** No custom format, no encryption, no wrapper.

| Property | Value |
|----------|-------|
| Format | PNG (standard, with `89 50 4e 47` header) |
| Resolution | 800 × 480 pixels |
| Color | 8-bit RGB (PNG type 02) |
| Extension | `.bin` (renamed PNG) |
| Exception | `_099` is JPEG (JFIF) |
| Typical size | 13–45 KB |

## File Location

| Path | Purpose |
|------|---------|
| `/mnt/share/bootscreens/CustomBootscreen_NNN.bin` | Factory defaults (79 files on HDD) |
| `/HBpersistence/CustomBootscreen_NNN.bin` | Active boot screen (flash persistence) |

The PCM copies the selected boot screen from HDD to flash on selection change.
The number `NNN` corresponds to the FeatureLevel / model variant.

## Known Boot Screen Numbers

Based on firmware analysis, the numbering appears to follow model/market variants:

| Range | Likely Model/Market |
|-------|-------------------|
| 001–016 | 911 (997) variants |
| 017 | (missing — skipped) |
| 018–031 | 911 (991) variants |
| 032–033 | (missing) |
| 034–054 | Cayenne (958) / Panamera (970) variants |
| 055 | (missing) |
| 056–067 | Cayenne continued (067 = Cayenne 958 NA) |
| 068–070 | (missing) |
| 071–079 | Boxster / Cayman (981) |
| 080–085 | (missing) |
| 086–088 | Special / development |
| 089–093 | (missing) |
| 094–099 | Macan (95B) / special editions |

Your car (Cayenne 958 NA) uses **CustomBootscreen_067.bin** (35,394 bytes).

## How to Set a Custom Boot Screen

### Method 1: USB Stick (via run.sh)

Add to your `run.sh`:

```bash
#!/bin/ksh
USBROOT="$1"
[ -z "$USBROOT" ] && USBROOT="/fs/usb0"
# Copy custom boot screen
cp "${USBROOT}/CustomBootscreen_067.bin" /HBpersistence/CustomBootscreen_067.bin
echo "Boot screen updated" > "${USBROOT}/pcm_ran.txt"
```

Place your 800×480 PNG on the USB stick renamed as `CustomBootscreen_067.bin`.

### Method 2: Engineering Menu

If Engineering mode is activated, the boot screen selector is available in the
Engineering menu under the display/boot settings section.

### Creating a Custom Image

1. Create or find an image you want
2. Resize to exactly **800 × 480 pixels**
3. Save as **PNG** (8-bit RGB, no alpha channel)
4. Rename to `CustomBootscreen_067.bin` (use your car's number)
5. Deploy via USB stick

**Keep file size under ~60KB** — the flash persistence partition is only 30KB free
space (from diagnostic log: 30,208 total, 8,082 used = ~22KB free). Larger PNGs
may fail to copy. Use PNG compression or reduce color complexity if needed.

⚠️ **Note on persistence space:** Your `/HBpersistence` partition is flash memory
with limited space. The factory bootscreen_067 is 35,394 bytes. If your custom
image is significantly larger, it may not fit. Monitor with diagnostic mode.

### Restoring Factory Boot Screen

To restore the factory boot screen:

```bash
#!/bin/ksh
USBROOT="$1"
# Remove custom, PCM will fall back to HDD copy
rm -f /HBpersistence/CustomBootscreen_*.bin
echo "Boot screen restored" > "${USBROOT}/pcm_ran.txt"
```

Or copy the original from the HDD:

```bash
cp /mnt/share/bootscreens/CustomBootscreen_067.bin /HBpersistence/CustomBootscreen_067.bin
```

## Archive

All 79 factory boot screens are archived in `PCM31_Bootscreens_All_79.zip`
in the research/firmware directory. Files are renamed from `.bin` to `.png`
for easy viewing (they're standard PNGs).

## Firmware References

From `PCM3Root` binary:

```
"/HBpersistence/CustomBootscreen_%03u.bin"     — persistence path pattern
"/mnt/share/bootscreens"                        — HDD source directory
"%s/CustomBootscreen_%03u.???"                  — wildcard search
"copy bootscreen from hdd to flash: system(%s)" — copy mechanism
"copy bootscreen from %s to flash: system(%s)"  — alternative source
"rm -f /HBpersistence/CustomBootscreen_*"       — cleanup command
"bootscreen %s available in persistence"         — found in flash
"bootscreen %s not available in persistence"     — not in flash, use HDD
"No unlock code for FeatureLevel present, set empty PathToBootscreen"
```

Boot screen display state machine:
```
SHOW_BOOTSCREEN_NEXT_0      → prepare next screen
SHOW_BOOTSCREEN_8           → display active
SHOW_BOOTSCREEN_WAIT_13     → waiting for graphics
BOOTSCREEN_TIMER_ELAPSED_GRAPHIC_READY_15     → timer done, graphic loaded
BOOTSCREEN_TIMER_ELAPSED_GRAPHIC_NOT_READY_17 → timer done, graphic failed
BootscreenShown             → confirmed visible
SWITCH_OFF Bootscreen sent SIGUSR1 to PCM3Boot → transition to main UI
```
