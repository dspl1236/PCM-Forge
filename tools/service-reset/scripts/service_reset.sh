#!/bin/sh
# service_reset.sh — Execute oil/inspection reset via UDS to cluster
# Usage: service_reset.sh [oil|inspection|all]
#
# !! DIDs are PLACEHOLDERS — must be confirmed via CAN capture !!
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

MODE="${1:-all}"
LOG="/fs/usb0/service_reset.log"
BINDIR="/scripts/ServiceReset"

# === PLACEHOLDER DIDs — REPLACE WITH REAL VALUES ===
# Get these by CAN-capturing a Durametric/iCarScan reset
# or extracting from EV_KombiUDSRBVW526.rod ODX file
DID_OIL_RESET="0000"   # IDE00342-ESI: oil service reset
DID_INSP_DIST="0000"   # IDE03351-FIX: distance since inspection → write 0
DID_INSP_TIME="0000"   # IDE03352-FIX: time since inspection → write 0

echo "=== PCM-Forge Service Reset ===" > "$LOG"
echo "Mode: $MODE" >> "$LOG"

# Safety check
if [ "$DID_OIL_RESET" = "0000" ]; then
    echo "ERROR: DID values are placeholders!" >> "$LOG"
    echo "" >> "$LOG"
    echo "To get real DIDs:" >> "$LOG"
    echo "  1. CAN capture during Durametric/iCarScan reset" >> "$LOG"
    echo "  2. VCDS module 17 adaptation on Cayenne/Touareg" >> "$LOG"
    echo "  3. Parse EV_KombiUDSRBVW526.rod from ODIS/PIWIS" >> "$LOG"
    echo "" >> "$LOG"
    echo "Then edit: $BINDIR/service_reset.sh" >> "$LOG"
    echo "  DID_OIL_RESET=XXXX" >> "$LOG"
    echo "  DID_INSP_DIST=XXXX" >> "$LOG"
    echo "  DID_INSP_TIME=XXXX" >> "$LOG"
    exit 1
fi

# Use native binary if available
if [ -x "$BINDIR/uds_send" ]; then
    echo "Using native UDS sender" >> "$LOG"
    
    # Step 1: Extended diagnostic session
    "$BINDIR/uds_send" 0x17 0x10 0x03 >> "$LOG" 2>&1
    sleep 1

    case "$MODE" in
        oil)
            "$BINDIR/uds_send" 0x17 0x2E $DID_OIL_RESET >> "$LOG" 2>&1
            ;;
        inspection)
            "$BINDIR/uds_send" 0x17 0x2E $DID_INSP_DIST 0x00 0x00 >> "$LOG" 2>&1
            sleep 1
            "$BINDIR/uds_send" 0x17 0x2E $DID_INSP_TIME 0x00 0x00 >> "$LOG" 2>&1
            ;;
        all)
            "$BINDIR/uds_send" 0x17 0x2E $DID_OIL_RESET >> "$LOG" 2>&1
            sleep 1
            "$BINDIR/uds_send" 0x17 0x2E $DID_INSP_DIST 0x00 0x00 >> "$LOG" 2>&1
            sleep 1
            "$BINDIR/uds_send" 0x17 0x2E $DID_INSP_TIME 0x00 0x00 >> "$LOG" 2>&1
            ;;
    esac
    echo "Reset sent. Check cluster." >> "$LOG"
else
    echo "ERROR: uds_send binary not found at $BINDIR/uds_send" >> "$LOG"
    echo "Build from src/uds_send.c (SH4 cross-compile)" >> "$LOG"
    echo "Or use ESP32 on OBD-II as alternative" >> "$LOG"
    exit 1
fi
