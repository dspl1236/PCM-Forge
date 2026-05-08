#!/bin/sh
# ioc_probe_run.sh — Wrapper for IOC probe
# Part of PCM-Forge

USBROOT="${1:-/fs/usb0}"

# Run probe directly from USB (root filesystem is read-only)
PROBE=""
if [ -f "$USBROOT/scripts/ioc_probe.sh" ]; then
    PROBE="$USBROOT/scripts/ioc_probe.sh"
elif [ -f "$USBROOT/ioc-probe/scripts/ioc_probe.sh" ]; then
    PROBE="$USBROOT/ioc-probe/scripts/ioc_probe.sh"
fi

if [ -n "$PROBE" ]; then
    chmod 755 "$PROBE" 2>/dev/null
    ksh "$PROBE"
else
    echo "ERROR: ioc_probe.sh not found" >> "$USBROOT/ioc_probe.log"
    echo "Searched:" >> "$USBROOT/ioc_probe.log"
    echo "  $USBROOT/scripts/ioc_probe.sh" >> "$USBROOT/ioc_probe.log"
    echo "  $USBROOT/ioc-probe/scripts/ioc_probe.sh" >> "$USBROOT/ioc_probe.log"
    ls -laR "$USBROOT/scripts/" >> "$USBROOT/ioc_probe.log" 2>&1
fi

# Install ESD screens (HBpersistence IS writable)
for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs"; do
    if [ -d "$d" ] || mkdir -p "$d" 2>/dev/null; then
        for esd in "$USBROOT"/engdefs/*.esd "$USBROOT"/ioc-probe/engdefs/*.esd; do
            [ -f "$esd" ] && cp "$esd" "$d/" 2>/dev/null
        done
        break
    fi
done

# Run cluster scan
if [ -f "$USBROOT/scripts/cluster_scan.sh" ]; then
    ksh "$USBROOT/scripts/cluster_scan.sh"
fi

# Run BAP channel scan
if [ -f "$USBROOT/scripts/bap_channel_scan.sh" ]; then
    ksh "$USBROOT/scripts/bap_channel_scan.sh"
fi
