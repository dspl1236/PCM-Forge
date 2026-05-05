# Custom Boot Screen — Design Spec

## Date: May 5, 2026
## Status: Design — not yet implemented

---

## Overview

Allow users to upload a custom boot screen (the Porsche splash shown on
every startup) via the existing USB Stick tab in the web app. Uses a
single reserved slot (100 / SubID 0x0064) outside the factory range.

## How It Works

PCM3Root loads boot screens using a `%03u` format string:

```
/HBpersistence/CustomBootscreen_%03u.bin        ← checked first (flash)
/mnt/share/bootscreens/CustomBootscreen_%03u.bin ← fallback (HDD)
PCM31_bootScreenPorscheLogo.jpg                  ← ultimate fallback (IFS, read-only)
```

The `NNN` number is determined by the FeatureLevel SubID in PagSWAct.002.
Factory models use SubIDs 0x0001–0x0063 (slots 001–099). We own the RSA-64
key, so we can generate valid activation codes for any SubID.

**Slot 100 (SubID 0x0064)** is reserved for user custom boot screens.
No factory model uses this slot.

## User Flow

All within the existing **USB Stick** tab — no new tab.

1. Enter VIN as usual
2. Check **FeatureLevel** checkbox
3. In the model dropdown, select **"Custom — Upload your own"**
4. Upload zone appears below the dropdown
5. Drag/drop or browse for a PNG/JPEG image
6. Web app validates and shows preview:
   - Must be PNG or JPEG
   - Resized to 800 × 480 via canvas if dimensions differ
   - Converted to PNG (8-bit RGB, no alpha)
   - Warns if output exceeds 60 KB
7. Select other features, click **Build USB**
8. USB contains all the usual files plus `CustomBootscreen_100.bin`
9. Insert USB after PCM boots, wait 60–90 seconds
10. Hard reboot (hold INFO + CAR)
11. Custom boot screen appears

## Web App Changes

### Model Dropdown

Add one entry at the top of the MODELS list:

```javascript
'custom': [0x0064, 'Custom — Upload your own']
```

When selected:
- Show an upload zone (file input + drag/drop area)
- Show a canvas preview at 800×480
- Hide the factory boot screen preview

When any factory model is selected:
- Hide the upload zone
- Show factory preview as today

### Image Processing (client-side)

```javascript
// On file upload:
// 1. Load into Image element
// 2. Draw to 800x480 canvas (letterbox or stretch — TBD)
// 3. Export as PNG blob via canvas.toBlob('image/png')
// 4. Check size — warn if > 60KB
// 5. Store as Uint8Array for USB bundle
```

### FeatureLevel Code Generation

When custom is selected, generate FeatureLevel code with SubID 0x0064:

```
feat_hex = '010e0064'   // FeatureLevel + SubID 0x0064 = slot 100
```

The existing RSA-64 signer handles this — no changes needed to the
crypto code.

### USB Bundle

Add to the files array:

```javascript
files.push({
  path: 'CustomBootscreen_100.bin',
  bytes: canvasExportedPngBytes
});
```

### run.sh Changes

The activate `run.sh` already has a loop for `CustomBootscreen_*.bin`:

```bash
for bs in "${USBROOT}"/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && cp "$bs" /HBpersistence/ 2>/dev/null
done
```

Change to:

```bash
# Clean any previous custom boot screen (slot 100)
rm -f /HBpersistence/CustomBootscreen_100.bin
rm -f /mnt/share/bootscreens/CustomBootscreen_100.bin
# Install new custom boot screen to both locations
for bs in "${USBROOT}"/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && {
        cp "$bs" /HBpersistence/ 2>/dev/null
        cp "$bs" /mnt/share/bootscreens/ 2>/dev/null
    }
done
```

Writing to both locations ensures:
- `/HBpersistence/` — immediate use on next boot
- `/mnt/share/bootscreens/` — survives if persistence is wiped

## Constraints

| Constraint | Value | Source |
|-----------|-------|--------|
| Resolution | 800 × 480 | All 79 factory screens |
| Format | PNG (8-bit RGB) | Factory standard (099 is JPEG exception) |
| Max file size | ~60 KB recommended | HBpersistence flash space is limited |
| Slot number | 100 (fixed) | First slot outside factory range (001–099) |
| SubID | 0x0064 | Hex for slot 100 |
| Simultaneous custom screens | 1 | One slot, always overwritten |

## Fallback Safety

If anything goes wrong, the boot screen cannot brick the PCM:

1. **Bad PNG** → PCM3Root fails to load → falls through to Porsche crest
   (`PCM31_bootScreenPorscheLogo.jpg` in read-only IFS)
2. **Oversized image** → `cp` may fail silently → Porsche crest
3. **User wants to undo** → next USB run overwrites slot 100, or
   delete with `rm -f /HBpersistence/CustomBootscreen_100.bin`
4. **Factory reset** → persistence wiped → HDD copy survives,
   or falls through to Porsche crest if HDD copy also removed

The Porsche crest in the IFS is the unbrickable safety net.

## Restore to Factory

If a user wants to go back to their car's factory boot screen:

- Select the correct factory model from the dropdown (instead of Custom)
- This generates a FeatureLevel code with the original SubID
- `run.sh` removes slot 100 and the factory screen loads from HDD

No special "restore" flow needed — just pick the factory model.

## What NOT to Build

- **Multiple custom slots** — unnecessary, one screen per car
- **In-app image editor** — out of scope, users can use any image tool
- **Custom screen without FeatureLevel** — the code must be in PagSWAct.002
- **New tab** — fits cleanly in the existing USB Stick flow
- **Separate "restore" button** — selecting factory model handles it

## Files to Change

| File | Change |
|------|--------|
| `docs/index.html` | Add 'custom' to MODELS, upload zone, canvas processing |
| `docs/index.html` | Update RUN_ACTIVATE to write both locations + clean slot 100 |
| `research/BOOTSCREEN_FORMAT.md` | Document slot 100 reservation |
| `research/FEATURE_REFERENCE.md` | Note custom boot screen capability |

## Future Considerations

- **Image guidelines** — suggest dark backgrounds (OLED contrast, less
  glare at night), avoid pure white (blinding on startup)
- **Template overlay** — optional "Porsche" text or crest watermark the
  user can toggle (purely cosmetic, done in canvas)
- **Gallery** — community-shared boot screens (separate from this spec)
