# CAN MMI bus — who sends what, and the cold-boot sequence

Captured 2026-08-03 on the bench: gateway `7PP907530Q` + PCM 3.1 on the CAN MMI
pair, 500 kbps, terminal 15 hard-wired so ignition is high from power-on.
Raw log: `captures/mmi_boot_20260803.log` (29,897 frames, 180 s).

## Attribution

The PCM alone — no gateway, terminal 30 only — transmits exactly six IDs. Every
other ID in the two-node capture is therefore the gateway. That gives a clean
split without having to unplug anything:

| source | IDs |
|--------|-----|
| **PCM** | `539` `541` `5FA` `5FB` `6AB` `6D3` |
| **gateway** | `31C` `31D` `38C` `38D` `39C` `3C3` `3F1` `444` `484` `523` `52E` `537` `538` `585` `5EA` `5EB` `5EC` `64C` `663` `66B` `66C` `6B2` `6C0` |

23 gateway IDs, 6 from the PCM. **The gateway alone is enough to give the PCM a
plausible car** — with it present the PCM stays awake indefinitely and needs no
injected keepalive, where alone it sleeps after ~1.2 s.

All 29 IDs appear within **114 ms** of each other. The bus arrives fully formed;
there is no staggered enumeration to observe.

`6D3` is the exception: five frames in the first 0.8 s and never again. A
startup announcement from the PCM, not periodic traffic.

## Cold-boot sequence

Payload transitions, which are the observable milestones. `6B2` is excluded —
it is a free-running 1 Hz counter from the gateway (171 changes) and drowns
everything else.

```
0.10s  GW   585  byte 1
0.12s  GW   663  bytes 1,3,5
0.22s  PCM  539  byte 0
0.97s  GW   6C0  byte 0     01 -> 04
1.18s  PCM  6AB  byte 7     20 -> A0
2.01s  GW   3F1  byte 1     00 -> 02        one-shot, never changes again
4.97s  GW   6C0  byte 2     05 -> 01
5.17s  GW   663  byte 0     73 -> 7B
6.86s  GW   663  byte 0     7B -> 78
12.18s PCM  6AB  bytes 6,7  00 A0 -> 43 A1
12.87s GW   663  byte 2     00 -> E0
16.73s PCM  539  byte 2     00 -> 80
21.23s PCM  539  bytes 4,5
21.98s PCM  5FB  populates  00.. -> 1F FF FF FF FF 1F F8 7E
22.99s PCM  5FA  populates  00.. -> 5B 9D C7 CC 9C 46 F1 FF
33.73s PCM  539  byte 0
```

After ~45 s the bus settles. Only `539` byte 0 and `6AB` byte 6 keep moving,
slowly and irregularly — the shape of a temperature or level, not a state.

## Candidates worth chasing

**`3F1` byte 1** — flips `00 -> 02` at 2 s and never moves again. A one-shot
latch is exactly the shape a terminal-15 flag would have. Best single candidate.

**`6C0`** — a gateway state machine: byte 0 `01 -> 04` at 1 s, byte 2 `05 -> 01`
at 5 s, then static. A two-stage system-state word.

**`5FA` / `5FB`** — both go from all-zero to six bytes of populated data at 22 s,
a second apart. That is the PCM publishing something once it is genuinely up,
and 22 s is about when the UI becomes usable.

**`6B2`** — gateway, 1 Hz, bytes 6–7 a rolling 16-bit counter with bit 15 used
as a separate flag. Time or uptime.

## Not yet isolated

Terminal 15 was hard-wired for this capture, so ignition is high from the first
frame and cannot be separated from power-on. **Lift the gateway's A14 and
re-run** — anything that differs is the ignition path.

## The diagnostic bus is silent, and correctly so

The Nano on the gateway's diag pair (`A19`/`A9`) captured **zero frames in
180 s**. Diagnostic CAN is request/response: nothing transmits until a tester
asks. Not a fault, and not a wiring problem — it needs a scan tool or a UDS
request from us before there is anything to hear.

## Tooling

`tools/bench-dongle/capture_both.ps1` runs both buses as parallel jobs with a
shared wall-clock stamp. See `BENCH_CAN.md` for the adapter traps — particularly
that the CANable will not receive until it has transmitted, which is why the
capture emits a burst before the unit is powered.

## Ignition: found, and not sufficient

Isolated 2026-08-03 by disconnecting the gateway's A14 and capturing, then
applying 12 V mid-capture.

**`3F1` byte 1 is the gateway's ignition flag.** `00` with A14 open, `02` with
12 V applied — predicted from shape two captures earlier (a one-shot latch at
2 s that never moved again) and then confirmed by controlled variable.
`663` byte 2 moves with it, `00 -> E0`.

The PCM's response, all on its own transmitted IDs:

| | ignition OFF | ignition ON |
|---|---|---|
| `539` | `XX 02 **00** 00 **FE 01** 00 00` | `XX 02 **80** 00 **08 03** 00 00` |
| `5FA` | all zeros | `5B 9D C7 CC 9C 46 F1 FF` |
| `5FB` | all zeros | `1F FF FF FF FF 1F F8 7E` |
| `6AB` byte 6 | `00` | `3F`/`41` (drifts) |
| `6D3` | present | absent |

### Ignition is sampled at boot, not watched

Applying 12 V to A14 while the PCM sat in standby did nothing — it stayed dark
and kept reporting ignition-off. Pressing the power knob afterwards made it
boot, read the flag, and report ignition-on. So the PCM latches vehicle state
at startup; asserting it later does not change its mind.

### A gateway-only restbus is not enough

With the real gateway off the bus, replaying all 23 of its IDs **verbatim** —
original order, original timing, live rolling counters, ignition asserted — and
power-cycling the PCM into it: the PCM boots (`6D3` fires twice) and still
reports ignition **off** on every signal above. 28,438 frames.

This also disproves the frozen-counter theory. A synthesised table with `6B2`
frozen failed, but so did a verbatim replay with the counter moving correctly,
so stale-data rejection is not the mechanism.

**The likely reason: we are replaying one node out of nine.** The topology
sheet lists gateway, PCM, instrument cluster, compass, A/C control unit, PDC
x2, CAN adapter and parking heater on CAN MMI. This bench has only ever had two
of them, so seven modules' worth of traffic has never been captured. The
instrument cluster is the obvious suspect — the function-flow sheet has it
sending cluster status, odometer, GPS time and light sensor to the PCM, and in
VAG-derived cars the cluster is usually the authority on vehicle state.

That a commercial CAN-only emulator reportedly does achieve this says the
answer is on this bus and we are simply missing most of it.

**Next: sniff a running car.** Pins A9/A11 at the PCM connector on the real
Cayenne gives all nine nodes at once. Replay that and the bench has a complete
car rather than a gateway impersonation.
