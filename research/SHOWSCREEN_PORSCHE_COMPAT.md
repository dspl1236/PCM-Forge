# showScreen on Porsche PCM 3.1 — and the native replacement, `showimg`

**STATUS: SOLVED (on-car confirmed 2026-07-18).** The Audi `showScreen` binary
cannot display on Porsche PCM 3.1 — but we no longer need it. `showimg` is a
Porsche-native image blitter that puts arbitrary pictures on the glass through
the layer manager, verified on a Cayenne. This doc explains why `showScreen`
fails and documents the working replacement.

## Why the Audi `showScreen` fails on Porsche

`showScreen` connects to the display via **`lmgrHMIConnect`** — a **layermanager
V2** call. Porsche PCM 3.1 runs **layermanager V1**, which has no `lmgrHMIConnect`;
it uses **`lmgrComponentConnect`** instead. So `showScreen` dies at the connect
step and displays nothing (on-car log: `lmgrHMIConnect failed`).

```
showScreen needs:              Audi V2    Porsche V1
─────────────────────────────────────────────────────
lmgrHMIConnect                   ✓          ❌ MISSING
lmgrComponentConnect             —          ✓  (use this)
lmgrRegisterDisplayable          ✓          ✓
lmgrGetVfb                       ✓          ✓
lmgrUpdateVfb                    ✓          ✓
```

Both platforms are otherwise identical for graphics — SH4A (SH7785), QNX 6.3.2,
and a **byte-identical `libgf.so.1`** — which is what makes the `gf` blit API
below directly reusable.

## The replacement: `showimg`

`showimg` reuses the **proven** Porsche layer-manager front-half (the same
`lmgrComponentConnect` → register → getvfb sequence our on-glass UIs already run)
and adds a `gf` image blit. It does **not** use QNX `libimg` at all — instead of
decoding a PNG on the head unit, the **host bakes the image to raw pixels** and
the car just blits them. No decoder, no `dlopen`, nothing to go wrong at runtime.

### The `gf` blit ABI (reverse-engineered from `showScreen`)

`showScreen`'s own disassembly (via `sh4-linux-gnu-objdump`; `libgf` is identical
on both platforms) gives the exact calls — no guessing:

```
gf_surface_attach(surface, dev, width, height, stride, format, palette, data, flags)   // 9 args
gf_draw_blit2   (context, src_surface, dst_surface, sx, sy, sx2, sy2, dx, dy)           // 9 args
```

Two details that matter, both taken straight from the real call sites:
- **`gf_draw_blit2` dst = 0** → blit onto the context's currently bound surface
  (the VFB, set via `gf_context_set_surface`).
- **Source rectangle uses INCLUSIVE corners** — pass `(0, 0)` → `(w-1, h-1)`, not
  a width/height extent.
- **`gf_format_t 0x1420`** is the 32-bpp format `showScreen` passes for a decoded
  image; `showimg` uses the same.

Sequence: `gf_dev_attach` → lmgr connect/register/getvfb →
`gf_surface_attach_by_sid`(VFB) → `gf_context_create` + `gf_context_set_surface` →
`gf_surface_attach`(our raw pixels) → `gf_draw_begin` → `gf_draw_blit2` →
`gf_draw_finish`/`end` → `lmgrUpdateVfb` → `lmgrShow` → hold → **clean unregister
teardown** (anti-snow) + fault handler.

### Blob format (`PFIM`)

A tiny raw container — 24-byte little-endian header, then pixels:

```
u32 magic  = 0x4d494650 ("PFIM")
u32 width
u32 height
u32 gf_format        // travels in the header -> change pixel format by RE-BAKING, no recompile
u32 stride           // 0 => width*bpp
u32 bpp              // bytes per pixel
... pixel bytes ...
```

The tool is `tools/sh4-toolchain/showimg.c` (build it with `tools/sh4-toolchain/build.sh`);
host baker `tools/sh4-toolchain/make_img.py` (Pillow): `python make_img.py in.png out.bin
[--format bgra8888|argb8888|rgba8888|abgr8888|rgb565] [--size WxH]`. Because the
`gf_format` lives in the header, iterating the pixel format is a re-bake, not a
recompile — handy for dialing in the exact byte order on the bench.

### Layer size

`showimg` registers a **480×240 component layer** (the same size our on-glass apps
use). It deliberately does **not** take the full 800×480 — a full-screen layer
brawls with PCM3Root's layer 0 (the oil/media/snow rotation). Full-screen splashes
are possible but require the heavier full-display path; the component layer is the
safe, proven target. Full-screen source art (e.g. the 800×480 toolkit status
screens) is simply down-scaled to 480×240 by the baker.

## On-car confirmation (Cayenne, 2026-07-18)

Every step returned success and the image displayed:

```
reg 480x240 -> GRANTED
getvfb sid=0xcc
surface_attach rc=0x00000000     <- gf_surface_attach (9-arg) + fmt 0x1420 accepted
show rc=0x00000000
image up 480x240 ... unregister rc=0 ... NO snow
```

Clean teardown, no CRT snow, reboot-safe (RAM only — never touches flash).

## No framebuffer device — the layer manager is the only way in

For completeness (and to close off a common wrong turn): PCM 3.1 has **no
Linux-style framebuffer node** you can `cat` raw bytes to. A live `/dev` listing
shows only:

```
/dev/io-display/10cf,202b,0     <- the Fujitsu (0x10cf) "Carmine" GPU (devg-carmine)
/dev/layermanager               <- the Harman compositor
```

Every `/dev/fb0`, `/dev/graphics/fb0`, `/dev/fb` path is **absent**. So
`cat splash.raw > /dev/fb0` (a Linux fbdev idiom) cannot work here — and even if a
raw buffer were writable, the compositor would immediately overwrite it. The
cooperative `gf` / layer-manager path that `showimg` uses is the only real way
onto this screen, and the compositor **respects** a registered layer instead of
fighting it.

## Fix options — resolved

| option | verdict |
|--------|---------|
| 1. Binary-patch `showScreen`'s `HMIConnect` → `ComponentConnect` | unnecessary |
| 2. **Write a Porsche-native tool** (`lmgrComponentConnect` + `gf`) | ✅ **done — this is `showimg`** |
| 3. Hijack PCM3Root's `CustomBootscreen` `.bin` loader | not needed for runtime display |
| 4. Skip status PNGs on Porsche | obsolete — status screens now work |

## Result

The toolkit's status screens (`running` / `done` / `activating` …), which the web
builder already drops on every USB, can now actually display on Porsche via
`showimg` instead of the dead Audi `showScreen` — and the same pipeline is the
foundation for custom on-glass UI.
