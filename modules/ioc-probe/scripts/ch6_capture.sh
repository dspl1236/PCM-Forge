#!/bin/sh
# ch6_capture.sh — Capture live CAN traffic from IOC ch6
# The V850 forwards CAN data to ch6 constantly.
# Capturing one message reveals the IPC message format.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/ch6_capture.log"
DUMPDIR="$USB/ioc_dump"
mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge ch6 CAN Traffic Capture ===" > "$LOG"
echo "" >> "$LOG"

CHAN="/dev/ipc/ioc/ch6"

if [ ! -r "$CHAN" ]; then
    echo "ERROR: $CHAN not readable" >> "$LOG"
    exit 1
fi

echo "Capturing from $CHAN..." >> "$LOG"

# Method 1: dd with 3-second timeout, small block size
echo "--- Method 1: dd bs=1 count=256 (3s timeout) ---" >> "$LOG"
(dd if="$CHAN" of="$DUMPDIR/ch6_raw_1.bin" bs=1 count=256 2>/dev/null) &
PID1=$!
sleep 3
kill $PID1 2>/dev/null
wait $PID1 2>/dev/null
if [ -f "$DUMPDIR/ch6_raw_1.bin" ] && [ -s "$DUMPDIR/ch6_raw_1.bin" ]; then
    SIZE=$(ls -la "$DUMPDIR/ch6_raw_1.bin" | awk '{print $5}')
    echo "  Captured: $SIZE bytes" >> "$LOG"
    cksum "$DUMPDIR/ch6_raw_1.bin" >> "$LOG" 2>&1
else
    echo "  No data (blocked)" >> "$LOG"
    rm -f "$DUMPDIR/ch6_raw_1.bin" 2>/dev/null
fi
echo "" >> "$LOG"

# Method 2: dd with larger block size
echo "--- Method 2: dd bs=512 count=1 (3s timeout) ---" >> "$LOG"
(dd if="$CHAN" of="$DUMPDIR/ch6_raw_2.bin" bs=512 count=1 2>/dev/null) &
PID2=$!
sleep 3
kill $PID2 2>/dev/null
wait $PID2 2>/dev/null
if [ -f "$DUMPDIR/ch6_raw_2.bin" ] && [ -s "$DUMPDIR/ch6_raw_2.bin" ]; then
    SIZE=$(ls -la "$DUMPDIR/ch6_raw_2.bin" | awk '{print $5}')
    echo "  Captured: $SIZE bytes" >> "$LOG"
    cksum "$DUMPDIR/ch6_raw_2.bin" >> "$LOG" 2>&1
else
    echo "  No data (blocked)" >> "$LOG"
    rm -f "$DUMPDIR/ch6_raw_2.bin" 2>/dev/null
fi
echo "" >> "$LOG"

# Method 3: cat with timeout (captures whatever is available)
echo "--- Method 3: cat (3s timeout) ---" >> "$LOG"
(cat "$CHAN" > "$DUMPDIR/ch6_raw_3.bin" 2>/dev/null) &
PID3=$!
sleep 3
kill $PID3 2>/dev/null
wait $PID3 2>/dev/null
if [ -f "$DUMPDIR/ch6_raw_3.bin" ] && [ -s "$DUMPDIR/ch6_raw_3.bin" ]; then
    SIZE=$(ls -la "$DUMPDIR/ch6_raw_3.bin" | awk '{print $5}')
    echo "  Captured: $SIZE bytes" >> "$LOG"
    cksum "$DUMPDIR/ch6_raw_3.bin" >> "$LOG" 2>&1
else
    echo "  No data (blocked)" >> "$LOG"
    rm -f "$DUMPDIR/ch6_raw_3.bin" 2>/dev/null
fi
echo "" >> "$LOG"

# Method 4: Try ch8 (the other data channel from PCM3Root)
echo "--- Method 4: ch8 capture (3s timeout) ---" >> "$LOG"
(dd if="/dev/ipc/ioc/ch8" of="$DUMPDIR/ch8_raw.bin" bs=512 count=1 2>/dev/null) &
PID4=$!
sleep 3
kill $PID4 2>/dev/null
wait $PID4 2>/dev/null
if [ -f "$DUMPDIR/ch8_raw.bin" ] && [ -s "$DUMPDIR/ch8_raw.bin" ]; then
    SIZE=$(ls -la "$DUMPDIR/ch8_raw.bin" | awk '{print $5}')
    echo "  Captured: $SIZE bytes" >> "$LOG"
    cksum "$DUMPDIR/ch8_raw.bin" >> "$LOG" 2>&1
else
    echo "  No data (blocked)" >> "$LOG"
    rm -f "$DUMPDIR/ch8_raw.bin" 2>/dev/null
fi
echo "" >> "$LOG"

echo "=== Capture complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
