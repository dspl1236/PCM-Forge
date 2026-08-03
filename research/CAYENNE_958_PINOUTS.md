# Cayenne 92A / 958 — Connector Pinouts

> Source: **PIWIS3 wiring diagrams**, Cayenne (92A) Model Year 2012 (C), read in
> the PIWIS3 PassThru VM. This information is not published anywhere public —
> searches turn up only parts listings. Recorded here so bench work doesn't
> depend on having PIWIS running.

Everything below is transcribed from OEM diagrams. Where a value is inferred
rather than read off a sheet, it says so.

## Notation

Porsche wire labels are `<colour><tracer> <cross-section>`, e.g. `OG VT 0.35`
is orange with a violet tracer, 0.35 mm².

| code | colour | code | colour |
|------|--------|------|--------|
| BK | black | OG | orange |
| BN | brown | RD | red |
| BU | blue | VT | violet |
| GN | green | WH | white |
| GY | grey | YE | yellow |

Destination codes like `/30A.4G` are cross-references: sheet 30A, grid square
4G. `Y4xx` / `SP_SCxx_P` markers are splice points, and `SLxxxxx` numbers are
wire/segment identifiers.

## Gateway control unit — SGGW_P (A010.1)

20-pin connector. This is the `7PP907530x` central gateway.

| pin | signal | pin | signal |
|-----|--------|-----|--------|
| A1 | **TERM. 30** (constant +12 V) | A11 | **TERM. 31** (ground) |
| A2 | LIN 1 | A12 | LIN 2 |
| A3 | FLEXRAY | A13 | SHIELD |
| A4 | FLEXRAY | A14 | **TERM. 15** (switched ignition) |
| A5 | CAN COMFORT LOW | A15 | CAN COMFORT HIGH |
| A6 | CAN DRIVE LOW | A16 | CAN DRIVE HIGH |
| A7 | CAN CRASH LOW | A17 | CAN CRASH HIGH |
| **A8** | **CAN MMI LOW** | **A18** | **CAN MMI HIGH** |
| A9 | CAN DIAGNOSTICS LOW | A19 | CAN DIAGNOSTICS HIGH |
| A10 | CAN CHASSIS LOW | A20 | CAN CHASSIS HIGH |

Six independent CAN buses, plus FlexRay and two LIN channels.

**CAN MMI (A8 / A18) is the PCM's infotainment bus, and it is a separate bus
from CAN COMFORT.** This distinction matters: low-speed fault-tolerant
(ISO 11898-3) physical-layer research generally concerns the *comfort* domain,
and none of it automatically applies to MMI.

## Diagnostic plug socket — DD_P (X001.1)

16-pin OBD-II socket.

| pin | signal | wire |
|-----|--------|------|
| 1 | **TERM. 15** | BK BU 0.5 |
| 2, 3 | not connected | |
| 4 | TERM. 31 (ground) | BN BN 0.5 |
| 5 | TERM. 31 (ground) | BN BU 0.5 |
| **6** | **CAN DIAGNOSTICS HIGH** | OG GY 0.35 |
| 7–13 | not connected | |
| **14** | **CAN DIAGNOSTICS LOW** | OG BN 0.35 |
| 15 | AIRBAG TRIGGERING | BU GY 0.5 |
| 16 | TERM. 30 | RD YE 0.5 |

Pins 6 and 14 are the standard OBD-II CAN pair. **Pin 1 carries terminal 15** —
Porsche uses the manufacturer-discretionary pin for switched ignition, which is
convenient on a bench: the OBD connector alone can supply both power rails and
the ignition signal.

Pin 15 is airbag triggering. Do not probe or inject there.

## PCM head unit — P100.1

Housing `B44LWL04A02`. Multi-chamber connector; chambers are lettered and pins
numbered within each chamber.

### PCMA_P — power and CAN

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

**Pin 9 is CAN LOW and pin 11 is CAN HIGH.** Widely-repeated forum guidance has
these reversed ("CAN-High and CAN-Low are pins 9 and 11 respectively") — that is
wrong per the OEM sheet. Swapping H and L does not degrade a CAN link, it stops
it dead: dominant bits arrive inverted and read as recessive, so the bus appears
permanently idle with no frames and no ACK. Verify by **wire colour**, which is
independent of pin counting and matches the gateway end:

    OG VT (orange/violet) = CAN HIGH  -> gateway A18
    OG BN (orange/brown)  = CAN LOW   -> gateway A8

**There is no TERM. 15 on this connector.** The PCM has only constant power
(A15) and ground (A12) — no ignition input. It must therefore be woken over
**CAN**, or via **RING BREAK DIAGNOSIS** (A16), the MOST ring's wake/diagnostic
line. On a bench with neither a gateway nor a MOST ring present, nothing ever
tells the PCM to wake: the CAN transceiver stays unpowered, both bus lines sit
at 0 V, and the unit will light its display and answer the power button while
transmitting nothing. A gateway is not a convenience for bench work — it is the
wake source.

### Other chambers

| chamber | pins | carries |
|---------|------|---------|
| PCMB_P | B1–B8 | speakers: rear right ±, front right ±, front left ±, rear left ± |
| PCMC_P | C1–C12 | microphone ± and shield, switched output amplifier, video signal, video GND, Bluetooth handset |
| PCMD_P | D1–D12 | iPod acc det / charge GND / charge power / accessory ident, iPod CON RX+TX, AUX 1 IN L+ / R+, AUX-1-RETURN, AUX shield |
| — | E1, E2 | **OPTICAL WAVEGUIDE IN / OUT** (MOST ring) |
| — | F1, F2 | OPTICAL WAVEGUIDE IN / OUT (second pair) |
| PCMG_P | G1, G2 | RADIO HF IN, shield |
| PCMH_P | H1, H2 | SDARS ANTENNA, shield |
| PCMJ_P | J1, J2 | GPS HF IN, shield |
| PCMK_P | K1, K2 | TELEPHONE HF IN, shield |
| PCML_P | L1–L5S | USB: DATA + (BU BU 0.14), VUSB (BN BN 0.14), DATA − (GN GN 0.14), GROUND (OG OG 0.14), shield (BK BK 1.0) |
| PCMM_P | M1–M5S | LVDS −, GROUND, LVDS +, GROUND, shield — the display link |
| PCMN_P | N1, N2 | DAB ANTENNA, shield |

The optical waveguide pairs cross-reference to sheet 39 (`LVL SEE SHEET 39`).

### Minimum bench harness

Only four pins are needed to power a PCM and put it on a bus:

    A15  TERM. 30F   -> +12 V constant
    A12  TERM. 31    -> ground
    A11  CAN HIGH    -> gateway A18  (OG VT)
    A9   CAN LOW     -> gateway A8   (OG BN)

Add `A16 RING BREAK DIAGNOSIS` if experimenting with MOST-side wake. Speakers
are `B1`–`B8` and USB is `PCML_P` if audio or mass storage is wanted.

Chambers A–D follow the standard VAG quadlock layout, so an Audi quadlock
housing fits physically. **The pin assignments do not carry over** — populate by
the Porsche numbers above and disregard what a donor Audi harness's wire colours
originally meant.

## External connectors on this sheet

### T020.1 — antenna amplifier, left side window (`DABB_P`)

| pin | signal |
|-----|--------|
| A1 | SUPPLY |
| A2, A3 | not connected |
| B1 | DAB ANTENNA |
| B2 | SHIELD |
| C1 | TV OUT |
| C2 | SHIELD |

TV tuner connection cross-references to sheet 25.

### X816.1 — TSX816 universal audio interface

The AUX/USB interface box, relevant to the AUX and Bluetooth source work.

| chamber | pin | signal |
|---------|-----|--------|
| AUX_P | A1 | AUX RETURN |
| | A2 | AUX L+ |
| | A3 | AUX R+ |
| | A4 | AUX SHIELD |
| USB_P | B1 | USB GROUND |
| | B2 | DATA − |
| | B3 | VUSB |
| | B4 | DATA + |
| | B5S | SHIELD |

Note this sheet shows the **fully-optioned** variant — DAB, TV tuner, SDARS,
iPod, telephone. A given car populates only what it was built with.

## CAN MMI bus topology

The MMI bus leaves the gateway on A18 / A8 and fans out through four splice
points to roughly eight nodes.

```
gateway A18 (CAN MMI HIGH, OG VT 0.35, wire 50123)
gateway A8  (CAN MMI LOW,  OG BN 0.35, wire 50124)
        |
   Y450 SP_SC50_P ---- Y454 SP_SC54_P
   Y451 SP_SC51_P ---- Y455 SP_SC55_P
        |
   drops to nodes at sheet refs:
   /30A.4G  /05.13G  /20A.6G  /20B.4G  /04.4G  /04.3G  /20.3G
   /05G.6G  /36.7G   /35.9G   /35.8G
```

Every drop is an `OG BN 0.35` / `OG VT 0.35` pair, consistent with the gateway
end. Node identities behind those sheet references are not yet transcribed.

## Bench harness

Minimum wiring to bring a gateway up on the bench with a PCM attached:

```
A1   TERM 30        -> +12 V constant
A14  TERM 15        -> +12 V switched
A11  TERM 31        -> ground

A19  CAN DIAG HIGH  -> USB-CAN H     (equivalently OBD pin 6)
A9   CAN DIAG LOW   -> USB-CAN L     (equivalently OBD pin 14)

A18  CAN MMI HIGH   -> PCM
A8   CAN MMI LOW    -> PCM
```

Termination is per-segment. Measure each pair unpowered before connecting:
60 Ω means two terminators are already present, 120 Ω means one, and anything
near 40 Ω means too many. See `tools/bench-dongle/` for the capture scripts.

## CAN MMI participants

From the `(07A) CAN TOPOLOGY` sheet. Nine nodes share this bus:

    GATEWAY          RADIO/PCM              INSTRUMENT CLUSTER
    COMPASS          AIR CONDIT. CONTROL UNIT
    PDC              PDC CONTROL UNIT
    CAN ADAPTER      CU PARKING HEATER

Splices SC50/51 and SC54/55.

A bench PCM has **zero** peers where the car gives it eight. That matters for
more than ACK: a node transmitting with nothing to acknowledge it accumulates
TEC by 8 per attempt and goes **bus-off at 255, ceasing to transmit entirely**.
A lone bench PCM will therefore talk briefly after power-up and then fall
permanently silent until reset — so a capture must be running *before* the unit
boots, and in normal (ACKing) mode, or it records nothing and proves nothing.

## What the gateway tells the PCM

From the `FUNCTION FLOW - PCM 3.1` sheet. Gateway to PCM, over CAN MMI:

    LOAD SWITCH-OFF STATUS        DRIVER DOOR STATUS
    ANTI-THEFT WARNING SYSTEM     MEMORY BUTTON STATUS
    PSM STATUS                    IMAGE OUTPUT ON
    PDK STATUS                    RADIO KEY
    EPS STATUS                    **TERM. 15**
    MSW STATUS                    S CONTACT
    UPS STATUS                    MANUAL RC
    CLSM STATUS
    PTT STATUS

**TERM. 15 arrives as a CAN message, not a wire.** This is why the PCM
connector has no ignition pin — the head unit is *told* the ignition is on by
the gateway. A bench unit with no gateway is never told, so it has no reason to
bring up or hold up its CAN section, which explains a unit that powers on,
lights its display, answers the power button, and transmits nothing.

Making a bench PCM believe it is in a car therefore reduces to a concrete task:
**transmit the frame carrying TERM. 15 and S CONTACT**. The ID and layout are
not yet known. The cleanest way to learn them is to sniff pins A9/A11 at the
PCM connector *in a running car* — CAN MMI sits behind the gateway and is not
reachable from the OBD port.

Other flows worth noting:

| from | over | signals |
|------|------|---------|
| Instrument cluster | CAN MMI | MCNET, indiv. memory, GPS time/status, **odometer**, cluster status, light sensor |
| Instrument cluster | LVDS | map display |
| PDC | CAN MMI | top-view display on/off, distance information, display readiness |
| A/C unit, front | CAN MMI | fresh air fan stage, sun intensity |
| MFL steering wheel | LIN → CLSM → CAN Comfort → gateway → CAN MMI | MSW status, PTT status |
| TV tuner, sound packages | MOST | video signal, audio signal |
| UAI | USB / serial (iPod) / AUX | — |

The odometer on CAN MMI is a second source for service-interval work,
independent of the DSI `SPHLogBook` route.

## Still to transcribe

- [x] ~~PCM quadlock — which pins carry CAN MMI, and terminal 15~~ (A9/A11; no
      terminal 15 exists — the PCM wakes over CAN or the MOST ring)
- [ ] Which modules terminate the MMI bus
- [ ] Node identities behind the MMI sheet references listed above
- [ ] Comfort, Drive, Chassis bus participants
- [ ] PCM power-up requirements (which rails gate the CAN section)
