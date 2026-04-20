#!/bin/sh
# service_status.sh — Capture IOC/NDR/CAN diagnostic state
# Logs to USB for offline analysis
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

LOG="/fs/usb0/service_status_$(date +%H%M%S 2>/dev/null).log"

echo "=== PCM-Forge Service Status ===" > "$LOG"

echo "--- IOC Channels ---" >> "$LOG"
ls -la /dev/ipc/ioc/ >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "--- NDR Interface ---" >> "$LOG"
ls -la /dev/ndr/ >> "$LOG" 2>&1
[ -w "/dev/ndr/cmd" ] && echo "ndr/cmd: WRITABLE" >> "$LOG" || echo "ndr/cmd: read-only" >> "$LOG"

echo "" >> "$LOG"
echo "--- NDR Message Queue Sample (256 bytes) ---" >> "$LOG"
dd if=/dev/ndr/msq bs=256 count=1 2>/dev/null | od -A x -t x1z >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "--- Persistence ---" >> "$LOG"
ls -la /HBpersistence/ >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "--- Processes ---" >> "$LOG"
pidin ar 2>/dev/null | head -40 >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "--- Available Tools ---" >> "$LOG"
for t in taco persdump2 showScreen mmecli; do
    f=$(find /mnt -name "$t" -type f 2>/dev/null | head -1)
    [ -n "$f" ] && echo "$t: $f" >> "$LOG"
done

echo "" >> "$LOG"
echo "Saved: $LOG" >> "$LOG"
