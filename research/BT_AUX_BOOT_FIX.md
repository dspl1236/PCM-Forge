# PCM 3.1 BT / AUX Boot Fix — Universal FM→A2DP Patch

## Status

**Working, offline-validated across the firmware matrix; on-car confirmation pending.** A single byte in `PCM3Root` decides whether a phone connected at startup plays over Bluetooth or gets dropped to FM radio. Flipping it routes the source to **A2DP** instead of **FM**. Because the instruction is byte-identical across every build (only its address moves), one signature-based patcher covers **every region / model / firmware from v2.00 up**.

Credit: this builds directly on **[WillCoder / PCM_31_AUX-BT](https://github.com/WillCoder/PCM_31_AUX-BT)**, who found the fix and the `/proc/<pid>/as` patch primitive. His delivery was an IFS reflash (which bricked two bench units); this module reimplements the same fix as a universal, brick-safe **runtime** patch.

## The bug

`PCM3Root` carries the string:

```
%s Fallback from A2DP to TUNER_FM!
```

When the Bluetooth stack is slow to come up at startup, the presentation controller falls back to `eSRC_TUNER_FM` — and there is **no retry-to-BT** once Bluetooth finishes connecting. It stays on FM (and, since volume is persisted, often at full volume). The relevant source enum values:

| Source | Enum value |
|--------|-----------|
| `eSRC_TUNER_FM` | **1** |
| `BT_A2DP` | **7** |

A source-routing map stores the FM index (`1`) for the BT-connected state. That stored `1` is the whole bug.

## The fix — one byte

Change the stored source index from FM (`1`) to A2DP (`7`). In SH4 the instruction that writes it is `mov #1, r1`; flipping the immediate makes it `mov #7, r1`:

```
before:  mov #1, r1     bytes: 01 e1      (stores FM index 1)
after:   mov #7, r1     bytes: 07 e1      (stores A2DP index 7)
```

Only the single immediate byte `0x01 → 0x07` changes. Nothing else moves.

## Universal signature (why it works on every car)

Hardcoding an address is fragile — it differs per build. Instead we locate the instruction by a **unique 6-byte signature** and patch whatever address it sits at:

```
signature :  05 1e 01 e1 15 1e
decode    :  mov.l r0,@(5,Rn) ; mov #1,r1 ; mov.l r1,@(5,Rn)
patch     :  the byte at signature offset +2   (0x01 -> 0x07)
```

The `01 e1` in the middle is the `mov #1,r1` that loads the FM index; the surrounding store instructions make the match unique within `PCM3Root`'s own code.

## Tested matrix

Extracted `PCM3Root` from Porsche update packages (`PCM31<REGION><VER>.rar`), then scanned for the signature:

| Firmware | Region | Model / trim | FM-map address | Byte | Result |
|----------|--------|--------------|----------------|------|--------|
| v4.00 | CHN (China) | 991 (9x1) facelift | `0x082b65e0` | `0x01` | patch |
| v4.00 | CHN (China) | 991 (9x1) pre-facelift | `0x082b65e0` | `0x01` | patch |
| STEP 9.6 | ARB (Arabic) | Cayenne (generic) facelift | `0x082b2a74` | `0x01` | patch |
| v4.00 | RDW (USA / RoW) | Cayenne (generic) facelift | `0x082b2a78` | `0x01` | patch |
| v2.00 (2014) | CHN (China) | generic | `0x08297f48` | `0x01` | patch |
| v1.00 (2013) | RDW (USA / RoW) | generic | — | — | **no-op** (see below) |

Observations:
- The **address clusters by model** — `9x1` lands at `0x082b65e0`, the generic (Cayenne/Panamera) build around `0x082b2a7x` — and shifts slightly by region. A hardcoded address would be wrong on most of these; the signature finds it every time.
- Even between **v2.00 and v4.00** the code *around* the store drifted (the bytes after it differ), but the 6-byte signature itself stayed identical and unique — so the patch tracks the instruction, not the layout.

Regional packages seen locally: **ARB** 300/400, **CHN** 100–400, **LOW** 400, **RDW** 100–400. Models per package: generic (Cayenne/Panamera), `9x1` (991/981), Macan; each in pre-facelift and facelift (MOPF) variants.

## The v1.00 exception

The 2013 launch firmware (`v1.00`) has **no `Fallback from A2DP to TUNER_FM` string and no signature match** — the fallback behaviour was introduced in a later update (present by v2.00). There is nothing to patch, so the patcher **safely does nothing**. A v1.00 unit should simply be updated first (which gives it the map). This is also the safety backstop: on any unrecognized build, the tool finds no signature and makes no change.

## Reproducing on any firmware

```
PCM31<REGION><VER>.rar                     # Porsche field-update package
  └─ PCM3_IFS1[_MOPF][_model].ifs          # the application IFS (LZO1X inside Harman hbcifs)
      └─ inflate  (research tooling)        # -> raw QNX imagefs
          └─ carve SH4 ELF "PCM3Root"       # verify: CPSoundPresCtrl + the fallback string
              └─ scan for  05 1e 01 e1 15 1e
                  └─ byte at +2 == 0x01     # this is the FM index to flip
```

The IFS uses LZO1X compression; decompress with the repo's inflate tooling, then carve the `PCM3Root` ELF (a ~6 MB SH4 LE binary — confirm it contains `CPSoundPresCtrl`, `CAudioMngPersistence`, and the fallback string before trusting it).

## Delivery — brick-safe runtime patch

The fix ships as a self-locating runtime patcher (`bin/bt_fix`), not a reflash:

- **Runtime patch** — writes `PCM3Root`'s *live* memory via `/proc/<pid>/as`. A reboot restores the stock flash image. The read-only firmware is never touched, so it **cannot brick**.
- **Self-locating** — scans `PCM3Root`'s own code range `[0x08040000, 0x08700000]` for the signature (its image loads at a fixed vaddr, non-PIE), so no per-build address is needed.
- **Fail-safe** — writes **only** when it finds *exactly one* signature match **and** the current byte is `0x01`. Zero matches (v1.00 / unknown build) or more than one → no write.
- **Modes** — *Runtime* (one-shot; reverts on reboot) or *Persistent* (a `/HBpersistence` boot hook re-applies each boot; reversible via the uninstall script).

## Credits

**WillCoder — [github.com/WillCoder/PCM_31_AUX-BT](https://github.com/WillCoder/PCM_31_AUX-BT)** built the original fix on a bench, and provided the pieces this module stands on: the `/proc/<pid>/as` byte-patch primitive (`mempoke`), the IFS LZO inflate/deflate pipeline, and an SH4 emulator for offline validation. His flash route was powerful but risky (two bench units lost to watchdog loops); PCM-Forge's contribution is turning it into a signature-located, fail-safe, brick-safe runtime patch that works on any PCM 3.1 without a flash.
