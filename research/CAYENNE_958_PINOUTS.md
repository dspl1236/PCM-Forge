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

## PCM head unit — the remaining chambers

Full map for **MJ0D–MJ0G**, which covers our MOPF unit. Read off sheet 20 of
the vehicle wiring set. Pins not listed are `nc`.

| chamber | pin | signal | wire |
|---------|-----|--------|------|
| **B** speakers | B1 | SPEAKER, REAR RIGHT + | VT VT 0.5 |
| | B2 | SPEAKER, FRONT RIGHT + | GY GY 0.5 |
| | B3 | SPEAKER, FRONT LEFT + | WH WH 0.5 |
| | B4 | SPEAKER, REAR LEFT + | GN GN 0.5 |
| | B5 | SPEAKER, REAR RIGHT − | VT BK 0.5 |
| | B6 | SPEAKER, FRONT RIGHT − | GY BK 0.5 |
| | B7 | SPEAKER, FRONT LEFT − | WH BK 0.5 |
| | B8 | SPEAKER, REAR LEFT − | GN BK 0.5 |
| **C** mic / video | C1 | MICROPHONE + | GY GY 0.35 |
| | C3 | MICROPHONE SHIELD | BK BK 0.35 |
| | C4 | SWITCHED OUTPUT AMPLIFIER | BK RD 0.35 |
| | C9 | MICROPHONE − | BU BU 0.35 |
| | C10 | VIDEO SIGNAL | BLK BLK 0.1 |
| | C11 | VIDEO GND | BK BK 0.75 |
| | C12 | BLUETOOTH HANDSET | WH WH 0.35 |
| **D** iPod / AUX | D1 | IPOD ACC DET | |
| | D2 | AUX 1 IN L+ | BU BU 0.14 |
| | D3 | IPOD CHARGE GND | OG OG 0.14 |
| | D4 | AUX SHIELD | BK BK 1.0 |
| | D5 | IPOD CON RX | |
| | D6 | IPOD CON TX | |
| | D7 | AUX 1 IN R+ | GN GN 0.14 |
| | D8 | AUX-1-RETURN | BN BN 0.14 |
| | D11 | IPOD ACCESSORY IDENT | |
| | D12 | IPOD CHARGEPOWER + | OG OG 0.14 |
| **E / F** MOST | E1 / F1 | OPTICAL WAVEGUIDE IN | |
| | E2 / F2 | OPTICAL WAVEGUIDE OUT | |
| **G** | G1 / G2 | RADIO HF IN / SHIELD | BLK 0.35 / BK 0.5 |
| **H** | H1 / H2 | SDARS ANTENNA / SHIELD | BLK 0.35 / BK 0.5 |
| **J** | J1 / J2 | GPS HF IN / SHIELD | BLK 0.35 / BK 0.5 |
| **K** | K1 / K2 | TELEPHONE HF IN / SHIELD | BLK 0.35 / BK 0.5 |
| **L** USB | L1 | DATA + | BU BU 0.14 |
| | L2 | **VUSB** | BN BN 0.14 |
| | L3 | DATA − | GN GN 0.14 |
| | L4 | GROUND | OG OG 0.14 |
| | L5S | SHIELD | BK BK 1.0 |
| **M** display | M1 | LVDS − | BU BU 0.14 |
| | M2 | GROUND | OG OG 0.14 |
| | M3 | LVDS + | GN GN 0.14 |
| | M4 | GROUND | BN BN 0.14 |
| | M5S | SHIELD | BK BK 1.0 |
| **N** | N1 / N2 | DAB ANTENNA / SHIELD | BLK 0.35 / BK 0.5 |

Sheet 20 also carries pins `A1`–`A4` that are **not** the PCM: they belong to
the AUX socket and the antenna module sharing the sheet. The PCM's own chamber
A starts at A9. Pin letters repeat across devices on one sheet, so read the
connector name, not just the pin.

### USB is native to the head unit, on chamber L

Worth stating because it is easy to assume otherwise from the MOST ring being
right there on the same sheet. The socket end of the same harness appears as
`B1`–`B4`, and the colours identify the wires unambiguously at either end:

    BN  VUSB      BU  DATA +      GN  DATA −      OG  GROUND      BK  shield

### The iPod path cannot substitute for USB

`D5 IPOD CON RX` / `D6 IPOD CON TX` is a **UART**, with audio arriving as
*analog* line-in on the AUX pins and charge power on D12. There are no
differential data lines in chamber D. It is the 30-pin dock arrangement — iAP
control over serial, sound over analog — so a mass-storage device has nothing
to enumerate against there, at any voltage, with any adapter.

### Model-year history

| years | what changed |
|-------|--------------|
| MJ0B, MJ0C | iPod on the **B** chamber (`B5` RX, `B10` TX, `B7` charge power). **No USB, no DAB.** |
| **MJ0D** | USB added (`L1`–`L5S`), DAB added (`N1`/`N2`), iPod relocated to chamber **D**, AUX to `A1`–`A4`. |
| MJ0D–MJ0G | stable; `MJ0F`→`MJ0G` differs only by cross-reference artifacts. **Our unit.** |
| MJ0H, MJ0J | different head unit: `MOST IN/OUT` replaces `OPTICAL WAVEGUIDE`, three LVDS pairs, `RESET CENTRAL COMPUTER`, a second CAN pair for the display control panel, LTE antennas. PCM 4.x split architecture. |

The later platform gained a discrete **`E5 POWER ON`** pin. Ours has no such
line, which is consistent with everything the bench has shown: power-on is
decided inside the box or over CAN, never by a wire.

> Data note: the `MJ0E` English file in the wiring set is actually German
> (`KL.30`, `MASSE`, `SCHIRM`, `LWL IN`). Diffing it against its neighbours
> produces dozens of phantom changes. Many projects in that set have no English
> branch at all — check the language before trusting a comparison.

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

The consequence for bench work is narrower than it first appears, and an
earlier version of this file overstated it. It claimed the PCM's CAN section
stays down without a gateway, both lines at 0 V, and that a gateway is
therefore the wake source. **Both claims were wrong** — they came from captures
taken at the wrong bitrate (100 k instead of 500 k) and in the CANable's broken
listen-only mode, which made a live bus look silent.

What is actually true, measured at 500 k:

- **The PCM transmits on terminal 30 alone**, six IDs: `539` `541` `5FA` `5FB`
  `6AB` `6D3`. No gateway needed to see traffic.
- A gateway does keep it awake indefinitely, where alone it sleeps after
  ~1.2 s — so the gateway is a convenience, not the wake source.
- Replaying all 23 gateway IDs verbatim, ignition asserted, still does not make
  the PCM report ignition on. See `CAN_MMI_BUS.md`.

Terminal 15 does still reach the PCM only as a CAN message, and the PCM samples
it at boot rather than watching it. That part stands.

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
