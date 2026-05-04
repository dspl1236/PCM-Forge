#!/bin/sh
# ioc_install.sh — Deploy IOC probe to PCM 3.1
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
SCRIPTDIR="/scripts/IocProbe"
LOG="$USB/ioc_install.log"

echo "=== PCM-Forge IOC Probe Install ===" > "$LOG"

# Create script directory
mkdir -p "$SCRIPTDIR" 2>/dev/null

# Install probe script
if [ -f "$USB/ioc-probe/scripts/ioc_probe.sh" ]; then
    cp "$USB/ioc-probe/scripts/ioc_probe.sh" "$SCRIPTDIR/" 2>/dev/null
    chmod 755 "$SCRIPTDIR/ioc_probe.sh" 2>/dev/null
    echo "Installed: ioc_probe.sh" >> "$LOG"
fi

# Install ESD screen
ENGDIR=""
for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs" "/mnt/flash/efs1/engdefs"; do
    if [ -d "$d" ] || mkdir -p "$d" 2>/dev/null; then
        ENGDIR="$d"
        break
    fi
done

if [ -n "$ENGDIR" ]; then
    for esd in "$USB"/ioc-probe/engdefs/*.esd; do
        if [ -f "$esd" ]; then
            cp "$esd" "$ENGDIR/" 2>/dev/null
            echo "Installed: $(basename $esd) → $ENGDIR/" >> "$LOG"
        fi
    done
fi

# Run the probe immediately
echo "" >> "$LOG"
echo "Running probe..." >> "$LOG"
"$SCRIPTDIR/ioc_probe.sh" >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "Done. Reboot PCM, then: GEM > System > IocProbe" >> "$LOG"
