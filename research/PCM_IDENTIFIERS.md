# What a PCM 3.1 will tell you, unlocked

Every identifier below reads on a **locked** unit — no SecurityAccess, no PIWIS,
no USB. Captured from the bench unit 2026-08-05 with
`tools/bench-dongle/pcm_slcan.py --step sweep`.

## Read it without a gateway

The PCM answers KWP on `773`/`7DD` **directly on CAN MMI** (PCM pins A9/A11).
The gateway is only a router between the OBD diagnostic pair and CAN MMI — with
the gateway powered down, requests over OBD get nothing, and the identical
requests injected onto CAN MMI are answered in full.

That matters on a car as much as a bench: tapping the PCM connector reaches the
unit whether or not the rest of the vehicle is awake.

    python pcm_slcan.py --port COM5 --step version   # one-line summary
    python pcm_slcan.py --port COM5 --step sweep     # enumerate everything

## Bench unit, for reference

| field | service | value |
|-------|---------|-------|
| **VIN** | `1A 9D` | `WP1AA2A21DLA04395` |
| part number | `1A 91` | `7P5035884AB` |
| Porsche part | `1A 01` | `95864296100` |
| software version | `1A 95` | `0114181A` |
| build date | `22 F009` | `28-APR-2014-R` |
| coding | `1A 83` | `343` |
| hardware | `1A 94` | `02 02 12` |
| config | `22 F008` | `00 03` |
| diagnostic status | `1A 9F` | `09 00` |

`1A 90` returns a *truncated* VIN field (`WP1  1. .`) and is the one the Autel
reads. **`1A 9D` carries the full 17 characters** — worth knowing, because the
short field looks like the unit is uncoded when it is not.

## Full enumeration

`ReadEcuIdentification`, 16 of 256 sub-identifiers answer:

| id | bytes | ascii |
|----|-------|-------|
| `01` | `3935383634323936313030202020` | `95864296100` |
| `81` | `303030…` (15 chars) | `000000000000000` |
| `82` | `0000000000` | |
| `83` | `333433` | `343` |
| `84` | `040826` | date-shaped |
| `90` | `5750312020310020002020202020202020` | `WP1  1. .` (truncated VIN) |
| `91` | `3750353033353838344142` | `7P5035884AB` |
| `92` | `424596214305019920` | binary |
| `94` | `020212` | hardware |
| `95` | `3031313431383141` | `0114181A` |
| `98` | `00000001` | |
| `99` | `050912` | date-shaped |
| `9C` | `09` | |
| **`9D`** | `575031414132413231444C413034333935` | **`WP1AA2A21DLA04395`** |
| `9E` | `03039041` | |
| `9F` | `0900` | |

`ReadDataByCommonIdentifier`, 16 of 256 in the `F0xx` block:

| did | notable content |
|-----|-----------------|
| `F001` | `010170` |
| `F002` | `00000000` |
| `F004` | `200209` |
| `F005` | `0003` |
| `F006` | `01` |
| `F007` | `03FFFF14` |
| `F008` | `0003` |
| `F009` | `28-APR-2014-R` |
| `F010` | `01320000000002890201140000…` |
| `F011` | `01100801100800000000…` |
| `F020` | multi-field: `09091109`, `0114181A` |
| `F021` | `…01D21030…`, `6HPUN24R` |
| `F024` | contains **`7PP035753`** — a MOST-side component part number |
| `F028` | `0114181A`, `10361A`, `05D21212` |
| `F029` | four `00000000` fields |
| `F030` | `04000002` |

`F1xx` is almost empty — one identifier of 256:

| did | content |
|-----|---------|
| `F19E` | `PCM31` |

`F19E` is the **ASAM/ODX file identifier** by convention, and the unit naming its
own description `PCM31` corroborates what the firmware showed independently: the
diagnostic services are ODX-described data walked by the `CRBDiag*` interpreter,
not compiled handlers. See `DIAG_DESCRIPTION.md`.

## Two units compared

A second unit — a **991** PCM (Spyderdoc's) — read on the same bench, screen
off, over CAN MMI.

| | Cayenne bench | 991 |
|---|---|---|
| `1A 9D` **VIN** | `WP1AA2A21DLA04395` | `WP0AC2A84GK191352` |
| `1A 01` | `95864296100` | `99164296116` |
| `1A 91` | `7P5035884AB` | `99164217822` |
| **`1A 93`** | *absent* | **`02011221`** |
| `1A 95` software version | `0114181A` | *absent* |
| `1A 83` coding | `343` | *absent* |
| `1A 84` | `040826` | `150321` |
| `1A 94` hardware | `020212` | `110515` |
| `1A 9C` | `09` | `13` |
| `1A 9F` | `0900` | `0901` |
| `F0xx` readable | 16 | **3** |

`WP0` is the sports-car WMI against the Cayenne's `WP1`. The 991 VIN's model-year
character `G` is **2016**, matching its `05.01.2016` build label.

### `1A 93` — the hardware stand

Present on the 991, absent on the Cayenne. Its value `02011221` matches the
`HW-Stand: 02011221` printed on the unit's own label exactly, making it the
cleanest identifier-to-label correspondence found so far. Worth reading on any
unit; it is not in the block the Autel reads.

### Read a unit with its drive installed — confirmed

The 991 first returned only **3** of the `F0xx` identifiers, with no software
version, coding or build date. Read again with the drive **refitted**: **17**.
So a large part of the identifier space is disk-backed, and a sparse read means
"drive absent", not "unit different".

| | drive out | drive in |
|---|---|---|
| `1A` readable | 15 | 17 |
| `F0xx` readable | 3 | 17 |
| `1A 95` software version | absent | `0115245A` |
| `1A 83` coding | absent | `476` |
| `1A 81` | absent | `000000000000000` |

Always read a unit with its drive in. `1A 95` is the field that settles a
unit's software version and it is one of the first to vanish.

### `1A 95` decodes to the label's SW-Stand

`0115245A` on the 991 — drop the leading `01` and it is **`15245A`**, matching
the `SW-Stand: 15245AS9` printed on the unit (the `S9` suffix is the step). The
Cayenne bench unit reads `0114181A` = `14181A`, a different software train.

`22 F003` carries the same value, and `22 F028` pairs it with `13171A`, which
matches the `SSS_Process: …_MOPF_SOP_Trunk__13171A` string on that unit's drive.

### `22 F022` — component part numbers, matching the physical label

On the 991:

```
7PP035593B      label: * 7PP 035 593 B*
7PP919193DE     label: DIG Tuner * 7PP 919 193 DE*
```

This is the identifier to read when you want to know what a unit *thinks* is
fitted, and it is verifiable against the sticker.

### `22 F024` is platform-wide, not equipment

`7PP035753` reads **identically on the Cayenne and the 991**. Two different
vehicle lines with different audio systems return the same value, so it is not
an equipment or amplifier identifier. Recorded because the opposite was
assumed; see `AMP_VARIANT.md`.

## The VIN is not coding — the PCM learns it from CAN

Established 2026-08-05, after trying and failing to change a bench unit's VIN
with PIWIS.

**PIWIS never sends a VIN write.** A full 47-minute session was captured on both
buses; the only writes in it are `3B 08` and `3B 09` with two-byte values. It
*reads* the VIN twice (`1A 90` truncated, `1A 9D` full) and never writes it. The
attempt failed inside the tool, not at the PCM — nothing was refused because
nothing was sent.

**There is nowhere to write it.** `21 00..FF` (ReadDataByLocalIdentifier) returns
21 identifiers on this PCM and **none is the VIN**, so its write counterpart
`3B` cannot reach it. It is absent from the `22 F0xx` and `F1xx` DID spaces too.
The VIN exists only at `1A 9D`, in the ECU-identification space, which has no
KWP write counterpart.

**Because it is not stored as configuration.** Searching a whole 93 GB drive for
its own unit's VIN returns hits in exactly one place — the system logs:

```
/log/watchdog_2020.05.20_19.31.41_sloginfo.txt
    pid 16417: VIN(A) from CAN: 'WP0AC2A84GK191352'
```

`VIN(A) from CAN`. The unit **receives** its VIN over the bus and reports back
what it heard. The `(A)` implies a multi-part message, which is how 17
characters travel in 8-byte frames.

**The broadcast is not on our bench.** Every capture was searched for the VIN in
fragments (`WP0`/`WP1` as hex, since a contiguous search misses a split
message). The only frames carrying one are diagnostic *responses* — `62 F190`
from the gateway, `5A 90` from the PCM. No periodic broadcast at all.

So the sender is a module this bench has never had. The topology lists nine on
CAN MMI and we have had two. **The instrument cluster is the prime suspect —
the same module already suspected of carrying the wake signal.**

### What this means practically

To change a bench PCM's VIN you do not write the PCM. You put the VIN on the
bus and let it learn. Which needs the message id and format, and those need a
capture from a real car.

Both open questions — the wake path and the VIN — now depend on the same
experiment: sniff CAN MMI on a running vehicle. See `BOOT_ORDER_AND_STARTER.md`.

## Nothing in the read space is locked

**512 identifiers probed, 33 readable, zero returned `securityAccessDenied`.**

That is worth stating plainly because it bounds what the SecurityAccess key is
actually worth. The key does not unlock *data* — every readable identifier on
this unit already answers on a locked PCM. What it gates is `31` routines
(demonstrated: refused when locked, ran immediately under the Autel's unlock)
and, presumably, the write services.

So the key buys **actions, not information**. Anyone wanting identity, version,
VIN, coding or build data needs no key at all.

## Reading a negative response

A sweep's failures carry information:

- `requestOutOfRange` (`0x31`) — the identifier does not exist.
- `securityAccessDenied` (`0x33`) — it exists and is **locked**.

None of the identifiers above returned `0x33`, which is why they are all
readable. Anything that does return `0x33` is worth recording separately: it is
a target the key would unlock, and so far nothing in the read path is.

## Writing is a different matter

`2E WriteDataByCommonIdentifier` and `3B WriteDataByLocalIdentifier` are how a
dealer tool codes a module, and both are expected to sit behind SecurityAccess.
**Untested deliberately** — no write opcode has been sent to any unit.

For actually changing behaviour, the proven route on this project is not the
diagnostic layer at all but `/HBpersistence`: the Burmester amplifier change was
made by editing `audiomixer_BOSE.txt`, and the `CVALUE*.CVA` coding store lives
there too. That needs no key, no PIWIS and no USB. See
`AMP_VARIANT.md` and `tools/cvalue_tool.py`.
