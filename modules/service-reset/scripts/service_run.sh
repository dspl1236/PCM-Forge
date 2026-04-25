#!/bin/ksh
# PCM-Forge Service Reset — Full diagnostic + reset
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"
LOG="${USBROOT}/service_reset.log"

{
echo "============================================"
echo "  PCM-Forge Service Reset"
echo "  $(date 2>/dev/null || echo 'no date cmd')"
echo "============================================"
echo ""

# Deploy uds_send binary to /tmp (writable)
if [ -f "${USBROOT}/bin/uds_send" ]; then
    cp "${USBROOT}/bin/uds_send" /tmp/uds_send
    chmod +x /tmp/uds_send
    echo "[OK] uds_send deployed to /tmp ($(ls -la /tmp/uds_send 2>&1))"
else
    echo "[ERROR] uds_send binary not found on USB"
    echo "service-reset FAILED" >> "${USBROOT}/pcm_ran.txt"
    exit 1
fi

# Quick test — does the binary run?
echo ""
echo "=== Binary Test ==="
/tmp/uds_send 2>&1
UDS_RC=$?
echo "Exit code: $UDS_RC"

if [ $UDS_RC -eq 127 ]; then
    echo "[ERROR] Binary failed to load (missing libs or wrong arch)"
    echo "service-reset FAILED" >> "${USBROOT}/pcm_ran.txt"
    exit 1
fi

echo ""
echo "=== NDR Device Check ==="
ls -la /dev/ndr/ 2>&1

echo ""
echo "=== Step 1: Extended Diagnostic Session (cluster 0x17) ==="
echo ">> uds_send 0x17 0x10 0x03"
/tmp/uds_send 0x17 0x10 0x03 2>&1
echo "RC=$?"
sleep 1

echo ""
echo "=== Step 2: Reset Oil Service (DID 0x0156) ==="
echo ">> uds_send 0x17 0x2E 0x01 0x56 0x00"
/tmp/uds_send 0x17 0x2E 0x01 0x56 0x00 2>&1
echo "RC=$?"
sleep 1

echo ""
echo "=== Step 3: Reset Inspection Distance (DID 0x0D17) ==="
echo ">> uds_send 0x17 0x2E 0x0D 0x17 0x00 0x00 0x00 0x00"
/tmp/uds_send 0x17 0x2E 0x0D 0x17 0x00 0x00 0x00 0x00 2>&1
echo "RC=$?"
sleep 1

echo ""
echo "=== Step 4: Reset Inspection Time (DID 0x0D18) ==="
echo ">> uds_send 0x17 0x2E 0x0D 0x18 0x00 0x00 0x00 0x00"
/tmp/uds_send 0x17 0x2E 0x0D 0x18 0x00 0x00 0x00 0x00 2>&1
echo "RC=$?"

echo ""
echo "=== Trying alternate cluster address 0x714 ==="
echo ">> uds_send 0x714 0x10 0x03"
/tmp/uds_send 0x714 0x10 0x03 2>&1
echo "RC=$?"

echo ""
echo "============================================"
echo "  Service Reset Log Complete"
echo "============================================"
} > "$LOG" 2>&1

echo "service-reset done" >> "${USBROOT}/pcm_ran.txt"
echo "Log: $LOG"
