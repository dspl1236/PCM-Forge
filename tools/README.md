# PCM-Forge tools

Purpose-built tooling for reverse-engineering, building for, and talking to the
Porsche **PCM 3.1** head unit (Harman Becker, Renesas SH4A / QNX 6.3.2). These
are the developer-side tools behind the USB modules — the workshop, not the
shipped payloads.

> **Nothing here modifies read-only flash, and no Porsche/Harman firmware is
> redistributed.** The RE tools operate on update packages you supply yourself;
> the on-car tools run from RAM (a reboot reverts everything). Research and
> personal use on your own vehicle.

## Build & run your own code — [`sh4-toolchain/`](sh4-toolchain/)

Compile runnable **QNX SH4 binaries with the stock Linux `sh4-linux-gnu`
cross-compiler — no QNX SDK.** SONAME stub libs + a bare `crt.S` let you link
against the unit's real (symbol-stripped) `libc.so.2` / `libgf.so.1`. Includes
the layermanager probes, the `bt_fix` patcher source, the DSI input clients, and
the custom on-glass UI apps (`app_oil`, `app_forge`). One command:
`./build.sh app_oil.c`. For on-glass images, `make_img.py` (CLI) and
`pfim_tool.py` (desktop GUI) bake a PNG into the raw `PFIM` blob that `showimg`
displays — the GUI also inspects a blob and compares channel orders to fix a
color swap.

## Firmware extraction & analysis — [`firmware-re/`](firmware-re/)

Pull `PCM3Root` out of a `PCM31<REGION><VER>.rar` package and analyse it:
`carve_pcm3root.py` (carve the SH4 ELF), `scan_pcm3root.py` (portable BT/AUX
signature verdict), `scan_all_firmware.py` (the batch harness behind the
31-build tested matrix), `decompile_keyinput.py` (Ghidra post-script).

## Activation

- **`prepare_usb.py`** — build the USB activation payload (`PagSWAct.002` +
  LF `copie_scr.sh`) for your VIN. `python prepare_usb.py <VIN> [features…]`.
- The activation-code algorithm itself is in **`../generate_codes.py`** (repo
  root) with the write-up in `research/ALGORITHM_CRACKED.md`.

## Module dev-tooling

Source, build scripts, and engineering-definition files behind the matching
`modules/`:

- **`service-reset/`** — `uds_send.c` + build + the UDS/`.esd` engineering defs
- **`ioc-probe/`** — BAP/CAN channel-scan scripts + IOC engineering defs
- **`sysinfo/`** — system-info dump scripts
- **`bench-dongle/`** — the bench-harness dongle firmware (`.ino`)

## Standalone probes & patchers

| tool | purpose |
|------|---------|
| `pcm_shell.py` | telnet shell client to the unit (`--host …`) |
| `cvalue_tool.py` | decode Harman `CVALUE*.CVA` coding-value files (read-only) — `python cvalue_tool.py FILE.CVA` |
| `asix_universal_patch.py` | patch the ASIX USB-Ethernet driver for clone/unsupported chips |
| `diff_fw.py` | diff two firmware images |
| `verify.py` | integrity/verification helper |
| `can_probe.sh` / `display_probe.sh` | on-car CAN bus / display probes |
| `ndr_probe`, `ndr_probe_v2`, `NavigationNdrInfo` | navigation NDR probes |
| `fb_test` | framebuffer smoke test |
| `gemmi_proxy` | GEMMI map-tile proxy helper |

---

New here (this drop): `sh4-toolchain/`, `firmware-re/`, `prepare_usb.py`. See
each subfolder's README for build/usage detail.
