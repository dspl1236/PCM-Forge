#!/bin/sh
# ioc_probe.sh — IOC Channel & BAP Protocol Probe
# Focused on CAN bus discovery for service reset development.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/ioc_probe.log"
DUMPDIR="$USB/ioc_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge IOC & BAP Probe ===" > "$LOG"
echo "Date: $(date 2>/dev/null || echo unknown)" >> "$LOG"
echo "" >> "$LOG"

# === 1. IOC CHANNEL MAP ===
echo "--- 1. IOC Channels ---" >> "$LOG"
ls -la /dev/ipc/ioc/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 2. NDR DEVICES ===
echo "--- 2. NDR Devices ---" >> "$LOG"
ls -la /dev/ndr/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 3. DEV-IPC CONFIG ===
echo "--- 3. dev-ipc Process ---" >> "$LOG"
pidin ar 2>/dev/null | grep "dev-ipc\|dev-most\|servicebroker\|PCM3Root\|ndr" >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 4. BAP CHANNEL SCAN ===
# Send BAP A0 (Open Request) to each writable channel
# The channel that responds with A1 is the BAP cluster channel
echo "--- 4. BAP Channel Scan ---" >> "$LOG"
echo "  Sending A0 handshake to each channel..." >> "$LOG"
echo "  Looking for A1 response (cluster BAP)" >> "$LOG"
echo "" >> "$LOG"

for ch in 2 3 4 5 6 7 8 9 10; do
    echo "  ch${ch}:" >> "$LOG"
    
    if [ -w "/dev/ipc/ioc/ch${ch}" ]; then
        # Write BAP A0 Open Request
        printf '\xA0\x0F\x8A\xFF\x4A\xFF' > /dev/ipc/ioc/ch${ch} 2>/dev/null
        WRESULT=$?
        echo "    write A0: exit=$WRESULT" >> "$LOG"
        
        # Read response (2 sec timeout)
        RESP="$DUMPDIR/bap_ch${ch}.bin"
        (dd if=/dev/ipc/ioc/ch${ch} of="$RESP" bs=64 count=1 2>/dev/null) &
        DDPID=$!
        sleep 2
        kill $DDPID 2>/dev/null
        wait $DDPID 2>/dev/null
        
        if [ -f "$RESP" ] && [ -s "$RESP" ]; then
            SIZE=$(ls -la "$RESP" | awk '{print $5}')
            echo "    RESPONSE: $SIZE bytes" >> "$LOG"
            # Hex dump response
            cksum "$RESP" >> "$LOG" 2>&1
            # Check for A1
            FIRST=$(dd if="$RESP" bs=1 count=1 2>/dev/null | od -A n -t x1 2>/dev/null | tr -d ' ')
            echo "    First byte: 0x$FIRST" >> "$LOG"
            if [ "$FIRST" = "a1" ]; then
                echo "    *** BAP CLUSTER FOUND ON ch${ch}! ***" >> "$LOG"
            fi
        else
            echo "    No response (2s timeout)" >> "$LOG"
            rm -f "$RESP" 2>/dev/null
        fi
    else
        echo "    Not writable" >> "$LOG"
    fi
done
echo "" >> "$LOG"

# === 5. SHOWSCREEN SLAY TEST ===
echo "--- 5. showScreen slay test ---" >> "$LOG"
SS=""
for s in "$USB/bin/showScreen" /usr/bin/showScreen; do
    [ -f "$s" ] && SS="$s" && break
done
if [ -n "$SS" ] && [ -f "$USB/lib/running.png" ]; then
    TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
    cp "$SS" "$TMPD/showScreen" 2>/dev/null
    chmod +x "$TMPD/showScreen" 2>/dev/null
    
    echo "  Attempting slay+showScreen sequence..." >> "$LOG"
    # Kill layermanager, show image, restart
    slay layermanager 2>/dev/null
    sleep 1
    "$TMPD/showScreen" -t 5 "$USB/lib/running.png" >> "$LOG" 2>&1
    SHOW_EXIT=$?
    echo "  showScreen exit: $SHOW_EXIT" >> "$LOG"
    sleep 1
    # Restart layermanager — PCM3Root has retry logic
    /proc/boot/layermanager -c /proc/boot/layermanager.cfg &
    LM_PID=$!
    echo "  layermanager restarted: PID $LM_PID" >> "$LOG"
else
    echo "  showScreen or running.png not available" >> "$LOG"
fi
echo "" >> "$LOG"

echo "=== Probe complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
