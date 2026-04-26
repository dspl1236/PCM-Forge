#!/bin/ksh
# PCM-Forge Display Probe — Run from PuTTY (telnet session)
# Investigates why showScreen fails with lmgrHMIConnect

echo "============================================"
echo "  PCM-Forge Display Probe"
echo "============================================"

echo ""
echo "=== Layer Manager ==="
ls -la /dev/layermanager 2>&1
ls -la /dev/layermanager* 2>&1

echo ""
echo "=== io-display ==="
ls -la /dev/io-display/ 2>&1

echo ""
echo "=== Graphics devices ==="
ls -la /dev/gf* /dev/pv* /dev/wms* 2>&1

echo ""
echo "=== Display processes ==="
pidin ar | grep -i "display\|layer\|video\|carmine\|PCM3Root\|PCM3Boot\|showScreen"

echo ""
echo "=== Layer Manager Config ==="
cat /etc/layermanagerV2*.cfg 2>&1
ls -la /etc/layermanager* 2>&1

echo ""
echo "=== Image Codec Config ==="
cat /etc/system/config/img.conf 2>&1

echo ""
echo "=== Display Config ==="
cat /etc/system/config/display.conf 2>&1

echo ""
echo "=== Carmine Config ==="
cat /etc/system/config/carmine*.conf 2>&1 | head -50

echo ""
echo "=== Video Control ==="
cat /etc/videoctrl*.cfg 2>&1 | head -30

echo ""
echo "=== IPC Channel 8 (display IPC) ==="
ls -la /dev/ipc/ch8 /dev/ipc/ioc/ch8 2>&1

echo ""
echo "=== libgf available? ==="
ls -la /lib/libgf* /usr/lib/libgf* /proc/boot/libgf* 2>&1

echo ""
echo "=== Image libs ==="
ls -la /lib/libimg* /usr/lib/libimg* /proc/boot/libimg* /lib/dll/img* 2>&1

echo ""
echo "=== Try showScreen directly ==="
SS=""
for s in /usr/bin/showScreen /HBbin/showScreen /mnt/data/tools/showScreen; do
    [ -f "$s" ] && SS="$s" && break
done
if [ -n "$SS" ]; then
    echo "Found: $SS"
    echo "Trying: $SS -v"
    $SS -v 2>&1
else
    echo "showScreen not found on PCM filesystem"
    echo "Need to deploy from USB first"
fi

echo ""
echo "=== /dev/shmem display-related ==="
ls /dev/shmem/ 2>&1 | grep -i "disp\|layer\|screen\|gf\|hmi\|video"

echo ""
echo "============================================"
echo "  Display Probe Complete"
echo "============================================"
