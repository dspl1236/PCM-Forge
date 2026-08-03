# Cayenne 92A / 958 — PCM and gateway pinouts

The two connectors this project works against, verified against the vehicle
wiring diagrams. Scoped deliberately: this is what the bench harness and the
CAN work need, not a transcription of the documentation.

Wire labels are `<colour><tracer> <cross-section>`, so `OG VT 0.35` is orange
with a violet tracer, 0.35 mm². `BK` black, `BN` brown, `BU` blue, `GN` green,
`GY` grey, `OG` orange, `RD` red, `VT` violet, `WH` white, `YE` yellow.

## Gateway control unit — SGGW_P, 20-pin

The `7PP907530x` central gateway.

| pin | signal | wire | pin | signal | wire |
|-----|--------|------|-----|--------|------|
| A1 | **TERM. 30** | RD YE 0.35 | A11 | **TERM. 31** | BN BN 0.5 |
| A2 | LIN 1 | BU BU 0.5 | A12 | LIN 2 | |
| A3 | FLEXRAY | BU BU 0.5 | A13 | SHIELD | |
| A4 | FLEXRAY | BU BU 0.5 | A14 | **TERM. 15** | BK BU 0.5 |
| A5 | CAN COMFORT LOW | OG BN 0.35 | A15 | CAN COMFORT HIGH | OG GN 0.35 |
| A6 | CAN DRIVE LOW | OG BN 0.35 | A16 | CAN DRIVE HIGH | OG BK 0.35 |
| A7 | CAN CRASH LOW | OG BN 0.35 | A17 | CAN CRASH HIGH | OG BU 0.35 |
| **A8** | **CAN MMI LOW** | OG BN 0.35 | **A18** | **CAN MMI HIGH** | OG VT 0.35 |
| A9 | CAN DIAGNOSTICS LOW | OG BN 0.35 | A19 | CAN DIAGNOSTICS HIGH | OG GY 0.35 |
| A10 | CAN CHASSIS LOW | OG BN 0.35 | A20 | CAN CHASSIS HIGH | OG RD 0.35 |

Six independent CAN buses plus FlexRay and two LIN channels. **CAN MMI
(A8 / A18) is the PCM's bus**, and it is separate from CAN COMFORT — physical
layer notes about comfort-domain buses do not transfer to it.

Useful identification trick: every CAN **low** is `OG BN`, so the **high**
wire's tracer is what tells the buses apart — comfort `OG GN`, drive `OG BK`,
crash `OG BU`, **MMI `OG VT`**, diagnostics `OG GY`, chassis `OG RD`.

Diagnostics (A9 / A19) is what surfaces at the OBD socket on the standard
pins 6 and 14. Note that Porsche also puts **terminal 15 on OBD pin 1**, which
is convenient on a bench.

## PCM head unit — P100.1, chamber PCMA_P

Housing `B44LWL04A02`. The multi-chamber quadlock; chamber A carries power
and CAN.

| pin | signal | wire |
|-----|--------|------|
| A9 | **CAN LOW** | OG BN 0.35 |
| A10 | not connected | |
| A11 | **CAN HIGH** | OG VT 0.35 |
| A12 | TERM. 31 (ground) | BN BN 2.5 |
| A13 | not connected | |
| A14 | ANTENNA SWITCHED OUTPUT | WH WH 0.5 |
| A15 | TERM. 30F (constant +12 V) | RD YE 2.5 |
| A16 | RING BREAK DIAGNOSIS | BN WH 0.35 |

The remaining chambers are speakers (B), microphone and video (C), iPod and
AUX (D), the two optical waveguide pairs for the MOST ring, four antenna HF
inputs, and USB.

## Two things worth stating plainly

### The CAN pair is the reverse of what forums say

**Pin 9 is CAN LOW and pin 11 is CAN HIGH.** Widely repeated guidance has
these swapped ("CAN-High and CAN-Low are pins 9 and 11 respectively"). That is
wrong, and it is not a cosmetic error: swapping H and L does not degrade a CAN
link, it stops it dead. Dominant bits arrive inverted and read as recessive,
so the bus appears permanently idle — no frames, no ACK, nothing to
distinguish it from a disconnected wire.

Check by **wire colour** rather than by counting pins. It is independent of
pin numbering and agrees with the gateway end:

    OG VT (orange/violet) = CAN HIGH  ->  gateway A18
    OG BN (orange/brown)  = CAN LOW   ->  gateway A8

### The PCM has no terminal 15

Only constant power (A15) and ground (A12). There is no ignition input to
find, because **terminal 15 reaches the PCM as a CAN message on CAN MMI**,
sent by the gateway alongside S CONTACT, RADIO KEY and the various chassis
status signals.

The consequence for bench work: a PCM with no gateway is never told the car is
on. It powers from terminal 30, lights its display and answers the power
button while its CAN section stays down — both bus lines sitting at 0 V. That
is not a fault, and no amount of probing the head unit will reveal anything,
because the thing it is waiting for is a frame that nobody is sending.

**A gateway is the wake source for a bench PCM, not a convenience.** Feed the
gateway terminal 15 on its A14 and it broadcasts the message the PCM wants.

## Bench harness

Seven wires to bring a gateway up with a PCM attached:

    gateway A1   TERM 30        -> +12 V constant
    gateway A14  TERM 15        -> +12 V switched
    gateway A11  TERM 31        -> ground
    gateway A19  CAN DIAG HIGH  -> CAN adapter H   (= OBD pin 6)
    gateway A9   CAN DIAG LOW   -> CAN adapter L   (= OBD pin 14)
    gateway A18  CAN MMI HIGH   -> PCM A11
    gateway A8   CAN MMI LOW    -> PCM A9

Only four pins are needed to power a PCM and put it on a bus: A15 constant
12 V, A12 ground, A11 CAN high, A9 CAN low. Chambers A–D follow the standard
VAG quadlock layout so an Audi housing fits physically, but the pin
assignments do not carry over — populate by the numbers above and ignore what
a donor harness's colours originally meant.

Termination is per segment; measure each pair unpowered before connecting.
60 Ω means two terminators are present, 120 Ω means one, and anything near
40 Ω means too many.

See `tools/bench-dongle/` for the capture scripts.
