# sh4-toolchain — build & run your own code on a PCM 3.1 (no QNX SDK)

The PCM 3.1 head unit is a **Renesas SH4A running QNX 6.3.2**. Harman never
shipped an SDK, and the on-unit libraries are symbol-stripped — so historically
you couldn't build a binary that runs on it. This toolchain solves that with
nothing but the stock Linux `sh4-linux-gnu` cross-compiler.

## How it works

Three pieces:

1. **`crt.S`** — a minimal C runtime. Provides `_start`: reads `argc`/`argv` off
   the stack, calls `main`, then `_exit(main())`. No glibc startup needed.
2. **`stub_libc.c` / `stub_libgf.c`** — tiny **SONAME stub** shared objects. They
   export just the *names* of the libc / libgf functions we call (plus the right
   `SONAME`). You link against these. At load time the PCM's own `ldqnx.so.2`
   rebinds every import to the **real** `libc.so.2` / `libgf.so.1` on the unit —
   so the stubs never actually run; they only satisfy the static linker.
3. **`build.sh`** — wires it together: builds the stub(s), compiles your `.c`
   `-ffreestanding`, assembles `crt.S`, and links a QNX SH4 LE ELF with the
   `/usr/lib/ldqnx.so.2` interpreter.

The result is a real, dynamically-linked QNX executable that calls the unit's
actual system libraries — built entirely off-target.

## Build

```sh
# one-time: apt install gcc-sh4-linux-gnu   (Debian/Ubuntu/WSL)
./build.sh app_oil.c        # -> ./app_oil   (QNX SH4 LE ELF)
./build.sh bt_fix.c
```

`build.sh` auto-adds the libgf stub when your source calls `gf_*`. Copy the
output to a FAT32 USB, then run it from the PCM shell (telnet/serial) as root.
Everything here is **RAM-only** — nothing writes to flash, a reboot is always a
clean slate.

## What's here

**Framework**
| file | purpose |
|------|---------|
| `crt.S` | minimal SH4 `_start` runtime |
| `stub_libc.c` | SONAME stub for `libc.so.2` (open/read/write/devctl/IPC…) |
| `stub_libgf.c` | SONAME stub for `libgf.so.1` (the `gf_*` graphics API) |
| `build.sh` | one-command cross-build + deploy hint |
| `font8x16.h` | self-shipped 8×16 bitmap font (text from `gf_draw_rect`) |

**Probes & runtime tools**
| file | purpose |
|------|---------|
| `lmgr_probe.c` | reverse-engineered layermanager connect/register probe — proves the cross-build runs and whether a 2nd display layer is free |
| `bt_fix.c` | universal self-locating BT/AUX boot patcher (see `../../modules/bt-aux-fix` and `research/BT_AUX_BOOT_FIX.md`) |
| `ch8read.c` | reads the raw Harman input stream off `/dev/ipc/ioc/ch8` |
| `dsi_probe.c` | attaches to the `KeyInput.SPHKeyInput` service via the DSI servicebroker |
| `dsi_client.c` | full staged DSI input listener (touch/key), diagnostic-first |

**Graphics / custom UI**
| file | purpose |
|------|---------|
| `lmgr_draw.c` | connect → register → getvfb → paint a rect on our own layer |
| `lmgr_overlay_safe.c` | small cooperative overlay + **clean teardown** (the anti-snow lifecycle) |
| `app_oil.c` | first real on-glass UI — an "oil service" screen drawn entirely from `gf_draw_rect` + the bitmap font |
| `app_forge.c` | multi-page toolkit shell (home/oil/info), Show-once + UpdateVfb page switching |

## Safety notes

- **Cooperative layers only.** Register a component-sized layer (480×240),
  never full-screen — fighting PCM3Root's layer 0 causes the oil/media/snow
  rotation. The examples probe down from 480×240.
- **Always tear down cleanly.** Unregister your displayable *before* exit so the
  compositor stops scanning your freed surface (a dirty exit leaves CRT "snow"
  that survives a soft power-off). `lmgr_overlay_safe.c` documents the ordering;
  the apps install a fault handler that unregisters on SIGSEGV/BUS/FPE/ILL.
- Nothing here touches read-only flash. Worst case is a reboot.

Built and validated on a Cayenne (958) PCM 3.1. Input (`dsi_*`, `ch8read`) is
diagnostic — protocol documented, on-car decode calibration ongoing.
