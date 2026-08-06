# PCM diagnostics — what the Autel does, decoded off the wire

Captured 2026-08-04 on the bench with an Autel on the OBD port and both buses
recorded in parallel: `captures/diag_autel_20260804.log` (1,265 frames on the
diagnostic pair) and `mmi_autel_20260804.log` (52,351 frames on CAN MMI).

**The two logs are stamped in different units.** The CANable writes
milliseconds, the Nano writes seconds; both runs end at 600 s, which is how the
factor of 1000 was spotted. Correlating them without dividing produces nonsense,
and briefly produced a confident wrong answer here.

## Addressing

| target | request | response | protocol |
|--------|---------|----------|----------|
| PCM | `773` | `7DD` | KWP2000 |
| gateway | `710` | `77A` | UDS |

KWP2000, not UDS — the service numbers overlap but mean different things. `0x31`
is `StartRoutineByLocalIdentifier` here, not `RoutineControl`, and a UDS decoder
silently mislabels exactly the half we care about.

The Autel also fires TP2.0 channel-setup probes at `200` (`<addr> C0 00 10`) for
addresses 18 1C 22 23 24 25 26 2F 35 43 49. Nothing answered any of them.

## Services the PCM answers

Counted over the whole session, requests only:

| service | n | meaning |
|---------|---|---------|
| `3E` | 212 | TesterPresent |
| `33` | 94 | RequestRoutineResultsByLocalId |
| `1A` | 18 | ReadEcuIdentification |
| `27` | 11 | SecurityAccess |
| `10` | 10 | StartDiagnosticSession |
| `31` | 6 | StartRoutineByLocalIdentifier |
| `18` | 5 | ReadDTCByStatus |
| `22` | 4 | ReadDataByCommonIdentifier |
| `32` | 2 | StopRoutineByLocalId |
| `14` | 1 | ClearDiagnosticInformation |

Only one session type is ever used: `10 89`, a manufacturer session. The session
lapses in seconds without `3E`, which is why 212 of the 361 requests are
keepalive.

`7F 3E 80` — NRC `0x80`, non-standard — is the answer to TesterPresent with no
session open. It is the reliable "PCM is alive but idle" tell.

## Identity — readable with no security at all

The Autel unlocked before reading this block, so the capture alone suggests the
block is gated. It is not: with the PCM **locked** (`27 01` returning a live
seed `995E`, no key sent), `1A 91` still answered `"7P5035884AB"`. The unlock in
the capture was for the routines that came later, not for these reads.

```
1A 9F   09 00                    diagnostic status
1A 90   "WP1  1. .        "      VIN field, mostly blank on the bench unit
1A 91   "7P5035884AB"            part number
1A 95   "0114181A"               software version
1A 01   "95864296100   "         Porsche part number 958.642.961.00
1A 94   02 02 12                 hardware
1A 83   "343"                    coding
22 F008 00 03                    config
22 F009 "28-APR-2014-R"          build date
```

## SecurityAccess — not forgeable from this capture

`27 01` requests a 2-byte seed, `27 02 <key>` answers it. Four live pairs:

```
seed 3D32 -> key 323D
seed A059 -> key 5399
seed 1C25 -> key 128E
seed B9FE -> key 1781
```

The first pair is a byte swap, which is a coincidence — none of the others are.
Brute-forced against rotate/xor/add/subtract with any 16-bit constant, affine
`seed*a+b` over all odd multipliers, and byte-wise combinations of both seed
bytes: **no candidate reproduces all four.** The algorithm is wider than 16 bits
or table-driven, and four pairs off the wire are not enough.

Worth knowing anyway: `27 01` returned seed `0000` three separate times, and the
tool sent no key and proceeded regardless. Once unlocked the PCM stays unlocked
across subsequent sessions for a while, so a single unlock is worth more than
the pair count suggests.

## Routines

```
31 17 01  -> 71 17           ok, immediate
31 0B     -> 71 0B 02 02     returns a 2-byte state; run 3x, same answer
31 2E 01  -> 71 2E           ok, immediate
31 29 00  -> 41 s of responsePending, then generalReject
32 02     -> 72 02 01        stop; never started in this capture
32 10     -> 72 10 02        stop; never started in this capture
```

`32 02` and `32 10` stopping routines that were never started means those two
were already running before the tool arrived.

Routine `17` was polled with `33 17` from 377 s — long before `31 17 01` at
425.6 s — and that poll storm ended in `generalReject` at 393.3 s.

## The power-on question is still open

The working theory going in was that `10 89` powers the unit up. **The aligned
timestamps do not support it.** At every one of the four moments the PCM
appeared on CAN MMI, the PCM moved first:

```
132.2  MMI   PCM announces on 6D3
132.5  DIAG  1A 9F
132.9  DIAG  10 89        <- 0.7 s after the PCM was already up

399.2  MMI   PCM resets, 539 -> 00 02 00
409.6  DIAG  10 89        <- 10.4 s after
```

The `539` progression — byte 1 `02 -> 08 -> 0A`, byte 2 `-> 80` — runs at +2 s,
+5 s and +9 s from reset whether or not a session is open, and matches the cold
boot in `CAN_MMI_BUS.md` exactly. It is the PCM's own startup, self-timed.

Genuine PCM resets (`539` byte 0/1/2 all clearing to `00 02 00`, with `6D3`):
**24.3, 40.5, 188.9, 342.3, 399.2 s.** They follow stretches of sustained tester
activity, not any single frame. The one at 188.9 s lands during the Autel's bus
auto-scan, which is when the operator first reported the service screen.

Two things this does establish:

- **The PCM answers diagnostics in standby, screen dark.** Its first frame in
  the capture is `7F 3E 80` at 131.8 s, before the tool had ever addressed it.
  We can query the unit cold without waking it.
- **No other module was told to bring it up.** The gateway conversation ends at
  242 s, before any of the routines, and nothing else on the bus was addressed.

## Bench-verified, 2026-08-04, driving it ourselves

`tools/bench-dongle/pcm_slcan.py` now talks KWP to the PCM directly, so the
capture's ambiguities can be settled by experiment instead of correlation.

**The PCM does full diagnostics with the screen dark — observed, not inferred.**
Screen on and screen off give byte-identical answers:

```
3E    -> 7F 3E 80   noActiveSession
1A 9F -> 9F 09 00
```

The earlier claim rested on the tester's first frame arriving at 131.8 s, but
the PCM had booted at 40.5 s and was running by then, so the log never actually
showed standby. Knobbing the screen off and re-probing does.

**`10 89` does not raise the screen.** Session accepted (`50 89`), held 30 s
with 480 TesterPresent — far heavier than the Autel's ~1/s — screen stayed dark.
The timestamp analysis is confirmed by direct test, not just correlation.

**The routines are security-gated; the identity block is not.**

```
27 01     -> 67 01 995E                       live seed: we are locked
1A 91     -> "7P5035884AB"                    answers anyway
31 17 01  -> 7F 31 33  securityAccessDenied
33 17     -> 7F 33 33  securityAccessDenied
```

That is why the Autel unlocked at 409.6 s: not for the reads at 275 s, which
need nothing, but for the routines at 425.6 s. **Whatever raises the screen is
behind SecurityAccess**, which puts the key algorithm on the critical path.

Two ways forward. The quick one: have the Autel perform an unlock and then ride
it. The durable one: recover the algorithm from the firmware, since four
seed/key pairs are not enough to brute-force it.

## Riding the Autel's unlock — proven, and its limit

Done on the bench 2026-08-04. With the Autel freshly into the PCM, `27 01`
returned seed `0000` — already unlocked — and **every routine that had been
refused an hour earlier now ran**:

```
31 17 01  -> 71 17          (was 7F 31 33 securityAccessDenied)
33 17     -> 73 17 01
31 2E 01  -> 71 2E
31 0B     -> 71 0B 02 02
```

Byte-identical to the Autel's own results. **SecurityAccess was the only gate**
— nothing else about the tool is special, and everything downstream of the lock
is reproducible by us.

**The unlock does not survive a PCM reboot.** It carries across diagnostic
sessions freely, but after a reboot `27 01` returns a live seed again (`33F0`
observed). So the usable window is "unlocked *and* not since rebooted", which
is easy to lose — the Autel itself reboots the unit regularly.

Two cautions learned the same afternoon:

- **Do not guess at keys.** KWP defines `0x36 exceedAttempts`; blind `27 02`
  tries risk an attempt limiter on a unit that is awkward to recover.
- **An active Autel contaminates every measurement.** One routine test was
  wasted because the PCM began rebooting 0.37 s *before* our injection and
  answered `7F 31 21 busyRepeatRequest`. Three extra ids (`3A1`, `3A2`, `6D3`)
  appear when it is driving a session. Keep it idle during any test.

## A third PCM state

`539` byte 1 has three observed values, not two:

| byte 1 | byte 2 | 5FA / 5FB | meaning |
|--------|--------|-----------|---------|
| `02` | `00` | zero | down / standby |
| `0A` | `80` | populated | up, normal |
| `00` | `80` | zero | third state, seen after Autel service entry |

The third appears with `539 = 2D 00 80 00 FE 29 00 00` and is the most likely
match for the on-screen "service" mode. Any wake test must check byte 1 against
all three, not just up/down.

## Dead end: A16 is not the wake input

The 991 wiring set labels PCM pin A16 `WAKEUP` where the Cayenne set calls it
`RING BREAK DIAGNOSIS` — same pin, same `BN WH 0.35` wire. Promising, but
measured on the bench it sits at **12 V and does not collapse under 1 kΩ**, and
pulling it produced no wake. That makes it an output — the PCM asserting ring
wake to other nodes — not its own trigger. See `CAYENNE_958_PINOUTS.md`.
