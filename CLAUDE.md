# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PCM-Forge generates activation codes and USB-based diagnostic/tooling payloads for the
**Porsche PCM 3.1** infotainment head unit (Harman Becker, Renesas SH4A, QNX 6.3.2). The
project has three layers:

1. **`docs/index.html`** — the single-file web app served via GitHub Pages
   (dspl1236.github.io/PCM-Forge). Runs entirely client-side: computes the RSA-64 activation
   codes, builds `PagSWAct.002`, and assembles USB sticks (activation, diagnostics, and the
   modular toolkit) as downloadable/saved files. No server, no build step.
2. **`modules/`** — the toolkit catalog. Each subfolder is a self-contained USB module
   (`module.json` + `scripts/` + optional `bin/`) that the web app fetches at build time via
   `docs/app/manifest.json`.
3. **`research/`, `tools/`, `PCM4/`** — the reverse-engineering side: how the activation
   algorithm and firmware were cracked, plus the host-side scripts used to do it. `PCM4/` is a
   parallel, self-contained RE effort for the newer MIB2-based PCM 4 (different platform,
   different unlock chain — see `PCM4/README.md`).

There is no build system or package manager. The web app and the module scripts are
validated by reasoning and by running them; `generate_codes.py` has a pytest suite in
`tests/` (`python -m pytest tests/ -q`), which also guards its byte-for-byte parity with the
web app and checks the algorithm against genuine factory codes in
`research/firmware/PagSWAct.csv`. Run it after touching either side.

## Working with the web app (`docs/index.html`)

Single ~1300-line HTML file: markup, CSS, and JS all inline, no bundler. Four tabs — Activation
Codes, USB Stick Builder, Toolkit, Backup. To preview, just open the file in a browser (or
serve `docs/` with any static file server) — nothing to compile.

**After adding/removing/editing a module in `modules/`, regenerate the manifest:**
```sh
python builder/generate_manifest.py
```
This rewrites `docs/app/manifest.json` from the `modules/` and `core/` trees — the web app
reads this manifest at runtime to know what files exist and fetches them from
`raw.githubusercontent.com`. Forgetting this step means new/changed module files are invisible
to the deployed app even though they're committed.

**Never publish `copie_scr.sh` (in `core/`) as a raw download.** The PCM's `proc_scriptlauncher`
autorun requires a specific XOR-encoded form that only the web app generates on the fly — a raw
copy from the repo will not trigger.

## Working with modules (`modules/*/module.json`)

Each module's `module.json` drives both the manifest and the toolkit UI. Key fields:
`status` (`ready`/`tested`/`alpha`/`experimental`/`paused`/`deprecated` — surfaced verbatim in
the UI), `standalone`, `run_script` + `script_dir` (where the module's entry script lands on
the USB stick / in the PCM's script path), `installs_to_flash` (should almost always be
`false` — see safety notes below), `compatible`, and an optional `options` block for
build-time-configurable module behavior (select/text inputs rendered in the web UI).

Dev-side sources for the shipped module scripts (C sources, build scripts, engineering-mode
`.esd` definitions) live in matching `tools/` subfolders (e.g. `tools/service-reset/`,
`tools/ioc-probe/`), not inside `modules/` itself — `modules/` holds only what gets shipped to
the USB stick.

## Building on-car binaries (`tools/sh4-toolchain/`)

QNX SH4 executables for the PCM are cross-compiled with the stock Linux `sh4-linux-gnu`
toolchain (no QNX SDK needed) via SONAME stub libs + a minimal `crt.S` that get rebound to the
unit's real (symbol-stripped) `libc.so.2`/`libgf.so.1` at load time:
```sh
./build.sh app_oil.c    # -> QNX SH4 LE ELF, run from USB or telnet as root
```
Everything built this way runs from RAM only; a reboot always reverts to stock.

## Firmware extraction/analysis (`tools/firmware-re/`, `PCM4/tools/`)

These operate on firmware packages/images the user supplies themselves — none are
redistributed in the repo. Chain: `.rar` update package → decompress the IFS
(`PCM4/tools/lzo1x.py`, pure-Python LZO1X, shared across both the PCM 3.1 and PCM 4 sides) →
carve the target ELF (`carve_pcm3root.py` for PCM 3.1, `PCM4/tools/*.py` for MIB2) → analyze.
See each tool's own `--help`/docstring; `tools/README.md` and `PCM4/tools/README.md` index them.

## Activation code generation (`generate_codes.py`)

Standalone CLI, no dependencies beyond stdlib:
```sh
python generate_codes.py <VIN>                       # list all 27 codes (911 model default)
python generate_codes.py <VIN> <USB_PATH>             # build an activation stick
python generate_codes.py --diag <USB_PATH>            # build a diagnostic stick (no VIN needed)
python generate_codes.py --show <PATH>                # decode an existing PagSWAct.002
python generate_codes.py <VIN> <USB_PATH> --from-backup --add TEL   # edit the car's own set
python generate_codes.py --list-models                 # show all model keys
```
The RSA-64 keys (`N`, `E`, `D`) and per-feature SWID/SubID tables live at the top of the file.
The ksh payloads the stick carries live in `payloads/` as real `.sh` files, so
`.gitattributes` keeps them LF; `copie_scr.sh` is generated and XOR-encoded at write time.
`pcm_forge_offline.py` is a Tkinter window over the same functions (codes, activation and
diagnostic sticks, reading a returned stick), packaged as `PCM-Forge-Offline.exe` by
`pcm_forge_offline.spec` + `.github/workflows/build-offline.yml` (rolling `offline-latest`
release); `tests/test_offline_app.py` holds it byte-identical to the CLI.
`tools/prepare_usb.py` is an older, narrower wrapper around the same algorithm and predates
all of the above. The algorithm write-up is in
`research/ALGORITHM_CRACKED.md`; the full feature list with costs/hardware requirements is in
`FEATURES.md`.

## Safety-critical conventions

- **Line endings matter functionally, not just stylistically.** `.gitattributes` forces LF on
  `*.sh` — the PCM's QNX shell chokes on CRLF, and the web app serves these scripts raw to the
  head unit. Never let an editor or `git config core.autocrlf` silently convert a shipped
  script.
- **Extensionless binaries under any `bin/` directory are forced `binary` in `.gitattributes`**,
  as are `*.so`/`*.bin`/`*.elf`/`*.o`/`.zip`. These are firmware/driver blobs or SH4 executables
  destined for the head unit — a single corrupted byte from line-ending conversion can brick a
  car's PCM. Don't add new binary-payload extensions without a matching `.gitattributes` rule.
- **`installs_to_flash` in a `module.json` should stay `false`** unless a module is deliberately
  and carefully designed to write persistent flash state — the project's default posture is
  RAM-only, reboot-reverts tooling. Treat any module setting this `true` as requiring extra
  scrutiny.
- Research/tooling here targets the user's own vehicle; don't add functionality whose only
  purpose is mass/unauthorized access to vehicles the user doesn't control.

## Two unrelated head-unit generations — don't cross-apply findings

`PCM 3.1` (this repo's primary target: SH4A/QNX 6.3.2, RSA-64, factored trivially) and
`PCM 4` / MIB2 (`PCM4/` subtree: Tegra 3 + TI DRA6xx + Renesas V850, RSA-1024 that's
cryptographically sound — the MIB2 unlock instead goes through factory engineering scripts and
a root shell, see `PCM4/handoff/UNLOCK_PLAYBOOK.md`) are different platforms with different
attack surfaces. Firmware formats, offsets, and activation mechanics from one do not transfer
to the other; `PCM4/` is intentionally kept as a near-independent subtree (own `README.md`,
own `.gitignore`, own tools) rather than merged into the top-level `research/`/`tools/`.
