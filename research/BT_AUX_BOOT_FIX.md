# PCM 3.1 BT / AUX Boot Fix — Universal FM→A2DP Patch

> ## ⚠️ CORRECTED — the patch below does not fix the bug
>
> **Measured on a car (WillCoder, 2026-06-22): `PCM3Root` already held `0x07` at the
> patch site and the unit still booted to FM.** The byte-flip is inert. The
> `bt-aux-fix` module has been paused and offers only *Revert to stock*.
>
> **Why it cannot work.** The patched instruction lives in the **LastMode persistence
> handler**. On power-off the unit stores LastMode = **10 (Default)** — never 7 — and at
> boot `CPOnOffPresCtrl` (`0x08216940`) sees source 10, takes a `> 9` shortcut and
> branches away. The handler holding the patched byte is **never reached at startup**,
> so its contents are irrelevant.
>
> **The deeper reason, and the one that matters.** Bluetooth is not slow at boot; it is
> *not started at boot at all*. In the launcher config, package **20
> `PHONE_AND_BLUETOOTH` ships `RequestState=STOP`** — it is demand-started. The same is
> true of the Audi MMI (package 13 `PHONE`, also `STOP`). **No Harman platform of this
> era brings Bluetooth up during startup.** So when the source is chosen, A2DP genuinely
> does not exist, and falling back to FM is *correct behaviour*, not a defect. The actual
> defect is that **nothing re-evaluates the source when the phone connects seconds
> later**.
>
> **Read "at boot" strictly.** `RequestState=STOP` describes the *boot* request state,
> not a permanent one. Confirmed on the bench 2026-08-03: with terminal 30 only, no
> gateway and no ignition, pressing the power knob brings Bluetooth up and a phone
> pairs and connects normally. The package is demand-started and the demand arrives
> when the unit leaves standby. That is the whole point — BT exists a few seconds
> after the source decision was already made, which is exactly the race described
> above. It also means **the bench is a valid testbed for this fix**; a car is not
> required to exercise it.
>
> Worth contrasting with USB, which is package 11 and *also* `STOP` at boot but does
> **not** come up on power-on. So the two are gated differently, and USB's blocker is
> elsewhere — most likely `/dev/sysregs` `IpodPwrEn` and `UsbCableDetEn`, which both
> default to 0, leaving the port unpowered regardless of what software is running.
>
> **Therefore every decision-layer patch is inert by construction** — this one, and any
> other that edits how the choice is made. The fix has to ride the **connect event**,
> which means a post-hoc source change: `SoundPresCtrl.SPHSound` →
> `requestNewEntertainmentConnection(AUX=24)` then `(BT_A2DP=40)`, sent once
> `/dev/scp_pss` exists. That is not a workaround; given the architecture it is the
> correct shape. See `BOOT_ORDER_AND_STARTER.md`.
>
> **What below is still true and still useful:** the signature is real and unique, the
> 31-binary scan is valid, and the region/version address table is accurate. The FM index
> genuinely is stored there. It is the *causal claim* — that this byte decides the boot
> source — that measurement refuted. Kept in full, because knowing exactly which
> plausible fix does not work, and why, is worth as much as the one that does.

## Status

~~**Working, offline-validated across all 31 firmware builds on hand; on-car confirmation pending.**~~ **Superseded — see the correction above.** A single byte in `PCM3Root` stores the FM source index for the BT-connected state, and one signature-based patcher can locate and flip it on **every region / model / firmware from v2.00 up**. On-car measurement then showed that flipping it does not change the boot source, for the reasons given above.

Credit: this builds directly on **[WillCoder / PCM_31_AUX-BT](https://github.com/WillCoder/PCM_31_AUX-BT)**, who found the byte and the `/proc/<pid>/as` patch primitive — and who also did the on-car measurement that disproved it, and said so publicly rather than letting it stand.

## The bug (as originally understood — see the correction above)

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

Every firmware package on hand was scanned exhaustively — **31 `PCM3Root` binaries**, one per package × model variant (`generic` = Cayenne/Panamera, `9x1` = 991/981, `Macan`, `Navis`; each in facelift and pre-facelift). Each was extracted (`.rar` → LZO inflate → carve the ELF) and scanned for the signature.

**Result: 29 patch · 2 safe no-op · 0 anomalies.**

The FM-map address is the **same for every model within a region+version** — the model-specific data lives outside `PCM3Root`'s source map — so it collapses to just five distinct addresses:

| Region | Version | Models covered | FM-map address | Result |
|--------|---------|----------------|----------------|--------|
| CHN (China) | v2.00 | generic, 9x1, Navis | `0x08297f48` | ✅ patch |
| CHN (China) | v4.00 | generic, 9x1, Macan, Navis | `0x082b65e0` | ✅ patch |
| ARB (Arabic) | v4.00 | generic, 9x1, Macan | `0x082b2a74` | ✅ patch |
| RDW (USA / RoW) | v4.00 | generic, 9x1, Macan | `0x082b2a78` | ✅ patch |
| LOW (low-line) | v4.00 | generic, 9x1, Macan | `0x082b00d8` | ✅ patch |
| RDW (USA / RoW) | v1.00 (2013) | generic | — (no signature) | ⚪ no-op (safe) |

Observations:
- Across **four regions, four models, both facelift and pre-facelift, v2.00 → v4.00**, the byte to patch (`0x01`, at signature +2) was present in every build. The address varies by **region and version — never by model**, which is one more reason a hardcoded address fails but the signature doesn't.
- Even where the code *around* the store drifted between versions, the 6-byte signature stayed identical and **unique** (exactly one match per binary), so the fail-safe never has to abort on a real unit.
- **Zero anomalies:** no build had the fallback bug present but the signature missing, and none had more than one match.
- The only non-patch is **v1.00** (2013 launch), which predates the fallback code — the tool correctly finds nothing and does nothing.

This is the empirical basis for "universal": because `bt_fix` locates the byte by signature at runtime, it already works on **whatever firmware a user's PCM is running (v2.00+)** with no per-car configuration — the same binary patched all 29 patchable builds and safely no-op'd the two v1.00 images.

Local packages scanned: **ARB** 400, **CHN** 200/400, **LOW** 400, **RDW** 100/400 (the versions we have as full update archives). Other point releases (e.g. v1.50, v2.50, v3.xx) weren't on hand as extractable firmware, but sit between confirmed-patchable neighbours.

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
