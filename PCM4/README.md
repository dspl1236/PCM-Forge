# PCM4 / MIB2 — Feature Activation Research

Reverse-engineering of the **Porsche PCM 4** (Harman **MIB2 "High"**) feature-activation
system. Continuation of the [PCM-Forge](https://github.com/dspl1236/PCM-Forge) (PCM 3.1)
and [MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit) (Audi/VW MMI3G+) projects.

> **Security / right-to-repair research.** This repository contains **documentation and
> analysis tooling only** — no proprietary Harman/VAG firmware or extracted binaries are
> distributed. Run the tools against your own firmware. See **[Disclaimer](#disclaimer)**.

---

## TL;DR

- **Platform:** Harman MIB2 High. Three processors:
  - **MMX** (main HMI/nav) — QNX 6.5.0 SP1 on **NVIDIA Tegra 3** (ARM Cortex-A9)
  - **RCC** (radio/media "HW31") — QNX on **TI DRA6xx (Jacinto)**, ARM
  - **IOC** (CAN/power) — **Renesas V850**
- **Activation** = VAG **FEC / SWaP**, **RSA-1024, e=3**, verified with **OpenSSL strict
  PKCS#1** → signatures (FSCs) are **not forgeable**.
- **The crypto was never the lock.** The firmware ships a complete factory **GEM
  engineering script library** that writes the activation/coding bits *directly*
  (`dumb_persistence_writer`, `VIPCmd ee vc`, FSID flag files, `fec_off.sh`). With a root
  shell you run the manufacturer's own scripts — no FSC, **no VIN**, no filesystem rewrite.
- **Getting that shell:** the RCC exposes **telnet / qconn / serial** (bench/network), and
  for end-users the **SD-card software-update path** is exploitable via the publicly
  disclosed **CVE-2020-28656** (append-after-`[Signature]` in the metainfo file).

Full detail in **[docs/FINDINGS.md](docs/FINDINGS.md)**.

---

## Repository layout

```
docs/
  FINDINGS.md        Technical findings, by topic (start here)
  FILE_FORMATS.md    Reverse-engineered formats: QNX IFS/EFS, LZO framing, metainfo, UPD
  CODING_MAP.md      Per-feature coding reference (VIPCmd / persistence / flag files)
research/
  MIB2_ACTIVATION_RESEARCH.md   Full session-by-session research log (source of truth)
handoff/
  UNLOCK_PLAYBOOK.md  The end-to-end practical chain (access -> root -> activate)
tools/
  lzo1x.py           Pure-Python LZO1X decompressor (kernel-faithful)
  ifs_extract.py     QNX6 IFS (LZO, big-endian block-framed) unpacker
  efs_extract.py     QNX EFS / F3S (UCL/LZO, little-endian) unpacker + UCL NRV2B
  enumerate_elfs.py  Scan/fingerprint the uncompressed ELFs inside app.img
  extract_persistence_pair.py / carve_rcc_bins.py  targeted ELF carvers
```

Not included (proprietary / large / generated): the firmware image, extracted binaries,
decompressed filesystems, Ghidra projects. See `.gitignore`.

---

## Tools

Pure-Python, no external deps (developed because `python-lzo`/`libucl` won't build on
the maintainer's Windows + Py3.14). Set the firmware path at the top of each script.

| Tool | Purpose |
|------|---------|
| `lzo1x.py` | LZO1X decompressor (faithful port of the Linux kernel `lzo1x_decompress_safe.c`) |
| `ifs_extract.py` | Decompress + walk a QNX6 IFS (e.g. RCC `ifs-root.ifs`) |
| `efs_extract.py` | Decompress + walk a QNX EFS/F3S flash image (e.g. RCC `efs-system.efs`); includes a pure-Python **UCL NRV2B** decompressor |
| `enumerate_elfs.py` | Locate the 788 uncompressed ARM ELFs in `app.img` by header |

---

## Platform & datasheets

| Unit | SoC | Reference |
|------|-----|-----------|
| MMX (HMI/nav) | NVIDIA Tegra 3 (T30), Cortex-A9 | Tegra 3 TRM; ARM Cortex-A9 r4p1 TRM |
| RCC (radio) | TI DRA6xx (Jacinto) | TI DRA6xx TRM |
| IOC (CAN/PM) | Renesas V850 | Renesas V850E2 family |

---

## Prior art & credits

- **Context Information Security** — *"A code signing bypass for the VW Polo"* (CVE-2020-28656),
  the metainfo signature-bypass this work confirms on the Porsche/MHI2 variant.
- **jtang613/qnx_dumpers** — `efsdump`, the QNX EFS/F3S format reference our extractor is ported from.
- **dspl1236/MMI3G-Toolkit**, **dspl1236/PCM-Forge** — the predecessor projects.
- **Linux kernel** `lib/lzo/lzo1x_decompress_safe.c` — the LZO1X reference implementation.
- The **MHH Auto** and **Rennlist** communities; `unbe/mmi-ifs`; `korni92/FIS-Writer`.

---

## Disclaimer

This is independent **security/reverse-engineering research** and documentation, published
in the spirit of right-to-repair and owner control of hardware.

- Activate features only on units **you own**. Some connected/online services require a
  valid subscription and/or vehicle provisioning **regardless** of local coding.
- **No proprietary firmware or extracted binaries** are included in this repository.
- **CVE-2020-28656** is a **publicly disclosed** vulnerability (reported to Volkswagen and
  documented by Context IS; addressed in later firmware). It is referenced here as prior
  published research, not novel weaponization.
- Provided for educational purposes, **as-is, without warranty**. You are responsible for
  complying with the laws and licenses applicable to you.
