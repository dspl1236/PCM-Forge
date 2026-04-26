#!/bin/ksh
# PCM-Forge NDR Probe — Discover correct devctl format
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"
LOG="${USBROOT}/ndr_probe.log"

{
echo "============================================"
echo "  PCM-Forge NDR devctl Probe"
echo "============================================"
echo ""

# Deploy probe binary
if [ -f "${USBROOT}/bin/ndr_probe" ]; then
    cp "${USBROOT}/bin/ndr_probe" /tmp/ndr_probe
    chmod +x /tmp/ndr_probe
    echo "[OK] ndr_probe deployed to /tmp"
    ls -la /tmp/ndr_probe
else
    echo "[ERROR] ndr_probe binary not found on USB"
    exit 1
fi

echo ""
echo "=== NDR Device ==="
ls -la /dev/ndr/ 2>&1

echo ""
echo "=== IOC Channels ==="
ls -la /dev/ipc/ioc/ 2>&1

echo ""
echo "=== Running NDR Process ==="
pidin ar | grep ndr 2>&1

echo ""
echo "=== Display System ==="
ls -la /dev/layermanager 2>&1
pidin ar | grep -i "layer\|display\|video" 2>&1

echo ""
echo "=== Engineering Screens ==="
ls -la /HBpersistence/engdefs/ 2>&1
ls -la /mnt/ifs1/engdefs/ /mnt/flash/efs1/engdefs/ 2>&1

echo ""
echo "=== Running Probe ==="
echo "Trying ~450 devctl class/cmd combinations..."
echo ""
/tmp/ndr_probe 2>&1

echo ""
echo "=== Grabbing Binaries for Analysis ==="
# Copy NavigationNdrInfo for disassembly
if [ -f /mnt/data/tools/NavigationNdrInfo ]; then
    cp /mnt/data/tools/NavigationNdrInfo "${USBROOT}/NavigationNdrInfo"
    echo "[OK] Copied NavigationNdrInfo ($(ls -la /mnt/data/tools/NavigationNdrInfo | awk '{print $5}') bytes)"
else
    echo "[WARN] NavigationNdrInfo not found"
fi

# Copy ndr binary from boot image
if [ -f /proc/boot/ndr ]; then
    cp /proc/boot/ndr "${USBROOT}/ndr_boot"
    echo "[OK] Copied /proc/boot/ndr ($(ls -la /proc/boot/ndr | awk '{print $5}') bytes)"
else
    echo "[WARN] /proc/boot/ndr not found"
fi

# Copy taco for analysis
if [ -f /mnt/data/tools/taco ]; then
    cp /mnt/data/tools/taco "${USBROOT}/taco"
    echo "[OK] Copied taco ($(ls -la /mnt/data/tools/taco | awk '{print $5}') bytes)"
fi

echo ""
echo "=== Factory ESD Files ==="
for dir in /HBpersistence/engdefs /mnt/ifs1/engdefs /mnt/flash/efs1/engdefs; do
    if [ -d "$dir" ]; then
        echo "--- $dir ---"
        ls -la "$dir" 2>&1
        mkdir -p "${USBROOT}/engdefs_dump" 2>/dev/null
        cp "$dir"/*.esd "${USBROOT}/engdefs_dump/" 2>/dev/null
    fi
done

echo ""
echo "=== showScreen Test ==="
if [ -f "${USBROOT}/bin/showScreen" ]; then
    cp "${USBROOT}/bin/showScreen" /tmp/showScreen
    chmod +x /tmp/showScreen
    waitfor /dev/layermanager 5 2>/dev/null
    /tmp/showScreen -v 2>&1
    echo "Trying display..."
    /tmp/showScreen -s "${USBROOT}/lib/running.png" 2>&1
fi

echo ""
echo "============================================"
echo "  NDR Probe Complete"
echo "============================================"
} > "$LOG" 2>&1

echo "ndr-probe done" >> "${USBROOT}/pcm_ran.txt"
