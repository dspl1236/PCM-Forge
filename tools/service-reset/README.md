# service-reset — Oil & Inspection Reset for Cayenne 958

Reset oil service and inspection intervals from the PCM touchscreen.
No PIWIS. No Durametric. No dealer.

## Status: READY — DIDs Confirmed

DID values derived from VCDS IDE channel numbers (decimal → hex conversion).
Confirmed via Ross-Tech wiki and Club Touareg forum documentation.

### UDS Data Identifiers

| IDE Channel | Function | Hex DID | UDS Command |
|---|---|---|---|
| IDE00342-ESI | Oil service reset trigger | `0x0156` | `2E 01 56` |
| IDE03351-FIX | Distance since inspection | `0x0D17` | `2E 0D 17 00 00` |
| IDE03352-FIX | Time since inspection | `0x0D18` | `2E 0D 18 00 00` |

### Additional Channels

| IDE Channel | Function | Hex DID |
|---|---|---|
| IDE00510-SEI | Service interval (soot) | `0x01FE` |
| IDE00511-ESI | Extended service interval | `0x01FF` |

## How it works

```
USB stick with copie_scr.sh
  → service_install.sh deploys to PCM
  → GEM > Car > ServiceReset screen appears
  → Press "RESET OIL SERVICE" button
  → service_reset.sh runs uds_send binary
  → devctl(/dev/ndr/cmd) → IOC → CAN → cluster module 0x17
  → UDS 0x2E WriteDataByIdentifier resets the counter
```

## Files

```
tools/service-reset/
├── module.json              Config
├── README.md                This file
├── engdefs/
│   ├── ServiceStatus.esd    GEM: read service data
│   └── ServiceReset.esd     GEM: reset buttons
├── scripts/
│   ├── service_install.sh   Deploy via copie_scr.sh
│   ├── service_status.sh    Log IOC/NDR/CAN state
│   └── service_reset.sh     Execute reset (needs DIDs)
└── src/
    └── uds_send.c           Native SH4 UDS sender
```

## Once you have the DIDs

Edit `scripts/service_reset.sh`:
```sh
DID_OIL_RESET="ABCD"   # real value for IDE00342
DID_INSP_DIST="EFGH"   # real value for IDE03351
DID_INSP_TIME="IJKL"   # real value for IDE03352
```

## Background

Porsche compiled PCM 3.1 WITHOUT the `CarKombiPresCtrl` / `InspectionReset`
code that exists in the Audi MMI3G+. The Audi has 228 CarKombi references
and 11 InspectionReset functions. The Porsche has zero.

See `research/OIL_SERVICE_RESET_ANALYSIS.md` for the full firmware comparison.

The cluster hardware (VDO PL72) and UDS dataset (`EV_KombiUDSRBVW526`) are
shared with the VW Touareg 7P. Same DIDs, same protocol — Porsche just
blocks the head unit from sending the reset command.
