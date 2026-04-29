#!/bin/ksh
# ============================================================
# PCM-Forge — NDR devctl Probe v2
# Uses DCMD constants extracted from NavigationNdrInfo binary
# SAFE: read-only operations only, no CAN bus writes
# ============================================================

USBROOT="${1:-/fs/usb0}"
BINDIR="${USBROOT}/bin"
LOGFILE="${USBROOT}/ndr_probe_v2.log"

echo "============================================" > "${LOGFILE}"
echo "  PCM-Forge NDR devctl Probe v2" >> "${LOGFILE}"
echo "============================================" >> "${LOGFILE}"
echo "" >> "${LOGFILE}"

# Deploy probe binary to /tmp
if [ -f "${BINDIR}/ndr_probe_v2" ]; then
    cp "${BINDIR}/ndr_probe_v2" /tmp/ndr_probe_v2
    chmod +x /tmp/ndr_probe_v2
    echo "[OK] ndr_probe_v2 deployed to /tmp" >> "${LOGFILE}"
    ls -la /tmp/ndr_probe_v2 >> "${LOGFILE}"
else
    echo "[ERROR] ndr_probe_v2 not found at ${BINDIR}" >> "${LOGFILE}"
    exit 1
fi

echo "" >> "${LOGFILE}"
echo "=== NDR Device ===" >> "${LOGFILE}"
ls -la /dev/ndr/ >> "${LOGFILE}" 2>&1

echo "" >> "${LOGFILE}"
echo "=== IOC Channels ===" >> "${LOGFILE}"
ls -la /dev/ipc/ioc/ >> "${LOGFILE}" 2>&1

echo "" >> "${LOGFILE}"
echo "=== Running NDR Process ===" >> "${LOGFILE}"
pidin ar | grep ndr >> "${LOGFILE}" 2>&1

echo "" >> "${LOGFILE}"
echo "=== Running Probe ===" >> "${LOGFILE}"
/tmp/ndr_probe_v2 "${USBROOT}" >> "${LOGFILE}" 2>&1

echo "" >> "${LOGFILE}"
echo "=== Probe Complete ===" >> "${LOGFILE}"
