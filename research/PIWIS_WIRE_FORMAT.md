# What PIWIS actually sends — captured on the wire

A full PIWIS 3 session against the bench gateway and PCM, captured 2026-08-05 on
both buses simultaneously with `tools/bench-dongle/dual_capture.py`. 563,893
frames over ~47 minutes.

One process reads both adapters against one `time.time()`. An earlier dual-bus
capture used two tools stamping in different units — CANable in milliseconds,
Nano in seconds — and correlating them without noticing produced a confident
wrong conclusion. Do not repeat that; use the one tool.

## Feature activation is `RoutineControl` routine `0xF0`

The headline. PIWIS's **MOST Funktionsfreischaltung** screen sends:

```
31 F0 <SWID:2> <activation code:9>
```

Two attempts were captured, and both name features this project already has the
algorithm for:

```
773  31 F0 01 0B  62 15 90 C3 DC 5B BA 90 00     ENGINEERING (Entwicklermenü)
773  31 F0 01 09  48 E0 CB F4 0B 72 1A D0 00     UMS (USB / iPod)
```

The SWIDs match `FEATURE_REFERENCE.md` exactly — `0x010B` ENGINEERING, `0x0109`
UMS — and the code field is **9 bytes**, not the 8 the PIWIS screen displays as
`0000000000000000`.

**Both were rejected with `requestOutOfRange` (`0x31`).**

This was *not* a security failure: the PCM had returned seed `0000` — already
unlocked — at 1942 s, well before these attempts at 2451 s and 2547 s. On a
routine, `requestOutOfRange` normally means the routine identifier is not
supported. So either routine `F0` does not exist on this unit, or the parameter
form differs from what PIWIS sent. Consistent with the PIWIS screen showing
every Freischaltcode as zeros: the dealer tool did not have valid codes either.

**Open question, and the obvious next experiment:** generate a real code for
`0x0109` with our own algorithm (see `ALGORITHM_CRACKED.md`) against this unit's
VIN and send the same frame. If it is accepted, feature activation over CAN is
solved and needs neither PIWIS nor USB. If it still returns
`requestOutOfRange`, routine `F0` is genuinely absent here and the USB route
stays the only one.

## Writes work once unlocked

`WriteDataByLocalIdentifier` on local ids `08` and `09`, all accepted:

```
3B 08 00 00 -> 7B 08        3B 09 00 00 -> 7B 09
3B 08 D8 42 -> 7B 08        3B 09 18 00 -> 7B 09
```

Bracketing routines, both accepted: `31 25` (returned `71 25 01` after ~6 s of
`responsePending`) and `31 22` (immediate).

## SecurityAccess — five PCM pairs, still unsolved

One clean, accepted exchange:

```
773  27 01           ->  7DD  67 01 6E 0F     seed 6E0F
773  27 02 91 F0     ->  7DD  67 02 34        ACCEPTED
```

`0x6E0F + 0x91F0 = 0xFFFF` exactly — the key is the seed's one's complement.
**That is a coincidence.** Scored against all five known pairs the complement
rule reproduces only that one, and the byte-swap rule only reproduces `3D32`:

| seed | key | xor | source |
|------|-----|-----|--------|
| `6E0F` | `91F0` | `FFFF` | PIWIS, accepted |
| `3D32` | `323D` | `0F0F` | Autel |
| `A059` | `5399` | `F3C0` | Autel |
| `1C25` | `128E` | `0EAB` | Autel |
| `B9FE` | `1781` | `AE7F` | Autel |

No constant xor, add or subtract fits. Still not forgeable.

**The unlock persists.** Seed `0000` at 1942 s, long after the 1286 s unlock —
the same ride-along window the Autel gave. Anything needing security can be done
by us inside it.

## The gateway is a separate problem — eight pairs, 32-bit

The gateway uses `27 03`/`27 04` with **four-byte** seeds, and unlocks twice per
session: once in session `03`, then again after entering session `4F`.

```
2703 -> 6703 96D73DF4     2704 C330F433
2703 -> 6703 8677BD65     2704 748524C5
2703 -> 6703 E606B422     2704 081FA7BF
2703 -> 6703 EDECA1BB     2704 0A743821
2703 -> 6703 59E1E080     2704 16ABCB1B
2703 -> 6703 3DED6681     2704 7988F9CD
2703 -> 6703 F668928E     2704 B0D2DF47
2703 -> 6703 EAFA9537     2704 75E758C9
```

No constant xor/add/sub across the eight. A 32-bit algorithm with eight known
pairs is a better-conditioned target than the PCM's, and unlike the PCM we can
harvest more pairs on demand by re-running a PIWIS session.

## Session structure, for reference

```
gateway   10 03  ->  50 03 00 32 01 F4      then 27 03/04
          10 4F  ->  50 4F 00 32 01 F4      then 27 03/04 again
PCM       10 89  ->  50 89                  then 27 01/02
cluster   714    10 03                       polled throughout
```

The cluster at `714` appears on **both** buses; the gateway (`710`/`77A`) only
on the diagnostic pair; the PCM (`773`/`7DD`) on both. That matches the routing
established in `BENCH_CAN.md` — the gateway bridges, and is itself only
reachable from the OBD side.

## Reproducing

```
python dual_capture.py --mmi COM5 --diag COM6 --out piwis --minutes 240
```

Start it before PIWIS. It prints sessions, SecurityAccess, writes and routines
live with ISO-TP reassembled, filters TesterPresent and repeated reads, and
writes `piwis_{mmi,diag,merged}.log` plus a summary of every `27`/`67` frame.

Note it writes to **relative** paths, so run it from the directory you want the
logs in.
