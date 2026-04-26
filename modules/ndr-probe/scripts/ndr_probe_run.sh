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

echo ""
echo "=== /etc Overlay Test ==="
echo "Current /etc mount:"
mount 2>&1 | grep "/etc"

echo ""
echo "Saving /etc contents..."
mkdir -p /dev/shmem/etc_save 2>/dev/null
cp /etc/* /dev/shmem/etc_save/ 2>/dev/null
ls /dev/shmem/etc_save/ 2>&1

echo ""
echo "Existing devf-ram instances:"
pidin ar | grep devf-ram 2>&1

echo ""
echo "Trying new devf-ram instance..."
devf-ram -s0,512k -i20,1 2>&1
sleep 1
ls /dev/fs20* 2>&1

echo ""
echo "Trying mount overlay on /etc..."
mount /dev/fs20 /etc 2>&1
MOUNT_RC=$?
echo "mount rc=$MOUNT_RC"

if [ $MOUNT_RC -eq 0 ]; then
    echo "[OK] /etc overlay mounted!"
    cp /dev/shmem/etc_save/* /etc/ 2>/dev/null
    echo "Copied saved contents back"
    
    # Now add our fixes
    echo "nameserver 8.8.8.8" > /etc/resolv.conf
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf
    echo "[OK] DNS servers added to /etc/resolv.conf"
    
    echo "2323 stream tcp nowait root /bin/ksh ksh -i" >> /etc/inetd.conf
    echo "[OK] Port 2323 added to /etc/inetd.conf"
    
    # Restart inetd to pick up changes
    slay -f inetd 2>/dev/null
    sleep 1
    /usr/sbin/inetd 2>/dev/null &
    echo "[OK] inetd restarted with new config"
    
    cat /etc/resolv.conf
    cat /etc/inetd.conf | grep 2323
    echo ""
    echo "*** /etc OVERLAY WORKS! ***"
else
    echo "[WARN] Mount failed — trying alternative approaches"
    
    # Try io-fs-media tmpfs
    echo "Trying tmpfs..."
    mount -Ttmpfs tmpfs /etc 2>&1
    
    # Try prefix utility  
    echo "Trying prefix redirect..."
    # On QNX, /dev/shmem is always writable — make it look like /etc
    ln -sf /dev/shmem/etc_save /dev/shmem/etc_link 2>/dev/null
fi

echo ""
echo "=== Final mount table ==="
mount 2>&1
