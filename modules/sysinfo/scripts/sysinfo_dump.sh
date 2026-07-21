#!/bin/sh
# sysinfo_dump.sh — Complete PCM 3.1 system diagnostic
# Read-only, no changes to car. Dumps everything to USB.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/sysinfo.log"
DUMPDIR="$USB/sysinfo_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge System Info ===" > "$LOG"
echo "Date: $(date 2>/dev/null || echo unknown)" >> "$LOG"
echo "" >> "$LOG"

# === 1. FIRMWARE VERSION ===
echo "--- 1. Firmware ---" >> "$LOG"
cat /mnt/ifs1/HBproject/version.txt >> "$LOG" 2>&1
cat /HBproject/version.txt >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 2. PROCESS LIST ===
echo "--- 2. Processes ---" >> "$LOG"
pidin ar >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 3. DISK SPACE ===
echo "--- 3. Disk Space ---" >> "$LOG"
df >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 4. DISPLAY STACK ===
echo "--- 4. Display Stack ---" >> "$LOG"
echo "  /dev/layermanager:" >> "$LOG"
ls -la /dev/layermanager >> "$LOG" 2>&1
echo "  Display config:" >> "$LOG"
cat /etc/system/config/display.conf >> "$LOG" 2>&1
echo "  Image codecs:" >> "$LOG"
cat /etc/system/config/img.conf >> "$LOG" 2>&1
for cfg in /etc/system/config/carmine*.conf; do
    [ -f "$cfg" ] && {
        echo "  === $(basename $cfg) ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    }
done
echo "" >> "$LOG"

# === 5. BOOT SCREENS ===
echo "--- 5. Boot Screens ---" >> "$LOG"
echo "  HDD (/mnt/share/bootscreens/):" >> "$LOG"
ls -la /mnt/share/bootscreens/ >> "$LOG" 2>&1
echo "  Active (/HBpersistence/):" >> "$LOG"
ls -la /HBpersistence/CustomBootscreen* >> "$LOG" 2>&1
echo "  IFS fallback:" >> "$LOG"
ls -la /proc/boot/PCM31_bootScreenPorscheLogo.jpg >> "$LOG" 2>&1
for bs in /HBpersistence/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && cp "$bs" "$DUMPDIR/" 2>/dev/null
done
echo "" >> "$LOG"

# === 6. PERSISTENCE ===
echo "--- 6. Persistence ---" >> "$LOG"

# persdump2 usage
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2; do
    [ -x "$p" ] && PERSDUMP="$p" && break
done
if [ -n "$PERSDUMP" ]; then
    echo "  persdump2: $PERSDUMP" >> "$LOG"
    "$PERSDUMP" >> "$LOG" 2>&1
    # Verbose dump first CVALUE file
    for cv in /HBpersistence/CVALUE*.CVA; do
        if [ -f "$cv" ]; then
            echo "  Test: $PERSDUMP $(basename $cv) v" >> "$LOG"
            "$PERSDUMP" "$cv" v >> "$LOG" 2>&1
            break
        fi
    done
fi
echo "" >> "$LOG"

# Copy all CVALUE files
echo "  CVALUE files:" >> "$LOG"
COUNT=0
for f in /HBpersistence/CVALUE*.CVA; do
    [ -f "$f" ] && { cp "$f" "$DUMPDIR/" 2>/dev/null; COUNT=$((COUNT + 1)); }
done
echo "  Copied $COUNT CVALUE files" >> "$LOG"
echo "" >> "$LOG"

# Full HBpersistence listing
echo "--- 7. /HBpersistence/ ---" >> "$LOG"
ls -laR /HBpersistence/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# Copy key persistence files
echo "--- 8. Persistence Files ---" >> "$LOG"
mkdir -p "$DUMPDIR/Early" "$DUMPDIR/Normal" 2>/dev/null
for f in /HBpersistence/EarlyPersistencyFiles/*; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/Early/" 2>/dev/null
done
for f in /HBpersistence/NormalPersistencyFiles/*; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/Normal/" 2>/dev/null
done
echo "  Copied EarlyPersistencyFiles + NormalPersistencyFiles" >> "$LOG"
echo "" >> "$LOG"

# === 9. DEBUG TOOLS ===
echo "--- 9. Debug Tools ---" >> "$LOG"
for t in taco persdump2 showScreen mmecli vi ping qdbc qconn sqlite_console find; do
    LOC=$(find /mnt -name "$t" -type f 2>/dev/null | head -1)
    [ -n "$LOC" ] && {
        SIZE=$(ls -la "$LOC" | awk '{print $5}')
        echo "  $t: $LOC ($SIZE bytes)" >> "$LOG"
    }
done
# Also check /proc/boot and /HBbin
for t in taco qdbc qconn; do
    for d in /usr/sbin /usr/bin /HBbin /proc/boot; do
        [ -x "$d/$t" ] && echo "  $t: $d/$t" >> "$LOG"
    done
done
echo "" >> "$LOG"

# === 10. NETWORK ===
echo "--- 10. Network ---" >> "$LOG"
ifconfig -a >> "$LOG" 2>&1
echo "" >> "$LOG"
cat /etc/inetd.conf >> "$LOG" 2>&1
echo "" >> "$LOG"
cat /etc/hosts >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 11. VIN & ACTIVATION ===
echo "--- 11. VIN & Activation ---" >> "$LOG"
echo "  VIN:" >> "$LOG"
cat /HBpersistence/vin >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  PagSWAct.002:" >> "$LOG"
ls -la /HBpersistence/PagSWAct.002 >> "$LOG" 2>&1
echo "  DBGModeActive:" >> "$LOG"
ls -la /HBpersistence/DBGModeActive >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 12. HYBRID DATA ===
echo "--- 12. hybrid.bin ---" >> "$LOG"
[ -f "/HBpersistence/hybrid.bin" ] && {
    ls -la /HBpersistence/hybrid.bin >> "$LOG" 2>&1
    cp /HBpersistence/hybrid.bin "$DUMPDIR/" 2>/dev/null
}
echo "" >> "$LOG"

# === 13. BT/AUX FIX STATE + AUDIO SOURCE (support diagnosis) ===
echo "--- 13. BT/AUX Fix State + Audio Source ---" >> "$LOG"
echo "  [boot hook] /HBpersistence/debugTools.sh" >> "$LOG"
echo "  A 'PCM-Forge bt_fix' block below = the patch RE-APPLIES every boot" >> "$LOG"
echo "  (Revert did not fully take -- this alone explains a stuck AUX/no-BT):" >> "$LOG"
echo "  .................................................................." >> "$LOG"
cat /HBpersistence/debugTools.sh >> "$LOG" 2>&1
echo "  .................................................................." >> "$LOG"
echo "  [fix files] should ALL be absent after a clean Revert:" >> "$LOG"
ls -la /HBpersistence/bt_boot.sh /HBpersistence/bt_fix /HBpersistence/bt_boot.log >> "$LOG" 2>&1
[ -f /HBpersistence/debugTools.sh ] && cp /HBpersistence/debugTools.sh "$DUMPDIR/" 2>/dev/null
[ -f /HBpersistence/bt_boot.log ]  && cp /HBpersistence/bt_boot.log  "$DUMPDIR/" 2>/dev/null
echo "" >> "$LOG"
echo "  [audio / source / bluetooth persistence]:" >> "$LOG"
ls -la /HBpersistence/*ource* /HBpersistence/*udio* /HBpersistence/*luetooth* /HBpersistence/*Mode* /HBpersistence/*edia* /HBpersistence/*uner* >> "$LOG" 2>&1
echo "  (Normal/EarlyPersistencyFiles already copied to sysinfo_dump/ for offline decode of last-source + pairing state)" >> "$LOG"
echo "" >> "$LOG"

echo "=== System Info complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
