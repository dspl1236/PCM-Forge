#!/bin/sh
# ioc_probe.sh — IOC Channel Probe for PCM 3.1
# Probes all /dev/ipc/ioc channels, captures system state,
# and collects diagnostic data for PCM-Forge development.
#
# SAFE: Read-only operations. Does not write to any channel.
#
# v2: Non-blocking sections first, blocking reads last.
#     Previous version hung on dd reads to IOC channels.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/ioc_probe.log"
DUMPDIR="$USB/ioc_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge IOC Channel Probe v2 ===" > "$LOG"
echo "Date: $(date 2>/dev/null || echo 'no date cmd')" >> "$LOG"
echo "" >> "$LOG"

# === 1. IOC CHANNEL ENUMERATION (instant) ===
echo "--- 1. IOC Channel Enumeration ---" >> "$LOG"
ls -la /dev/ipc/ioc/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 2. PROCESS LIST (instant) ===
echo "--- 2. Processes ---" >> "$LOG"
pidin ar >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 3. NDR DEVICES (instant) ===
echo "--- 3. NDR Devices ---" >> "$LOG"
ls -la /dev/ndr/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 4. DISPLAY STACK (instant) ===
echo "--- 4. Display Stack ---" >> "$LOG"
echo "  /dev/layermanager:" >> "$LOG"
ls -la /dev/layermanager >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  GF devices:" >> "$LOG"
ls -la /dev/gf* >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  Display config:" >> "$LOG"
cat /etc/system/config/display.conf >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  Image codec config:" >> "$LOG"
cat /etc/system/config/img.conf >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  Layer manager config:" >> "$LOG"
for cfg in /etc/layermanager*.cfg /etc/system/config/layermanager*.cfg; do
    if [ -f "$cfg" ]; then
        echo "  === $cfg ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    fi
done
echo "" >> "$LOG"

echo "  Carmine GPU config:" >> "$LOG"
for cfg in /etc/system/config/carmine*.conf; do
    if [ -f "$cfg" ]; then
        echo "  === $cfg ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    fi
done
echo "" >> "$LOG"

# === 5. BOOT SCREEN & STORAGE (instant) ===
echo "--- 5. Boot Screen & Storage ---" >> "$LOG"

echo "  /mnt/share/bootscreens/:" >> "$LOG"
ls -la /mnt/share/bootscreens/ >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  /HBpersistence/CustomBootscreen*:" >> "$LOG"
ls -la /HBpersistence/CustomBootscreen* >> "$LOG" 2>&1
echo "" >> "$LOG"

for bs in /HBpersistence/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && cp "$bs" "$DUMPDIR/" 2>/dev/null
done

echo "  IFS fallback:" >> "$LOG"
ls -la /proc/boot/PCM31_bootScreenPorscheLogo.jpg >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  Disk space:" >> "$LOG"
df >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "  Firmware version:" >> "$LOG"
cat /mnt/ifs1/HBproject/version.txt >> "$LOG" 2>&1
cat /HBproject/version.txt >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 6. FACTORY ESD FILES (instant) ===
echo "--- 6. Factory ESD Files ---" >> "$LOG"
for d in /mnt/ifs1/engdefs /mnt/flash/efs1/engdefs /mnt/efs-system/engdefs /HBpersistence/engdefs; do
    if [ -d "$d" ]; then
        echo "  $d/:" >> "$LOG"
        ls -la "$d"/ >> "$LOG" 2>&1
        for f in "$d"/*.esd; do
            if [ -f "$f" ]; then
                cp "$f" "$DUMPDIR/" 2>/dev/null
                echo "" >> "$LOG"
                echo "  === $(basename $f) ===" >> "$LOG"
                cat "$f" >> "$LOG" 2>&1
            fi
        done
    fi
done
echo "" >> "$LOG"

# === 7. PERSISTENCE DUMP (quick) ===
echo "--- 7. Persistence Scan ---" >> "$LOG"
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2; do
    if [ -x "$p" ]; then
        PERSDUMP="$p"
        break
    fi
done

if [ -n "$PERSDUMP" ]; then
    echo "Using: $PERSDUMP" >> "$LOG"

    echo "" >> "$LOG"
    echo "  Service addresses:" >> "$LOG"
    for addr in 0x0010001F 0x0014004E 0x00100033 0x0014007D; do
        echo "  per3 $addr: $($PERSDUMP 3 $addr 2>&1)" >> "$LOG"
    done

    echo "" >> "$LOG"
    echo "  Cluster range 0x0015xxxx:" >> "$LOG"
    i=0
    while [ $i -lt 32 ]; do
        addr=$(printf "0x001500%02X" $i)
        result=$("$PERSDUMP" 3 "$addr" 2>&1)
        if [ -n "$result" ]; then
            echo "    $addr: $result" >> "$LOG"
        fi
        i=$((i + 1))
    done

    echo "" >> "$LOG"
    echo "  Cluster range 0x0016xxxx:" >> "$LOG"
    i=0
    while [ $i -lt 32 ]; do
        addr=$(printf "0x001600%02X" $i)
        result=$("$PERSDUMP" 3 "$addr" 2>&1)
        if [ -n "$result" ]; then
            echo "    $addr: $result" >> "$LOG"
        fi
        i=$((i + 1))
    done

    echo "" >> "$LOG"
    echo "  Vehicle range 0x0010xxxx:" >> "$LOG"
    i=0
    while [ $i -lt 64 ]; do
        addr=$(printf "0x001000%02X" $i)
        result=$("$PERSDUMP" 3 "$addr" 2>&1)
        if [ -n "$result" ]; then
            echo "    $addr: $result" >> "$LOG"
        fi
        i=$((i + 1))
    done

    echo "" >> "$LOG"
    echo "  Protocol range 0x0014xxxx:" >> "$LOG"
    i=0
    while [ $i -lt 128 ]; do
        addr=$(printf "0x001400%02X" $i)
        result=$("$PERSDUMP" 3 "$addr" 2>&1)
        if [ -n "$result" ]; then
            echo "    $addr: $result" >> "$LOG"
        fi
        i=$((i + 1))
    done
else
    echo "persdump2 not found" >> "$LOG"
fi
echo "" >> "$LOG"

# === 8. CVALUE FILES (instant) ===
echo "--- 8. CVALUE Files ---" >> "$LOG"
ls -la /HBpersistence/CVALUE*.CVA >> "$LOG" 2>&1
for f in /HBpersistence/CVALUE*.CVA; do
    if [ -f "$f" ]; then
        cp "$f" "$DUMPDIR/" 2>/dev/null
    fi
done
COUNT=0
for f in /HBpersistence/CVALUE*.CVA; do
    [ -f "$f" ] && COUNT=$((COUNT + 1))
done
echo "  Copied $COUNT CVALUE files" >> "$LOG"
echo "" >> "$LOG"

# === 9. DEBUG TOOLS INVENTORY (instant) ===
echo "--- 9. Available Debug Tools ---" >> "$LOG"
for t in taco persdump2 showScreen mmecli vi ping sqlite_console find qdbc qconn; do
    LOC=$(find /mnt -name "$t" -type f 2>/dev/null | head -1)
    if [ -n "$LOC" ]; then
        SIZE=$(ls -la "$LOC" 2>/dev/null | awk '{print $5}')
        echo "  $t: $LOC ($SIZE bytes)" >> "$LOG"
    fi
done
echo "" >> "$LOG"

# === 10. DATAPST.DB (instant copy) ===
echo "--- 10. DataPST.db ---" >> "$LOG"
if [ -f "/HBpersistence/DataPST.db" ]; then
    SIZE=$(ls -la /HBpersistence/DataPST.db | awk '{print $5}')
    echo "  Found: $SIZE bytes" >> "$LOG"
    cp /HBpersistence/DataPST.db "$DUMPDIR/" 2>/dev/null
    echo "  Copied to USB" >> "$LOG"
else
    echo "  Not found" >> "$LOG"
fi
echo "" >> "$LOG"

# === 11. KEY FILES (instant copy) ===
echo "--- 11. Key Files ---" >> "$LOG"
for kd in /HBpersistence/Keys/DataKey /HBpersistence/Keys/FSCKey /HBpersistence/Keys/MetainfoKey; do
    if [ -d "$kd" ]; then
        echo "  $kd:" >> "$LOG"
        ls -la "$kd"/ >> "$LOG" 2>&1
        mkdir -p "$DUMPDIR/Keys/$(basename $kd)" 2>/dev/null
        cp "$kd"/* "$DUMPDIR/Keys/$(basename $kd)/" 2>/dev/null
    fi
done
echo "" >> "$LOG"

# === 12. HBPERSISTENCE FULL LISTING (instant) ===
echo "--- 12. /HBpersistence/ full listing ---" >> "$LOG"
ls -laR /HBpersistence/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 13. SHOWSCREEN TEST (quick) ===
echo "--- 13. showScreen Test ---" >> "$LOG"
echo "  /dev/layermanager: $(ls /dev/layermanager 2>&1)" >> "$LOG"
echo "  Previous result: lmgrHMIConnect failed (exclusivity confirmed)" >> "$LOG"
echo "" >> "$LOG"

# === 14. IOC CHANNEL SUMMARY (no blocking reads) ===
echo "--- 14. IOC Channel Summary ---" >> "$LOG"
echo "  Channels found: ch2-ch10, debug, onoff, watchdog" >> "$LOG"
echo "  ch2-ch10: nrw-rw-rw- (world read-write, named special)" >> "$LOG"
echo "  debug/onoff/watchdog: nr--r--r-- (read-only)" >> "$LOG"
echo "  Raw reads block without CHBIpcProtocol client registration." >> "$LOG"
echo "  CAN communication requires devctl() handshake with 0xFADE framing." >> "$LOG"
echo "" >> "$LOG"

echo "=== Probe complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "Saved: $LOG" >> "$LOG"
