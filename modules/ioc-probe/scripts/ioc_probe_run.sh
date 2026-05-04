#!/bin/sh
# ioc_probe_run.sh — Wrapper for IOC probe
# Part of PCM-Forge

USBROOT="${1:-/fs/usb0}"
SCRIPTDIR="/scripts/IocProbe"

# Install probe script
mkdir -p "$SCRIPTDIR" 2>/dev/null
cp "$USBROOT/ioc-probe/scripts/ioc_probe.sh" "$SCRIPTDIR/" 2>/dev/null
chmod 755 "$SCRIPTDIR/ioc_probe.sh" 2>/dev/null

# Install ESD screens
for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs"; do
    if [ -d "$d" ] || mkdir -p "$d" 2>/dev/null; then
        for esd in "$USBROOT"/ioc-probe/engdefs/*.esd; do
            [ -f "$esd" ] && cp "$esd" "$d/" 2>/dev/null
        done
        break
    fi
done

# Run probe immediately
"$SCRIPTDIR/ioc_probe.sh"
