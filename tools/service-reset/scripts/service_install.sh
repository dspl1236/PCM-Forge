#!/bin/sh
# service_install.sh — Deploy service reset to PCM 3.1
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

SCRIPTDIR="/scripts/ServiceReset"
LOGFILE="/fs/usb0/service_install.log"
USB="/fs/usb0"

# PCM 3.1 uses /HBpersistence for writable storage
# Engineering screens go in the EFS engdefs directory
ENGDIR=""
for d in "/mnt/efs-system/engdefs" "/mnt/flash/efs1/engdefs" "/HBpersistence/engdefs"; do
    if [ -d "$d" ] || mkdir -p "$d" 2>/dev/null; then
        ENGDIR="$d"
        break
    fi
done

echo "=== PCM-Forge Service Reset Install ===" > "$LOGFILE"
echo "EngDefs: $ENGDIR" >> "$LOGFILE"
echo "Date: $(date 2>/dev/null)" >> "$LOGFILE"

# Create script directory on head unit
mkdir -p "$SCRIPTDIR" 2>/dev/null

# Install ESD screens
for esd in ServiceStatus.esd ServiceReset.esd; do
    if [ -f "$USB/service-reset/engdefs/$esd" ]; then
        cp "$USB/service-reset/engdefs/$esd" "$ENGDIR/" 2>/dev/null
        echo "Installed: $esd → $ENGDIR/" >> "$LOGFILE"
    fi
done

# Install scripts
for script in service_status.sh service_reset.sh; do
    if [ -f "$USB/service-reset/scripts/$script" ]; then
        cp "$USB/service-reset/scripts/$script" "$SCRIPTDIR/" 2>/dev/null
        chmod 755 "$SCRIPTDIR/$script" 2>/dev/null
        echo "Installed: $script" >> "$LOGFILE"
    fi
done

# Install native binary
if [ -f "$USB/service-reset/bin/uds_send" ]; then
    cp "$USB/service-reset/bin/uds_send" "$SCRIPTDIR/" 2>/dev/null
    chmod 755 "$SCRIPTDIR/uds_send" 2>/dev/null
    echo "Installed: uds_send" >> "$LOGFILE"
fi

echo "" >> "$LOGFILE"
echo "Done. Reboot PCM, then: GEM > Car > ServiceReset" >> "$LOGFILE"
