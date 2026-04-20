# service-reset — Oil & Inspection Reset for Cayenne 958

Reset oil service and inspection intervals from the PCM touchscreen.
No PIWIS. No Durametric. No dealer.

## Status: FRAMEWORK READY — Blocked on 3 hex values

Everything is built. The tool refuses to run until the placeholder DIDs are
replaced with real values from the Cayenne 958 cluster.

### What's needed

| IDE Channel | Function | DID | Status |
|---|---|---|---|
| IDE00342-ESI | Oil service reset | `0x????` | **UNKNOWN** |
| IDE03351-FIX | Distance since inspection | `0x????` | **UNKNOWN** |
| IDE03352-FIX | Time since inspection | `0x????` | **UNKNOWN** |

### How to get them

1. **CAN capture** — sniff OBD-II while iCarScan/Durametric resets
2. **VCDS** — module 17 → Adaptation dropdown on Cayenne or Touareg 7P
3. **ODX** — parse `EV_KombiUDSRBVW526.rod` from PIWIS/ODIS

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
