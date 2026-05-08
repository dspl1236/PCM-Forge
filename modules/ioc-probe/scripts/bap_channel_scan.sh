#!/bin/sh
# bap_channel_scan.sh — Find which IOC channel carries BAP cluster traffic
# Sends BAP A0 (Open Request) to each channel, looks for A1 response
#
# BAP Open Request: A0 0F 8A FF 4A FF
# BAP Open Response: A1 0F 8A FF 4A FF (from cluster)
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/bap_scan.log"

echo "=== PCM-Forge BAP Channel Scanner ===" > "$LOG"
echo "Looking for BAP cluster on CAN 0x490/0x491" >> "$LOG"
echo "" >> "$LOG"

# BAP A0 Open Request (6 bytes)
# We use printf to write binary data
BAP_OPEN=$(printf '\xA0\x0F\x8A\xFF\x4A\xFF')

for ch in 2 3 4 5 6 7 8 9 10; do
    echo "Scanning ch${ch}..." >> "$LOG"
    
    # Try to open and write the BAP handshake
    if [ -w "/dev/ipc/ioc/ch${ch}" ]; then
        # Write A0 Open Request
        printf '\xA0\x0F\x8A\xFF\x4A\xFF' > /dev/ipc/ioc/ch${ch} 2>/dev/null
        WRESULT=$?
        echo "  Write result: $WRESULT" >> "$LOG"
        
        # Try to read response (2 second timeout)
        RESP_FILE="$USB/bap_resp_ch${ch}.bin"
        (dd if=/dev/ipc/ioc/ch${ch} of="$RESP_FILE" bs=64 count=1 2>/dev/null) &
        DDPID=$!
        sleep 2
        kill $DDPID 2>/dev/null
        wait $DDPID 2>/dev/null
        
        if [ -f "$RESP_FILE" ] && [ -s "$RESP_FILE" ]; then
            SIZE=$(ls -la "$RESP_FILE" | awk '{print $5}')
            echo "  RESPONSE: $SIZE bytes" >> "$LOG"
            # Check first byte for A1 (BAP Open Acknowledge)
            FIRST=$(dd if="$RESP_FILE" bs=1 count=1 2>/dev/null | od -A n -t x1 | tr -d ' ')
            echo "  First byte: 0x$FIRST" >> "$LOG"
            if [ "$FIRST" = "a1" ]; then
                echo "  *** FOUND BAP CLUSTER ON ch${ch}! ***" >> "$LOG"
            fi
        else
            echo "  No response (timeout)" >> "$LOG"
            rm -f "$RESP_FILE" 2>/dev/null
        fi
    else
        echo "  Not writable" >> "$LOG"
    fi
    echo "" >> "$LOG"
done

echo "=== Scan complete ===" >> "$LOG"
