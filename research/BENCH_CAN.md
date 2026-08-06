# Bench CAN — what actually works

Measured 2026-08-03 against the bench PCM 3.1, and it corrects two things this
project believed for months.

## The infotainment bus is 500 kbps

**Not 100.** An earlier note recorded 100 kbps as "confirmed empirically" and it
was wrong. That single number sent a whole session of captures to a rate the bus
does not use, produced consistent silence, and from that silence a confident and
entirely false conclusion: that the unit was asleep and needed a gateway to wake
it. The unit had been transmitting the whole time.

Six IDs, captured with **terminal 30 alone** — no gateway, no ignition, nothing
but constant power and a keepalive:

| ID | ~rate | payload | notes |
|----|-------|---------|-------|
| `0x539` | 3.1/s | `XX 02 00 00 FE 01 00 00` | **byte 0 varies** |
| `0x541` | 3.1/s | all zeros | static |
| `0x5FA` | 0.8/s | `00 00 00 00 00 00 F8 FF` | static |
| `0x5FB` | 0.8/s | `00 00 00 00 00 00 00 7E` | static |
| `0x6AB` | 3.6/s | `00 00 00 00 00 00 00 XX` | **byte 7 varies** |
| `0x6D3` | 2.0/s | `01 01 00 00 00 00 00` | static |

Match on **ID, never on payload** — the two varying bytes move between runs.

## The PCM sleeps, and that is correct behaviour

It wakes on bus activity, transmits for about **1.2 seconds**, and goes quiet.
Five consecutive stir-and-listen cycles produced 21 frames over a 94–1289 ms
window every time, identical to the millisecond. That is not bus-off — bus-off
stays off until reset. It is a wake-capable transceiver doing exactly what it
should in a car with the ignition off.

The gateway board confirms the mechanism: it carries five **TJA1041AT** plus a
**TJA1040**, and the TJA1041 has a standby mode with remote wake over the bus.
The PCM almost certainly runs the same class of part.

**A keepalive every 50 ms holds it awake indefinitely** — 404 frames over 30 s
with all six IDs still transmitting at the end. That is the minimum restbus this
unit wants, and it needs no gateway.

## Adapter traps — CANable 2.0, `normaldotcom/canable2` firmware

Two behaviours that silently produce false negatives:

1. **Listen-only does not receive.** A sweep of all nine bitrates in listen-only
   returned zero frames at *every* rate including the correct one. That result
   looks like proof the bus is dead and is proof of nothing. Always open with
   `O` (normal).
2. **It will not receive until it has transmitted.** Opening at 500 k and
   listening passively gives nothing; transmit a burst first and the whole bus
   appears immediately.

The firmware is terse — it answers `V` with a version string but returns
*nothing* for `S`/`O`/`C`, so a script cannot distinguish an accepted bitrate
from a refused one by reply. It does not implement `F` (status), so error
counters are unavailable and TEC-style reasoning is impossible on this adapter.

## Working recipe

```
C  ->  S6 (500k)  ->  O  ->  transmit a burst  ->  read
```

`t<3-hex-id><dlc><data>` to send; received frames arrive in the same form.

## What the bench is actually made of

Read 2026-08-05 over CAN, no dealer tool. The gateway answers **UDS** on
`710`/`77A` on the **diagnostic** pair — not on CAN MMI, so it must be probed
through the OBD-side adapter; the same request on the MMI adapter gets nothing.

```
python pcm_slcan.py --port COM6 --target gateway --step version
```

| | VIN | part |
|---|---|---|
| gateway | `WP1AD2A22DLA79324` | `7PP907530Q` |
| PCM (Cayenne) | `WP1AA2A21DLA04395` | `7P5035884AB` |
| PCM (991, Spyderdoc) | `WP0AC2A84GK191352` | — |

Gateway detail: software `1043`, serial `2441B510013317`, system name
`zentr Gateway`, ODX id `CAN/CAN Gateway`, programming status `0x40` (valid
application).

**These are three different vehicles.** The gateway and the Cayenne PCM are
both 2013 Leipzig cars (`D` = model year, `L` = plant) but different serials —
`79324` against `04395` — and different model codes, `AD2A2` against `AA2A2`.

Worth stating because it will otherwise be mistaken for a fault: any coding,
component-list or VIN mismatch between the gateway and either PCM is **expected**
on this bench. Nothing here has ever been a matched set.

## Tools

`tools/bench-dongle/*.ps1` drive the adapter's serial port directly from
PowerShell — no Python needed on the bench machine.

| script | for |
|--------|-----|
| `canlisten.ps1` | plain capture, new IDs reported as they appear |
| `canwatch.ps1` | characterise: per-ID cadence, and which bytes are live vs fixed |
| `cankeep.ps1` | **hold the bus awake and capture** — the one to use |
| `canpoke.ps1` | repeated stir-and-listen; separates standby from bus-off |
| `cansweep.ps1` | bitrate sweep — but see the listen-only trap above |

Wiring: PCM **A11 → CAN-H**, **A9 → CAN-L**, ground to the PCM case. Pinout in
`CAYENNE_958_PINOUTS.md`.

## What this does not overturn

The connector facts still stand: there is no terminal 15 pin, and ignition does
reach the PCM as a CAN message from the gateway. That remains true. It simply is
not the reason the bus looked dead, and the unit is not silent without it.

Bluetooth is a good illustration — with terminal 30 only, pressing the power
knob brings BT up and a phone connects. USB does not, so the two are gated
differently and USB's blocker is elsewhere.
