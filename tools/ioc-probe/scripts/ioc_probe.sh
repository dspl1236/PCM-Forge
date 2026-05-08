#!/bin/sh
# ioc_probe.sh — IOC Channel & BAP Protocol Probe
# Focused on CAN bus discovery for service reset development.
#
# v3: Fixed printf (doesn't exist on QNX) — uses pre-built binary.
#     Fixed timeout handling — channels no longer hang the script.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/ioc_probe.log"
DUMPDIR="$USB/ioc_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge IOC & BAP Probe v3 ===" > "$LOG"
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
echo "--- 3. Key Processes ---" >> "$LOG"
pidin ar 2>/dev/null | grep "dev-ipc\|dev-most\|servicebroker\|PCM3Root\|ndr\|layermanager" >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 4. BAP CHANNEL SCAN ===
echo "--- 4. BAP Channel Scan ---" >> "$LOG"
echo "  Sending BAP A0 Open Request to each channel" >> "$LOG"
echo "  Using pre-built bap_a0.bin (printf not available on QNX)" >> "$LOG"
echo "" >> "$LOG"

BAP_BIN="$USB/bin/bap_a0.bin"
if [ ! -f "$BAP_BIN" ]; then
    echo "  ERROR: bap_a0.bin not found at $BAP_BIN" >> "$LOG"
    echo "  Skipping BAP scan" >> "$LOG"
else
    echo "  bap_a0.bin: $(ls -la $BAP_BIN 2>&1)" >> "$LOG"
    echo "" >> "$LOG"

    for ch in 2 3 4 5 6 7 8 9 10; do
        echo "  ch${ch}:" >> "$LOG"

        if [ -w "/dev/ipc/ioc/ch${ch}" ]; then
            # Write BAP A0 via cat (dd also works)
            cat "$BAP_BIN" > /dev/ipc/ioc/ch${ch} 2>/dev/null
            WRESULT=$?
            echo "    write A0: exit=$WRESULT" >> "$LOG"

            # Read response with 1 second timeout (shorter to avoid hanging)
            RESP="$DUMPDIR/bap_ch${ch}.bin"
            (dd if=/dev/ipc/ioc/ch${ch} of="$RESP" bs=64 count=1 2>/dev/null) &
            DDPID=$!
            sleep 1
            kill $DDPID 2>/dev/null
            wait $DDPID 2>/dev/null

            if [ -f "$RESP" ] && [ -s "$RESP" ]; then
                SIZE=$(ls -la "$RESP" | awk '{print $5}')
                echo "    RESPONSE: $SIZE bytes" >> "$LOG"
                cksum "$RESP" >> "$LOG" 2>&1
                echo "    *** GOT DATA ON ch${ch}! ***" >> "$LOG"
            else
                echo "    No response (1s timeout)" >> "$LOG"
                rm -f "$RESP" 2>/dev/null
            fi
        else
            echo "    Not writable" >> "$LOG"
        fi
    done
fi
echo "" >> "$LOG"

# === 5. SHOWSCREEN SLAY+RESTART TEST ===
echo "--- 5. showScreen slay+restart test ---" >> "$LOG"
SS=""
for s in "$USB/bin/showScreen" /usr/bin/showScreen; do
    [ -f "$s" ] && SS="$s" && break
done
if [ -n "$SS" ] && [ -f "$USB/lib/running.png" ]; then
    TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
    cp "$SS" "$TMPD/showScreen" 2>/dev/null
    chmod +x "$TMPD/showScreen" 2>/dev/null

    echo "  Killing layermanager..." >> "$LOG"
    slay layermanager >> "$LOG" 2>&1
    SLAY_EXIT=$?
    echo "  slay exit: $SLAY_EXIT" >> "$LOG"
    sleep 1

    echo "  Launching showScreen..." >> "$LOG"
    "$TMPD/showScreen" "$USB/lib/running.png" >> "$LOG" 2>&1 &
    SHOW_PID=$!
    sleep 5

    echo "  Killing showScreen (PID $SHOW_PID)..." >> "$LOG"
    kill $SHOW_PID 2>/dev/null
    wait $SHOW_PID 2>/dev/null
    sleep 1

    echo "  Restarting layermanager..." >> "$LOG"
    # Find the layermanager binary and config
    LM_BIN=""
    LM_CFG=""
    for b in /proc/boot/layermanager /usr/bin/layermanager /mnt/ifs1/usr/bin/layermanager; do
        [ -x "$b" ] && LM_BIN="$b" && break
    done
    for c in /proc/boot/layermanager.cfg /etc/system/config/layermanager.cfg; do
        [ -f "$c" ] && LM_CFG="$c" && break
    done
    if [ -n "$LM_BIN" ]; then
        if [ -n "$LM_CFG" ]; then
            "$LM_BIN" -c "$LM_CFG" &
        else
            "$LM_BIN" &
        fi
        LM_PID=$!
        echo "  layermanager restarted: PID $LM_PID" >> "$LOG"
        echo "  PCM3Root should reconnect via retry logic" >> "$LOG"
    else
        echo "  ERROR: layermanager binary not found!" >> "$LOG"
        echo "  Checked: /proc/boot, /usr/bin, /mnt/ifs1/usr/bin" >> "$LOG"
    fi
else
    echo "  showScreen or running.png not available, skipping" >> "$LOG"
fi
echo "" >> "$LOG"

echo "=== Probe complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
