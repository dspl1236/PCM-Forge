# PCM4 / MIB2 — Cross-Firmware Comparison

Comparing two Porsche MIB2 firmware generations to establish what's version-specific
vs. what generalizes — in particular the affected range for CVE-2020-28656.

| | **Firmware A (baseline)** | **Firmware B (newer)** |
|---|---|---|
| Release | `MHI2_ER_POG24_K5137_MU1417` | `MH2p_ER_POG35_K9829_MU0105` |
| Model / part | Panamera 971 (`971919360T`) | Cayenne 9Y0 (`9Y0919360B`) |
| Platform tag | MHI2 / MMX2 | **MH2p / MMX2P** (bigger: ~2 GB app vs 716 MB) |
| Approx. date | ~early 2018 | 2018-12 |
| MMX SoC / OS | NVIDIA Tegra + QNX (Quickboot) | NVIDIA Tegra + QNX (Quickboot) — same family |

## Update signing — the key difference (CVE-2020-28656)

**Firmware A (vulnerable):** flat `metainfo2.txt` with an **inline `[Signature]`** section.
The integrity SHA1 covers only two byte ranges (`start→MetafileChecksum` and
`→[Signature]`), so content appended after `[Signature]` is parsed but unsigned →
append a `[…\File]` section to drop a root-run file. (See FINDINGS §5.)

**Firmware B (fixed):** JSON manifests with a **detached signature**:
```
Meta/multi.mnf                 (top-level, JSON)
Meta/SWUP_*/main.mnf           (per-package, JSON)
Meta/SWUP_*/main.mnf.cks       (SHA1 of every package, JSON)
Meta/SWUP_*/main.mnf_cks_S.sig (detached signature)
   [Header] SignedFile = "main.mnf.cks"  TypeOfSignature = "Serie"
   [ECU-Signature] signature1..8  (8×16B = 128B = RSA-1024)
```
The signature now covers the **entire** `main.mnf.cks` (which lists all package
checksums). There is no parse-vs-validate range gap → **the append bypass is closed.**

⇒ **CVE-2020-28656 is older-firmware-only.** It applies to the inline-`[Signature]`
design (Firmware A era); the redesigned detached-signature scheme (Firmware B) fixes it.
Crypto strength is unchanged either way (**RSA-1024**, 8×16-byte signatures).

## What generalizes across both

- **Platform:** NVIDIA Tegra + QNX (Quickboot, `qnx-armv7`) on both.
- **Activation mechanism:** the GEM/coding layer is unchanged — `dumb_persistence_writer`
  and `/eso/hmi/engdefs/scripts` are present in both. (On MMX2P the script *library* lives
  in the compressed `mifs-stage2`; the `dumb_persistence_writer` binary + engdefs path are
  in `app.img`.) So once you have root, the same coding approach applies.
- **Update crypto:** RSA-1024 on both (not upgraded to 2048).
- **SFD:** not enforced on either build → the OBD diagnostic-coding route likely remains
  open across both.

## What changed in packaging (Firmware B deep-dig)

Direct extraction of Firmware B with our own unpackers turned up several packaging changes
that **don't affect the activation thesis** but are worth recording for anyone re-running
the tools against an MMX2P image:

- **MMX `/mnt/system` config partition extracts cleanly with our `efs_extract.py`.** The
  QNX **EFS/F3S** format is unchanged across generations — `MMX2P.efs-system` (`_CLU24_`
  variant) unpacked to 143 files rooted at `/mnt/system` (`etc/config/*.conf`,
  `etc/eso/presets/*.json`, `etc/db`). ⇒ **the EFS tooling generalizes.**
- **FEC config presets are logging-only.** `etc/eso/presets/fec.json` and
  `component_protection.json` only set trace/log levels (`"FEC":"info"/"debug"`) — no
  keys, FSID tables, or policy. The activation *state* still lives at runtime in
  `efs-persist`, as in Firmware A.
- **FEC public keys are no longer loose files.** Firmware A stored them as loose
  `efs-system/backup/Keys/{FECKey,DataKey,MetainfoKey}/…` blobs. Firmware B's
  `MMX2P.efs-system` is the `/mnt/system` config partition and contains **no** loose key
  files (`*_public_signed.bin` / `FECKey` search across the whole `Data/` tree = 0 hits).
  The keys moved into a packed image (the verifier/keys live with `FecManager` in MMX
  `app.img`). Crypto **format** (288-byte `n|e|sig`, `e=3`, RSA-1024) is a VAG-platform
  constant and the update signatures confirm RSA-1024 is retained — but the loose-file
  key-dump route from Firmware A does **not** apply to Firmware B.
- **The RCC IFS is repacked with a newer container.** Firmware A's RCC (DRA6xx) used a
  QNX IFS with standard `\x89LZO` + big-endian 64 KB LZO1X blocks — our `ifs_extract.py`
  walks it. Firmware B's RCC is **DRA74x (Jacinto 6)** and its `ifs-dra74x-vayu-evm.bin`
  does **not** decode under that framing: the only `\x89LZO`-like marker sits ~6.4 MB deep
  with a **non-standard signature** (`89 4C 5A 4F 00 0D 0A A9 1A` vs QNX's
  `89 4C 5A 4F 0D 0A 1A 0A`), and no LZO1X block framing (LE/BE × 16/32-bit length, sig
  offsets 6–20) yields a valid block. ⇒ the RCC build toolchain changed with the SoC.
  **Confirming the RCC root vectors (telnet/qconn/inetd) on Firmware B therefore needs a
  bench unit or a port of the new container** — it could not be confirmed statically here.
  This is a tooling gap, not a regression in the findings: the GEM bypass runs on the
  **MMX**, whose `app.img` (and thus `dumb_persistence_writer` + engdefs) is confirmed
  present in Firmware B.
- **`mifs-stage2` switched to LZ4.** Firmware B's `main_stage2.img` carries an `LZ4_`
  magic (vs the LZOZ chunked-LZO of Firmware A), so dumping the GEM *script library* on
  Firmware B would need an LZ4 decoder. The `dumb_persistence_writer` binary and the
  engdefs path remain in `app.img`, so this only blocks bulk script enumeration, not the
  mechanism.

## Net
The SD-card update vector is the one thing VW closed between these generations. The
underlying **activation/coding mechanism, platform, and crypto strength carry over**, so
the research generalizes — newer units just need a non-SD root vector (telnet/qconn/serial)
or the OBD coding path instead of the SD-card append.

What *did* change is **packaging**, not protection: the RCC moved to DRA74x with a newer
IFS container, the FEC keys moved out of loose EFS files into packed images, and
`mifs-stage2` moved to LZ4. None of these add a security control — they just mean some of
the Firmware-A static-extraction shortcuts (loose key dump, RCC IFS walk, script-library
enumeration) need updated tooling or a bench unit on MMX2P. The EFS config partition still
extracts with the existing tools.

_Comparison only — no proprietary firmware is included; analysis was run against
locally-held images._
