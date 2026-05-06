#!/bin/sh
# ioc_probe_run.sh — Wrapper for IOC probe
# Part of PCM-Forge

USBROOT="${1:-/fs/usb0}"
SCRIPTDIR="/scripts/IocProbe"

# Install probe script
# Web app places files at $USBROOT/scripts/ (flat structure)
mkdir -p "$SCRIPTDIR" 2>/dev/null
if [ -f "$USBROOT/scripts/ioc_probe.sh" ]; then
    cp "$USBROOT/scripts/ioc_probe.sh" "$SCRIPTDIR/" 2>/dev/null
elif [ -f "$USBROOT/ioc-probe/scripts/ioc_probe.sh" ]; then
    cp "$USBROOT/ioc-probe/scripts/ioc_probe.sh" "$SCRIPTDIR/" 2>/dev/null
fi
chmod 755 "$SCRIPTDIR/ioc_probe.sh" 2>/dev/null

# Install ESD screens
for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs"; do
    if [ -d "$d" ] || mkdir -p "$d" 2>/dev/null; then
        for esd in "$USBROOT"/engdefs/*.esd "$USBROOT"/ioc-probe/engdefs/*.esd; do
            [ -f "$esd" ] && cp "$esd" "$d/" 2>/dev/null
        done
        break
    fi
done

# Run probe immediately
if [ -x "$SCRIPTDIR/ioc_probe.sh" ]; then
    "$SCRIPTDIR/ioc_probe.sh"
else
    echo "ERROR: ioc_probe.sh not found" >> "$USBROOT/ioc_probe.log"
    ls -la "$USBROOT/scripts/" >> "$USBROOT/ioc_probe.log" 2>&1
fi
