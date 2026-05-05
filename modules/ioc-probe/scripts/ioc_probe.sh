#!/bin/sh
# ioc_probe.sh — IOC Channel Probe for PCM 3.1
# Probes all /dev/ipc/ioc channels, captures CAN bus data,
# and maps the IPC protocol format.
#
# SAFE: Read-only operations. Does not write to any channel.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/ioc_probe.log"
DUMPDIR="$USB/ioc_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge IOC Channel Probe ===" > "$LOG"
echo "Date: $(date 2>/dev/null || echo 'no date cmd')" >> "$LOG"
echo "" >> "$LOG"

# === 1. ENUMERATE ALL IOC CHANNELS ===
echo "--- IOC Channel Enumeration ---" >> "$LOG"
ls -la /dev/ipc/ioc/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 2. PROBE EACH CHANNEL ===
echo "--- Channel Details ---" >> "$LOG"
for ch in /dev/ipc/ioc/*; do
    name=$(basename "$ch")
    echo "Channel: $name" >> "$LOG"
    
    # Check permissions
    if [ -r "$ch" ]; then
        echo "  Readable: YES" >> "$LOG"
    else
        echo "  Readable: NO" >> "$LOG"
    fi
    if [ -w "$ch" ]; then
        echo "  Writable: YES" >> "$LOG"
    else
        echo "  Writable: NO" >> "$LOG"
    fi
    
    # Try to read first 256 bytes (non-blocking with timeout)
    # Use dd with count=1 bs=256, timeout via background + kill
    if [ -r "$ch" ]; then
        (dd if="$ch" of="$DUMPDIR/${name}_sample.bin" bs=256 count=1 2>/dev/null) &
        DDPID=$!
        sleep 2
        kill $DDPID 2>/dev/null
        wait $DDPID 2>/dev/null
        
        if [ -f "$DUMPDIR/${name}_sample.bin" ]; then
            SIZE=$(ls -la "$DUMPDIR/${name}_sample.bin" 2>/dev/null | awk '{print $5}')
            echo "  Sample: $SIZE bytes captured" >> "$LOG"
            
            # Check for 0xFADE magic in first bytes
            if [ "$SIZE" -gt 1 ] 2>/dev/null; then
                # Use cksum as a fingerprint
                CKSUM=$(cksum "$DUMPDIR/${name}_sample.bin" 2>/dev/null)
                echo "  Checksum: $CKSUM" >> "$LOG"
            fi
        else
            echo "  Sample: read blocked (no data in 2s)" >> "$LOG"
        fi
    fi
    echo "" >> "$LOG"
done

# === 3. CAN CHANNEL DEEP PROBE ===
echo "--- CAN Channel Deep Probe (ch2, ch6, ch8) ---" >> "$LOG"
for ch in ch2 ch6 ch8; do
    DEV="/dev/ipc/ioc/$ch"
    if [ -r "$DEV" ]; then
        echo "Capturing $ch (4KB, 5s timeout)..." >> "$LOG"
        (dd if="$DEV" of="$DUMPDIR/${ch}_deep.bin" bs=4096 count=1 2>/dev/null) &
        DDPID=$!
        sleep 5
        kill $DDPID 2>/dev/null
        wait $DDPID 2>/dev/null
        
        if [ -f "$DUMPDIR/${ch}_deep.bin" ]; then
            SIZE=$(ls -la "$DUMPDIR/${ch}_deep.bin" 2>/dev/null | awk '{print $5}')
            echo "  $ch: $SIZE bytes captured" >> "$LOG"
        else
            echo "  $ch: no data (blocked)" >> "$LOG"
        fi
    else
        echo "  $ch: not readable" >> "$LOG"
    fi
done

# === 4. SENSOR CHANNEL (ch5 = NDR data) ===
echo "" >> "$LOG"
echo "--- Sensor Channel (ch5 = NDR/GPS) ---" >> "$LOG"
if [ -r "/dev/ipc/ioc/ch5" ]; then
    (dd if="/dev/ipc/ioc/ch5" of="$DUMPDIR/ch5_sensor.bin" bs=4096 count=1 2>/dev/null) &
    DDPID=$!
    sleep 3
    kill $DDPID 2>/dev/null
    wait $DDPID 2>/dev/null
    SIZE=$(ls -la "$DUMPDIR/ch5_sensor.bin" 2>/dev/null | awk '{print $5}')
    echo "  ch5: $SIZE bytes captured" >> "$LOG"
fi

# === 5. NDR COMPARISON ===
echo "" >> "$LOG"
echo "--- NDR vs IOC comparison ---" >> "$LOG"
echo "NDR devices:" >> "$LOG"
ls -la /dev/ndr/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 6. PROCESS LIST (CAN-related) ===
echo "--- CAN/IOC Processes ---" >> "$LOG"
pidin ar 2>/dev/null | grep -i "can\|ioc\|ipc\|ndr\|PCM3" >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 7. FACTORY ESD FILES ===
echo "--- Factory ESD Files ---" >> "$LOG"
for d in /mnt/ifs1/engdefs /mnt/flash/efs1/engdefs /mnt/efs-system/engdefs /HBpersistence/engdefs; do
    if [ -d "$d" ]; then
        echo "  $d/:" >> "$LOG"
        ls -la "$d"/ >> "$LOG" 2>&1
        # Copy factory ESDs to USB
        for f in "$d"/*.esd; do
            if [ -f "$f" ]; then
                cp "$f" "$DUMPDIR/" 2>/dev/null
                echo "    Copied: $(basename $f)" >> "$LOG"
            fi
        done
        # Dump contents
        for f in "$d"/*.esd; do
            if [ -f "$f" ]; then
                echo "" >> "$LOG"
                echo "  === $(basename $f) ===" >> "$LOG"
                cat "$f" >> "$LOG" 2>&1
            fi
        done
    fi
done

# === 8. PERSISTENCE DUMP (if persdump2 available) ===
echo "" >> "$LOG"
echo "--- Persistence Scan ---" >> "$LOG"
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2; do
    if [ -x "$p" ]; then
        PERSDUMP="$p"
        break
    fi
done

if [ -n "$PERSDUMP" ]; then
    echo "Using: $PERSDUMP" >> "$LOG"
    
    # Service-related addresses
    for addr in 0x0010001F 0x0014004E 0x00100033 0x0014007D; do
        echo "  per3 $addr: $($PERSDUMP 3 $addr 2>&1)" >> "$LOG"
    done
    
    # Scan cluster range
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
    
    # Vehicle data range
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
else
    echo "persdump2 not found" >> "$LOG"
fi

# === 9. CVALUE FILES ===
echo "" >> "$LOG"
echo "--- CVALUE Persistence Files ---" >> "$LOG"
ls -la /HBpersistence/CVALUE*.CVA >> "$LOG" 2>&1
# Copy all CVALUE files to USB for analysis
for f in /HBpersistence/CVALUE*.CVA; do
    if [ -f "$f" ]; then
        cp "$f" "$DUMPDIR/" 2>/dev/null
    fi
done
COUNT=$(ls /HBpersistence/CVALUE*.CVA 2>/dev/null | wc -l)
echo "  Copied $COUNT CVALUE files to USB" >> "$LOG"

# === 10. DEBUG TOOLS INVENTORY ===
echo "" >> "$LOG"
echo "--- Available Debug Tools ---" >> "$LOG"
for t in taco persdump2 showScreen mmecli vi ping sqlite_console find; do
    LOC=$(find /mnt -name "$t" -type f 2>/dev/null | head -1)
    if [ -n "$LOC" ]; then
        SIZE=$(ls -la "$LOC" 2>/dev/null | awk '{print $5}')
        echo "  $t: $LOC ($SIZE bytes)" >> "$LOG"
    fi
done

# === 11. DISPLAY STACK PROBE ===
echo "" >> "$LOG"
echo "--- Display Stack ---" >> "$LOG"

# Layer manager device
echo "  /dev/layermanager:" >> "$LOG"
ls -la /dev/layermanager >> "$LOG" 2>&1

# Display processes
echo "" >> "$LOG"
echo "  Display processes:" >> "$LOG"
pidin ar 2>/dev/null | grep -i "layer\|display\|carmine\|io-display\|PCM3Root\|PCM3Boot\|showScreen" >> "$LOG" 2>&1

# Graphics devices
echo "" >> "$LOG"
echo "  Graphics devices:" >> "$LOG"
ls -la /dev/gf* >> "$LOG" 2>&1
ls -la /dev/io-display* >> "$LOG" 2>&1
ls -la /dev/pv* >> "$LOG" 2>&1

# Display config
echo "" >> "$LOG"
echo "  Display config:" >> "$LOG"
cat /etc/system/config/display.conf >> "$LOG" 2>&1

# Image codec config (what formats are supported)
echo "" >> "$LOG"
echo "  Image codec config:" >> "$LOG"
cat /etc/system/config/img.conf >> "$LOG" 2>&1

# Layer manager config
echo "" >> "$LOG"
echo "  Layer manager config:" >> "$LOG"
for cfg in /etc/layermanager*.cfg /etc/system/config/layermanager*.cfg; do
    if [ -f "$cfg" ]; then
        echo "  === $cfg ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        echo "" >> "$LOG"
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    fi
done

# Carmine GPU config
echo "" >> "$LOG"
echo "  Carmine GPU config:" >> "$LOG"
for cfg in /etc/system/config/carmine*.conf; do
    if [ -f "$cfg" ]; then
        echo "  === $cfg ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    fi
done

# showScreen test — try with waitfor to test timing theory
echo "" >> "$LOG"
echo "  showScreen test:" >> "$LOG"
SS=""
for s in "$USB/bin/showScreen" /usr/bin/showScreen; do
    [ -f "$s" ] && SS="$s" && break
done
if [ -n "$SS" ]; then
    # Copy to tmpfs (some QNX versions won't exec from USB)
    TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
    cp "$SS" "$TMPD/showScreen" 2>/dev/null
    chmod +x "$TMPD/showScreen" 2>/dev/null

    # Test 1: direct (this is what currently fails)
    echo "  Test 1 (direct):" >> "$LOG"
    "$TMPD/showScreen" 2>> "$LOG"
    echo "  exit code: $?" >> "$LOG"

    # Test 2: with waitfor (tests timing theory)
    echo "  Test 2 (waitfor layermanager):" >> "$LOG"
    if waitfor /dev/layermanager 5 2>/dev/null; then
        echo "  waitfor: /dev/layermanager EXISTS" >> "$LOG"
        # Try showing a test image for 3 seconds
        if [ -f "$USB/lib/running.png" ]; then
            "$TMPD/showScreen" -t 3 "$USB/lib/running.png" >> "$LOG" 2>&1
            echo "  showScreen -t 3: exit code $?" >> "$LOG"
        fi
    else
        echo "  waitfor: /dev/layermanager NOT FOUND (timing theory confirmed)" >> "$LOG"
    fi

    # Test 3: direct GF bypass (no layer manager)
    echo "  Test 3 (GF devices):" >> "$LOG"
    ls -la /dev/gf* >> "$LOG" 2>&1
else
    echo "  showScreen binary not available" >> "$LOG"
fi

# === 12. BOOT SCREEN & STORAGE ===
echo "" >> "$LOG"
echo "--- Boot Screen & Storage ---" >> "$LOG"

# HDD boot screens (factory images — where custom screen would go)
echo "  /mnt/share/bootscreens/:" >> "$LOG"
ls -la /mnt/share/bootscreens/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# Count and total size
echo "  Factory boot screen count:" >> "$LOG"
ls /mnt/share/bootscreens/CustomBootscreen_*.bin 2>/dev/null | wc -l >> "$LOG"
echo "" >> "$LOG"

# Current persistence boot screen
echo "  /HBpersistence/CustomBootscreen*:" >> "$LOG"
ls -la /HBpersistence/CustomBootscreen* >> "$LOG" 2>&1
echo "" >> "$LOG"

# Copy current boot screen to USB for reference
for bs in /HBpersistence/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && cp "$bs" "$DUMPDIR/" 2>/dev/null
done

# Disk space — critical for boot screen sizing
echo "  Disk space:" >> "$LOG"
df -h >> "$LOG" 2>&1
echo "" >> "$LOG"

# Persistence partition specifically
echo "  /HBpersistence space:" >> "$LOG"
df /HBpersistence/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# HDD share partition
echo "  /mnt/share space:" >> "$LOG"
df /mnt/share/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# IFS boot screen (the Porsche crest fallback)
echo "  IFS fallback boot screen:" >> "$LOG"
ls -la /proc/boot/PCM31_bootScreenPorscheLogo.jpg >> "$LOG" 2>&1

# Firmware version
echo "" >> "$LOG"
echo "  Firmware version:" >> "$LOG"
cat /mnt/ifs1/HBproject/version.txt >> "$LOG" 2>&1
cat /HBproject/version.txt >> "$LOG" 2>&1

echo "" >> "$LOG"
echo "=== Probe complete. Files in $DUMPDIR ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "Saved: $LOG" >> "$LOG"
