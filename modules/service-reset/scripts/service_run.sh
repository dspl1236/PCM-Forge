#!/bin/ksh
# PCM-Forge Service Reset v2 — Reads commands from /tmp/uds_cmd
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"
LOG="${USBROOT}/service_reset.log"

{
echo "============================================"
echo "  PCM-Forge Service Reset v2"
echo "============================================"
echo ""

# Deploy uds_send binary
if [ -f "${USBROOT}/bin/uds_send" ]; then
    cp "${USBROOT}/bin/uds_send" /tmp/uds_send
    chmod +x /tmp/uds_send
    echo "[OK] uds_send deployed to /tmp"
    ls -la /tmp/uds_send
else
    echo "[ERROR] uds_send binary not found"
    exit 1
fi

echo ""
echo "=== NDR Device ==="
ls -la /dev/ndr/ 2>&1

# Write UDS commands to /tmp/uds_cmd
# Format: <ecu_hex> <service_id> [data bytes...]
# 0x17 = instrument cluster
echo ""
echo "=== Writing UDS commands ==="

# Step 1: Extended diagnostic session
echo "17 10 03" > /tmp/uds_cmd
echo "[CMD] 17 10 03 (Extended Diagnostic Session)"
/tmp/uds_send 2>&1
sleep 1

# Step 2: Reset oil service (DID 0x0156)
echo "17 2E 01 56 00" > /tmp/uds_cmd
echo "[CMD] 17 2E 01 56 00 (Reset Oil Service DID 0x0156)"
/tmp/uds_send 2>&1
sleep 1

# Step 3: Reset inspection distance (DID 0x0D17)
echo "17 2E 0D 17 00 00 00 00" > /tmp/uds_cmd
echo "[CMD] 17 2E 0D 17 00 00 00 00 (Reset Distance DID 0x0D17)"
/tmp/uds_send 2>&1
sleep 1

# Step 4: Reset inspection time (DID 0x0D18)
echo "17 2E 0D 18 00 00 00 00" > /tmp/uds_cmd
echo "[CMD] 17 2E 0D 18 00 00 00 00 (Reset Time DID 0x0D18)"
/tmp/uds_send 2>&1

echo ""
echo "============================================"
echo "  Service Reset Complete"
echo "============================================"
} > "$LOG" 2>&1

echo "service-reset done" >> "${USBROOT}/pcm_ran.txt"
