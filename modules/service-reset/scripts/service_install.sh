#!/bin/ksh
# service_install.sh — Deploy service reset ESD screens + tools to PCM 3.1
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge
#
# Deploys ServiceStatus.esd and ServiceReset.esd to the engineering menu.
# After install, reboot PCM -> press SOURCE+SOUND -> Car -> ServiceStatus/ServiceReset

USBROOT="${1:-/fs/usb0}"
LOGFILE="${USBROOT}/service_install.log"
SCRIPTDIR="/scripts/ServiceReset"

{
echo "============================================"
echo "  PCM-Forge Service Reset Install"
echo "============================================"
echo ""

# Find writable engdefs directory
ENGDIR=""
for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs" "/mnt/flash/efs1/engdefs"; do
    if [ -d "$d" ]; then
        ENGDIR="$d"
        echo "[OK] Found engdefs: $d"
        break
    fi
done

if [ -z "$ENGDIR" ]; then
    for d in "/HBpersistence/engdefs" "/mnt/efs-system/engdefs"; do
        mkdir -p "$d" 2>/dev/null
        if [ -d "$d" ]; then
            ENGDIR="$d"
            echo "[OK] Created engdefs: $d"
            break
        fi
    done
fi

if [ -z "$ENGDIR" ]; then
    echo "[ERROR] No writable engdefs directory found"
    exit 1
fi

echo ""
echo "=== Existing ESD files ==="
ls -la "$ENGDIR/" 2>&1

echo ""
echo "=== Installing ESD screens ==="
for esd in ServiceStatus.esd ServiceReset.esd; do
    SRC="${USBROOT}/service-reset/engdefs/${esd}"
    if [ -f "$SRC" ]; then
        cp "$SRC" "${ENGDIR}/${esd}" 2>/dev/null
        chmod 644 "${ENGDIR}/${esd}" 2>/dev/null
        echo "[OK] ${esd} -> ${ENGDIR}/"
    else
        echo "[SKIP] ${esd} not found at ${SRC}"
    fi
done

echo ""
echo "=== Installing scripts ==="
mkdir -p "$SCRIPTDIR" 2>/dev/null
for script in service_reset.sh service_status.sh service_run.sh; do
    SRC="${USBROOT}/service-reset/scripts/${script}"
    if [ -f "$SRC" ]; then
        cp "$SRC" "${SCRIPTDIR}/${script}" 2>/dev/null
        chmod 755 "${SCRIPTDIR}/${script}" 2>/dev/null
        echo "[OK] ${script}"
    fi
done

echo ""
echo "=== Installing uds_send binary ==="
SRC="${USBROOT}/service-reset/bin/uds_send"
if [ -f "$SRC" ]; then
    cp "$SRC" "${SCRIPTDIR}/uds_send" 2>/dev/null
    chmod 755 "${SCRIPTDIR}/uds_send" 2>/dev/null
    echo "[OK] uds_send deployed"
else
    echo "[SKIP] uds_send not found (ServiceStatus ESD still works without it)"
fi

echo ""
echo "=== Installed files ==="
ls -la "${ENGDIR}/"*.esd 2>&1
ls -la "${SCRIPTDIR}/" 2>&1

echo ""
echo "============================================"
echo "  Install complete!"
echo ""
echo "  Reboot PCM (hold INFO+CAR)"
echo "  Press SOURCE+SOUND for engineering menu"
echo "  Go to: Car -> ServiceStatus / ServiceReset"
echo ""
echo "  ServiceStatus reads service data (no binary needed)"
echo "  ServiceReset sends UDS reset (needs uds_send)"
echo "============================================"
} > "$LOGFILE" 2>&1

echo "service-reset installed" >> "${USBROOT}/pcm_ran.txt"
