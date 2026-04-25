#!/bin/sh
# service_reset.sh — Execute oil/inspection reset via UDS to cluster
# Usage: service_reset.sh [oil|inspection|all]
#
# DIDs derived from VCDS IDE channel numbers (decimal → hex)
# Confirmed via Ross-Tech wiki + Club Touareg forum posts
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

MODE="${1:-all}"
USBROOT="${2:-/fs/usb0}"
LOG="${USBROOT}/service_reset.log"
BINDIR="${USBROOT}/bin"

# === UDS Data Identifiers for Cayenne 958 / Touareg 7P Cluster ===
# IDE00342 = 342 dec = 0x0156 | IDE03351 = 3351 dec = 0x0D17
# IDE03352 = 3352 dec = 0x0D18
DID_OIL_RESET="0156"   # IDE00342-ESI: oil service reset
DID_INSP_DIST="0D17"   # IDE03351-FIX: distance since inspection → write 0
DID_INSP_TIME="0D18"   # IDE03352-FIX: time since inspection → write 0

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
    
    # Split DIDs into high/low bytes for uds_send
    OIL_HI="0x$(echo $DID_OIL_RESET | cut -c1-2)"
    OIL_LO="0x$(echo $DID_OIL_RESET | cut -c3-4)"
    DST_HI="0x$(echo $DID_INSP_DIST | cut -c1-2)"
    DST_LO="0x$(echo $DID_INSP_DIST | cut -c3-4)"
    TIM_HI="0x$(echo $DID_INSP_TIME | cut -c1-2)"
    TIM_LO="0x$(echo $DID_INSP_TIME | cut -c3-4)"

    # Step 1: Extended diagnostic session
    echo ">> DiagnosticSessionControl Extended" >> "$LOG"
    "$BINDIR/uds_send" 0x17 0x10 0x03 >> "$LOG" 2>&1
    sleep 1

    case "$MODE" in
        oil)
            echo ">> Reset oil service (IDE00342 = 0x$DID_OIL_RESET)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $OIL_HI $OIL_LO 0x00 >> "$LOG" 2>&1
            ;;
        inspection)
            echo ">> Reset distance (IDE03351 = 0x$DID_INSP_DIST)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $DST_HI $DST_LO 0x00 0x00 0x00 0x00 >> "$LOG" 2>&1
            sleep 1
            echo ">> Reset time (IDE03352 = 0x$DID_INSP_TIME)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $TIM_HI $TIM_LO 0x00 0x00 0x00 0x00 >> "$LOG" 2>&1
            ;;
        all)
            echo ">> Reset oil service (IDE00342 = 0x$DID_OIL_RESET)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $OIL_HI $OIL_LO 0x00 >> "$LOG" 2>&1
            sleep 1
            echo ">> Reset distance (IDE03351 = 0x$DID_INSP_DIST)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $DST_HI $DST_LO 0x00 0x00 0x00 0x00 >> "$LOG" 2>&1
            sleep 1
            echo ">> Reset time (IDE03352 = 0x$DID_INSP_TIME)" >> "$LOG"
            "$BINDIR/uds_send" 0x17 0x2E $TIM_HI $TIM_LO 0x00 0x00 0x00 0x00 >> "$LOG" 2>&1
            ;;
    esac
    echo "Reset sent. Check cluster." >> "$LOG"
else
    echo "ERROR: uds_send binary not found at $BINDIR/uds_send" >> "$LOG"
    echo "Build from src/uds_send.c (SH4 cross-compile)" >> "$LOG"
    echo "Or use ESP32 on OBD-II as alternative" >> "$LOG"
    exit 1
fi
