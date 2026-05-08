#!/bin/sh
# sysinfo_run.sh — Run system info dump
# Part of PCM-Forge

USBROOT="${1:-/fs/usb0}"

if [ -f "$USBROOT/scripts/sysinfo_dump.sh" ]; then
    ksh "$USBROOT/scripts/sysinfo_dump.sh"
else
    echo "ERROR: sysinfo_dump.sh not found" >> "$USBROOT/sysinfo.log"
fi
