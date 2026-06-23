# PCM4 / MIB2 — Practical Unlock Playbook

Actionable companion to `research/MIB2_ACTIVATION_RESEARCH.md`. Distills 12 sessions of
analysis into "how you actually unlock features." Labels **[CONFIRMED]** (from firmware)
vs **[NEEDS BENCH]** (validate on hardware).

---

## 0. The one-sentence model
The activation crypto (FEC/FSC = RSA-1024 e=3 verified with **OpenSSL strict PKCS#1** —
**not forgeable**) is a solid wall, BUT the factory ships a complete **GEM engineering
script library** that writes the activation/coding bits *directly*, skipping the crypto.
So: **get a root shell → run the factory scripts → features unlock.** No FSC, no VIN, no
filesystem rewrite.

---

## 1. What's possible / not
- ✅ **Unlock offline features** (nav, CarPlay, Android Auto, MirrorLink, picture-nav,
  cluster map, RVC, station logos, 2nd phone, messaging) — coding bits only, **no VIN**.
- ✅ **Unlock online/connected features' coding** (live traffic/VZO/LGI, online POI,
  Google Earth/Street View, online dictation, WiFi hotspot, OTA) — but the **backend
  validates the car's VIN**; needs the real provisioned VIN or the `UseFakeVin` spoof,
  plus a working modem/SIM. [NEEDS BENCH for the online backend behavior]
- ✅ **Persistent** — coding bits live in writable flash (efs-persist / persistence DB);
  survive reboot; one-time per car.
- ❌ **Forge an official FSC** — FEC verify = OpenSSL RSA_verify, strict padding. Closed.
- ⚠️ **ExceptionList FSC whitelist** — guarded by **MD5** (broken). Populating
  `[SupportedFSC]` + recomputing the 8 MD5 sigs *may* whitelist FSCs without RSA.
  Depends on whether the MD5 is plain or keyed. [NEEDS BENCH / more RE]

---

## 2. Access vectors (pick one to get the root shell)
| Vector | Needs | Use case |
|---|---|---|
| **SD/USB SWDL "toolbox"** (CVE-2020-28656) | crafted SD/USB | **End-user delivery** — no network, no password, no teardown |
| **Telnet :23** | OABR/Ethernet adapter + root pw (`/etc/shadow_rcc` = `root:88PTlG6BPJk6M`, DES — recoverable/likely default) | Bench/installer |
| **qconn :8000** | OABR/Ethernet adapter, NO password | Bench (may be engineering-mode only) |
| **Serial** | open unit, UART /dev/ser1, `login root` | Lab |

Network: RCC defaults to **en0 = 172.16.250.247/24** (DHCP optional) on the OABR/diagnostic
Ethernet. MMX↔RCC are one **QNET** cluster — a shell on either drives both via `on -f`.

---

## 3. SD-card SWDL toolbox path (the consumer route) — CVE-2020-28656 [CONFIRMED vector]
**The real bug** (Context IS disclosure, confirmed identical on this Porsche firmware,
Session 13): the metainfo parser reads the file end-to-end, but the MetafileChecksum/RSA
signature only covers **[start→MetafileChecksum line] + [after it→`[Signature]` line]**.
**`[Signature]` is the LAST section in our metainfo2.txt**, so anything **appended after
`signature8` is parsed but NOT signed.**

Recipe (the toolbox):
1. Start from a **legitimately-signed** Porsche/MHI2 update (keeps the signed region intact).
2. **Append a new `[…\File]` section AFTER `signature8`**:
   ```
   [Toolbox\X\0\default\File]
   Source = "../relative/path/to/evil_on_card"
   Destination = "<a privileged root-run script path on the unit>"
   FileSize = "..."  CheckSumSize = "524288"  CheckSum = "<sha1 of evil>"
   ```
   (The appended section is self-consistent and outside the signed byte ranges, so the
   original signature still verifies.)
3. Put `evil_on_card` on the SD. On "perform update", the parser copies it over the target
   → on apply it runs as **root** → it executes the §4 GEM activation commands.
- No crypto break, no pre-existing shell, no FS rewrite. Delivery = insert SD, run update.
- [NEEDS BENCH]: pick the live target script (scriptPre/scriptPost vs finalScriptSequence)
  and confirm the customer-mode apply flow. Note `UserSwdl=true` skips the *finalScript*,
  so target a pre/post or a component script that runs in customer mode.

---

## 4. The activation step (run these once you have root)
All are FACTORY scripts at `/eso/hmi/engdefs/scripts/` (present on every unit). Each calls
`navpre.sh` first (remount RW). Examples — run the script OR the underlying command:

```sh
# remount RW (prereq for the flag-file scripts)
/eso/hmi/engdefs/scripts/navpre.sh

# Navigation (FSID flag)
/eso/hmi/engdefs/scripts/naviAppEnable.sh        # touch /navigation/FSID_Navi_Enabled

# Apple CarPlay / Android Auto / MirrorLink
/eso/hmi/engdefs/scripts/activate_CarPlay.sh
/eso/hmi/engdefs/scripts/activate_AndroidAuto.sh
/eso/hmi/engdefs/scripts/activate_MirrorLink.sh

# Coding-bit features (MMX persistence; partition 0xC0040114 = 3221356628)
/eso/bin/dumb_persistence_writer -P -L 1 -O 70 0 3221356628 80   # OTA
/eso/bin/dumb_persistence_writer -P 0 3221356674 01              # mobile online
# (full offset map in research doc Session 4b)

# RCC variant-coding (run on RCC, or via QNET from MMX)
on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc Online_Navi__Google_Earth 1   # Google Earth/StreetView
on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc VZO 1                         # live traffic
on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc WIFI_Hotspot 1
on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc Picture_Navi 1
# full settable list: research doc Session 4b

# Global FEC kill switch (optional, nav layer)
/eso/hmi/engdefs/scripts/fec_off.sh              # rm USE_FEC / USE_FEC_SIG
/eso/hmi/engdefs/scripts/disablesigcheck.sh      # defeats map-DB content.sig

# system reset to apply
mount -uw /mnt/system; touch /etc/ooc.allow.reset; echo hmi-sys-reset > /dev/ooc/reset
```

VIN: **not required** — the unit uses its own factory-coded VIN; the bypass writes the
downstream bits. Online services are the exception (backend VIN check → `activateUseFakeVin.sh`).

---

## 5. Verify / revert
- Verify: `dumb_persistence_reader` reads back coding bits; ESD/GEM "SWaP" menu shows state;
  feature appears after restart.
- Revert: each `activate_*` has a `deactivate_*`; `naviAppRestoreDefault.sh` returns to
  FEC control; `fec_on.sh` / `enablesigcheck.sh` restore enforcement.

---

## 6. Status of unknowns (for next sessions / bench)
1. SD-card SWDL trigger + whether finalScriptSequence runs in customer mode.
2. ExceptionList MD5 scheme (plain vs keyed) → is the FSC-whitelist route viable?
3. Online-services VIN behavior + `UseFakeVin` exact writes.
4. Whether qconn auto-starts on retail (telnet is the confirmed auto-started vector).
