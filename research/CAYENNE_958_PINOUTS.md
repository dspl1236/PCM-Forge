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

## Still to transcribe

- [ ] PCM / head unit quadlock — which pins carry CAN MMI, and terminal 15
- [ ] Which modules terminate the MMI bus
- [ ] Node identities behind the MMI sheet references listed above
- [ ] Comfort, Drive, Chassis bus participants
- [ ] PCM power-up requirements (which rails gate the CAN section)
