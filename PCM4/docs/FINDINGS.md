# PCM4 / MIB2 — Technical Findings

Topical summary of the research. The chronological detail is in
[`research/MIB2_ACTIVATION_RESEARCH.md`](../research/MIB2_ACTIVATION_RESEARCH.md); the
practical chain is in [`handoff/UNLOCK_PLAYBOOK.md`](../handoff/UNLOCK_PLAYBOOK.md).

Firmware analyzed: `MHI2_ER_POG24_K5137_MU1417_971919360T` (Panamera 971919360T, Harman,
variant `FM2-P-N-EU-PO-MLE`).

---

## 1. Platform architecture

| Unit | Role | CPU / OS | Image |
|------|------|----------|-------|
| **MMX** | Main HMI, navigation, multimedia, SWaP logic | **NVIDIA Tegra 3** (ARM Cortex-A9), **QNX 6.5.0 SP1** | `MMX2/app/50/default/app.img` (716 MB; 788 uncompressed ARM ELFs) |
| **RCC** | Radio, media, CAN ("HW31") | **TI DRA6xx (Jacinto)**, ARM, QNX | `RCC/ifs-root/31/default/ifs-root.ifs` (LZO IFS) + `efs-system.efs` (EFS) |
| **IOC** | CAN bus, power mgmt | **Renesas V850** | `IOC/Main/31/default/V850app_MLBPO.bin` |

MMX and RCC form a **QNX QNET cluster** — a shell on either node runs commands on both via
`on -f mmx …` / `on -f rcc …`.

(Earlier notes assumed "ARM Linux" / 2048-bit RSA / SH4 RCC — all corrected during the work:
the MMX is QNX, FEC RSA is 1024-bit, the RCC is ARM/Jacinto.)

---

## 2. The activation system (FEC / SWaP)

VAG **FEC** (Feature Enabling Code = *FreischaltCode*) / **SWaP** (Software as Product):

- A signed **FSC** unlocks a feature, identified by an **FSID**. Runtime record:
  `@dsi.swap.SFscDetails = { swid, state, version, vin, date }`.
- **FecManager** (the validator) imports FSCs, checks them, and pushes per-FSID states
  (`include/ignore fsid [0x..] fecState [..]`) to client apps over DSI.
- Content packages (nav map DBs) embed an FSC-ID and are gated by a `FecChecker`.
- No static FSID→feature table exists in firmware (`fecconfig.ems_table.json = {}`);
  the per-unit activation state lives at runtime in `efs-persist`.

### Cryptography (the wall)
- All FEC / Data / Metainfo keys are **RSA-1024, public exponent e=3**, stored per-OEM
  (AU/BY/**PO**/SE/SK/VW) as 288-byte `[ n(128) | e(32)=3 | sig(128) ]` blobs in
  `efs-system/backup/Keys/{FECKey,DataKey,MetainfoKey}/`.
- Verification uses **OpenSSL `libcrypto.so.2`** (`RSA_verify` / `EVP_VerifyFinal` with
  `RSA_padding_check_PKCS1_type_1`) — **strict PKCS#1 v1.5**.
- ⇒ The `e=3` weakness does **not** enable Bleichenbacher forgery here; **FSCs cannot be
  forged.** (The only hand-rolled RSA, `cryptolib/rsa.c`, is for **Tegra secure-boot (BCT)**
  signing — unrelated to activation.)

---

## 3. The bypass (why the crypto doesn't matter)

The firmware ships the complete factory **GEM engineering script library**
(`/eso/hmi/engdefs/scripts/`, ~568 scripts) that writes the activation/coding bits
*directly*, downstream of the FEC crypto. Four independent layers:

1. **File-flag toggles** — `touch`/`rm` flags like `/navigation/FSID_Navi_Enabled`
   (`naviAppEnable.sh`).
2. **`dumb_persistence_writer`** — writes coding bits straight into the persistence DB
   (partition `0xC0040114`), e.g. online services, OTA, picture-nav, cluster mode.
3. **`VIPCmd ee vc <feature> 1`** — the RCC factory variant-coding channel
   (Online_Navi__Google_Earth, VZO, WIFI_Hotspot, Picture_Navi, LTE_Modul, …).
4. **Global FEC kill switches** — `fec_off.sh` (remove `USE_FEC`/`USE_FEC_SIG`),
   `disablesigcheck.sh` (move map `content.sig` aside).

These are the **manufacturer's own scripts**. The bypass is simply running them from a root
shell instead of the locked engineering menu. **No FSC, no VIN, no filesystem rewrite** —
the bits live on writable flash. The complete per-feature command set (32 VIPCmd features,
13 persistence writes, 22 flag files) is in [`CODING_MAP.md`](CODING_MAP.md).

**VIN note:** offline features ignore the VIN (the unit uses its own factory-coded VIN, and
the bypass skips the FEC's VIN check). Only **online/connected** services are VIN-bound at
the *backend* — hence the `activateUseFakeVin.sh` spoof script.

---

## 4. Getting root (access vectors)

| Vector | Needs | Notes |
|--------|-------|-------|
| **SD-card software update** | crafted SD card | **CVE-2020-28656**, §5 — end-user delivery |
| **Telnet :23** | diagnostic Ethernet + root password (`/etc/shadow_rcc` = `root:88PTlG6BPJk6M`, DES — recoverable / likely a known fleet default) | inetd-launched, runs as root |
| **qconn :8000** | diagnostic Ethernet, no password | QNX remote-exec; may be engineering-mode-only |
| **Serial console** | UART `/dev/ser1` | `login root` |

The RCC defaults to **`en0 = 172.16.250.247/24`** (DHCP optional) on the OABR/diagnostic
Ethernet; `inetd` is started at boot (`srv-starter.cfg`).

### Diagnostic (OBD) coding — a no-root route
`diag_server.elf` (the DSI diagnostic system) has **`SystemDiagModuleThread::handleUpdateCoding`**
— it applies coding bytes received over **UDS/SDIS** (the ODIS/OBD channel). **SFD is NOT
enforced** on this 2018 build (no SFD lock/token strings — the MY2020+ protection doesn't
apply). So the standard OBD variant-coding route (OBDeleven/VCDS/VCP-style) is the cleanest
delivery for the ~32 `VIPCmd ee vc` features — **no root, no SD card**. The exact
SecurityAccess gating is a bench/OBD-tool item. Nav (FSID) + FEC-licensed features still
need GEM/root or a real FreischaltCode.

**Three deployment tiers (none require forging crypto):**

| Route | Root? | Hardware | Best for |
|-------|-------|----------|----------|
| OBD diagnostic coding | No | OBD dongle | variant-coded features (pre-SFD) |
| SD-card SWDL (CVE-2020-28656) | No | SD card | broad changes / scripts |
| Root shell (telnet/qconn/serial) | Yes | bench/adapter | everything, full control |

---

## 5. SD-card delivery — CVE-2020-28656 (confirmed on this firmware)

The metainfo parser reads the file **end-to-end**, but the `MetafileChecksum` (SHA1, RSA-
signed) only covers two byte ranges: `[start → MetafileChecksum line]` and
`[next line → "[Signature]" line]`. **`[Signature]` is the last section** in this
firmware's `metainfo2.txt` (8 hex pairs = a 128-byte RSA-1024 signature).

⇒ **Content appended after `signature8` is parsed and applied but never validated.** An
attacker appends a `[…\File]` section with `Source=`/`Destination=` to drop an
attacker-controlled file (e.g. overwrite a privileged script run during the update) →
executed as **root**. No crypto break, no shell required, no teardown.

Confirmed here: identical metainfo layout; carved verifier (`metainfo_verify.elf`) with the
`Count of hex chars should be 128` / `[Signature] not found` strings; the signature-block
assembler (`FUN_0020ab04`) matches the disclosed logic exactly. Picking the live target
script and confirming the customer-mode apply flow are bench-validation items.

**Affected range (verified against a newer build):** a later firmware
(`MH2p_ER_POG35_K9829`, Cayenne, Dec 2018) **replaced this design** with JSON manifests +
a **detached signature over the whole checksum file** (`main.mnf_cks_S.sig` →
`SignedFile = "main.mnf.cks"`) — closing the append gap. So this vector is specific to the
older inline-`[Signature]` design. The activation/coding mechanism, Tegra/QNX platform, and
RSA-1024 crypto carry over to the newer build. See [`FIRMWARE_COMPARISON.md`](FIRMWARE_COMPARISON.md).

---

## 6. Reusable artifacts produced

- Pure-Python unpackers for the QNX **IFS (LZO)** and **EFS/F3S (UCL/LZO, little-endian)**
  formats, plus a kernel-faithful **LZO1X** and a **UCL NRV2B** decompressor (`tools/`).
- Format documentation: [`FILE_FORMATS.md`](FILE_FORMATS.md).
- A working **headless Ghidra** workflow for the ARM/QNX binaries.

---

## 7. Status

**Understood (from firmware):** platform, activation architecture, the GEM bypass + exact
per-feature commands, the crypto (unforgeable), all access vectors, the SD-card metainfo
vector.

**Needs a bench unit:** live telnet/qconn confirmation; the exact SD-card target script +
customer-mode apply flow; online-services VIN behavior; whether the `ExceptionList.txt`
`[SupportedFSC]` whitelist is a viable no-shell route — note its 8×16-byte trailer is an
**RSA-1024 signature** (same format as the FEC/update sigs), *not* an MD5 hash, so it
cannot be regenerated offline.

**Firmware B (Cayenne MMX2P) — also needs a bench unit / new tooling:** the RCC moved to
DRA74x with a different IFS container (our LZO walker doesn't apply) and `mifs-stage2`
moved to LZ4, so RCC root-vector confirmation and GEM script-library enumeration on that
build are not statically reachable with the current tools. See
[`FIRMWARE_COMPARISON.md`](FIRMWARE_COMPARISON.md).
