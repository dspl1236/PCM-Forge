#!/bin/sh
# ioc_probe_run.sh — Run IOC & BAP probe
# Part of PCM-Forge

USBROOT="${1:-/fs/usb0}"

# Run probe directly from USB
if [ -f "$USBROOT/scripts/ioc_probe.sh" ]; then
    ksh "$USBROOT/scripts/ioc_probe.sh"
else
    echo "ERROR: ioc_probe.sh not found" >> "$USBROOT/ioc_probe.log"
fi

# Run ch6 traffic capture
if [ -f "$USBROOT/scripts/ch6_capture.sh" ]; then
    ksh "$USBROOT/scripts/ch6_capture.sh"
fi
