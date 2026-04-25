#!/bin/ksh
# PCM-Forge System Info — Comprehensive PCM 3.1 diagnostic
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"
DTSTAMP=$(date +%Y%m%d_%H%M%S 2>/dev/null || echo nodate)
LOG="${USBROOT}/pcm_sysinfo_${DTSTAMP}.log"
DUMPDIR="${USBROOT}/pcm_dump_${DTSTAMP}"
mkdir -p "$DUMPDIR" 2>/dev/null

{
echo "============================================"
echo "  PCM-Forge System Info"
echo "============================================"

echo ""
echo "=== PCM Version ==="
cat /mnt/ifs1/HBproject/version.txt 2>&1
cat /HBproject/version.txt 2>&1

echo ""
echo "=== VIN ==="
cat /HBpersistence/vin 2>&1

echo ""
echo "=== Mount Points ==="
mount 2>&1

echo ""
echo "=== Processes ==="
pidin 2>&1

echo ""
echo "=== Network ==="
ifconfig 2>&1

echo ""
echo "=== /HBpersistence ==="
ls -la /HBpersistence/ 2>&1

echo ""
echo "=== Flash/HDD ==="
ls -la /dev/fs0* /dev/hd0* 2>&1

echo ""
echo "=== IFS/EFS Paths ==="
ls -d /mnt/ifs1/ /mnt/flash/ /mnt/efs-system/ /mnt/data/ /mnt/share/ /mnt/nav/ 2>&1

echo ""
echo "=== Engineering ESD ==="
ls /mnt/flash/efs1/engdefs/ /HBpersistence/engdefs/ /mnt/ifs1/engdefs/ 2>&1

echo ""
echo "=== inetd.conf ==="
cat /etc/inetd.conf 2>&1

echo ""
echo "=== /dev ==="
ls /dev/ 2>&1

echo ""
echo "=== IPC/DSP ==="
ls -laR /dev/ipc/ /dev/dspipc/ 2>&1

echo ""
echo "=== WiFi / Network Credentials ==="
cat /HBpersistence/wifi_networks.conf 2>&1
cat /HBpersistence/wpa_supplicant.conf 2>&1
ls -la /HBpersistence/DLinkReplacesPPP /HBpersistence/usedhcp 2>&1

echo ""
echo "=== Persistence Dump ==="
ls -laR /HBpersistence/ 2>&1

echo ""
echo "=== CVALUE Files ==="
for cva in /HBpersistence/CVALUE*.CVA; do
    [ -f "$cva" ] && cp "$cva" "$DUMPDIR/" 2>/dev/null && echo "  Copied: ${cva##*/}"
done

echo ""
echo "=== FSC Files ==="
mkdir -p "$DUMPDIR/FSC" 2>/dev/null
cp -r /HBpersistence/FSC/* "$DUMPDIR/FSC/" 2>/dev/null
ls -la /HBpersistence/FSC/ 2>&1

echo ""
echo "=== CAN / IOC Probe ==="
ls -laR /dev/ipc/ 2>&1
ls -la /dev/can* /dev/ser* /dev/spi* /dev/i2c* /dev/most* 2>&1
ls -la /dev/sysregs/ 2>&1
ls -la /dev/ndr/ 2>&1
ls -la /srv/ 2>&1
ls -laR /hbsystem/ 2>&1
ls /dev/shmem/ 2>&1

echo ""
echo "=== Development Tools ==="
ls -la /mnt/data/tools/ 2>&1

echo ""
echo "============================================"
echo "  System Info Complete"
echo "============================================"
} > "$LOG" 2>&1

# Backup key files
cp /HBpersistence/vin "$DUMPDIR/vin" 2>/dev/null
cp /HBpersistence/screensaver.conf "$DUMPDIR/" 2>/dev/null
cp /HBpersistence/hybrid.bin "$DUMPDIR/" 2>/dev/null
[ -f /HBpersistence/PagSWAct.002 ] && cp /HBpersistence/PagSWAct.002 "$DUMPDIR/" 2>/dev/null
for bs in /HBpersistence/CustomBootscreen_*.bin; do [ -f "$bs" ] && cp "$bs" "$DUMPDIR/" 2>/dev/null; done
mkdir -p "$DUMPDIR/engdefs" 2>/dev/null
cp /HBpersistence/engdefs/* "$DUMPDIR/engdefs/" 2>/dev/null

echo "sysinfo done" >> "${USBROOT}/pcm_ran.txt"
