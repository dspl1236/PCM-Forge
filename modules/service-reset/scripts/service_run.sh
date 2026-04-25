#!/bin/ksh
# PCM-Forge Service Reset — Wrapper script
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"

echo "======== Service Reset ========"

# Deploy uds_send binary to /tmp (writable)
if [ -f "${USBROOT}/bin/uds_send" ]; then
    cp "${USBROOT}/bin/uds_send" /tmp/uds_send
    chmod +x /tmp/uds_send
    echo "[OK] uds_send deployed to /tmp"
else
    echo "[ERROR] uds_send binary not found on USB"
    echo "service-reset FAILED" >> "${USBROOT}/pcm_ran.txt"
    return 1
fi

# Quick test — does the binary run?
/tmp/uds_send 2>&1 | head -1
if [ $? -eq 0 ] || [ $? -eq 1 ]; then
    echo "[OK] uds_send binary works"
else
    echo "[ERROR] uds_send binary failed to execute"
    echo "service-reset FAILED" >> "${USBROOT}/pcm_ran.txt"
    return 1
fi

# Run the reset (defaults to "all" — oil + inspection)
BINDIR=/tmp
export BINDIR

echo ""
echo "Running oil + inspection reset..."
echo ""

# Step 1: Extended diagnostic session to cluster (0x17 = cluster address)
echo ">> DiagnosticSessionControl Extended"
/tmp/uds_send 0x17 0x10 0x03
sleep 1

# Step 2: Reset ESI oil service (DID 0x0156)
echo ">> WriteDataByIdentifier: Reset oil service (0x0156)"
/tmp/uds_send 0x17 0x2E 0x01 0x56 0x00
sleep 1

# Step 3: Reset distance since inspection (DID 0x0D17)
echo ">> WriteDataByIdentifier: Reset inspection distance (0x0D17)"
/tmp/uds_send 0x17 0x2E 0x0D 0x17 0x00 0x00 0x00 0x00
sleep 1

# Step 4: Reset time since inspection (DID 0x0D18)
echo ">> WriteDataByIdentifier: Reset inspection time (0x0D18)"
/tmp/uds_send 0x17 0x2E 0x0D 0x18 0x00 0x00 0x00 0x00

echo ""
echo "Service reset commands sent. Check cluster display."
echo "service-reset done" >> "${USBROOT}/pcm_ran.txt"
