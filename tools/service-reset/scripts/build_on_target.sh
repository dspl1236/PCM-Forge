#!/bin/sh
# build_on_target.sh — Link uds_send.o into executable on QNX target
# Run this on the PCM head unit (via telnet or copie_scr.sh)
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
BINDIR="/scripts/ServiceReset"
LOG="$USB/build_uds_send.log"

echo "=== PCM-Forge: Building uds_send ===" > "$LOG"

# Check for the object file
if [ ! -f "$USB/service-reset/bin/uds_send.o" ]; then
    echo "ERROR: uds_send.o not found on USB" >> "$LOG"
    echo "Expected: $USB/service-reset/bin/uds_send.o" >> "$LOG"
    exit 1
fi

mkdir -p "$BINDIR" 2>/dev/null
cp "$USB/service-reset/bin/uds_send.o" "$BINDIR/" 2>/dev/null

# Try method 1: QNX cc compiler (if available)
if [ -x "/usr/bin/cc" ]; then
    echo "Linking with cc..." >> "$LOG"
    /usr/bin/cc -o "$BINDIR/uds_send" "$BINDIR/uds_send.o" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        chmod 755 "$BINDIR/uds_send" 2>/dev/null
        echo "OK: Built with cc" >> "$LOG"
        "$BINDIR/uds_send" >> "$LOG" 2>&1
        exit 0
    fi
fi

# Try method 2: QNX ld linker
if [ -x "/usr/bin/ld" ]; then
    echo "Linking with ld..." >> "$LOG"
    /usr/bin/ld -o "$BINDIR/uds_send" "$BINDIR/uds_send.o" \
        -lc -dynamic-linker /usr/lib/ldqnx.so.2 >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        chmod 755 "$BINDIR/uds_send" 2>/dev/null
        echo "OK: Built with ld" >> "$LOG"
        "$BINDIR/uds_send" >> "$LOG" 2>&1
        exit 0
    fi
fi

# Try method 3: qcc (QNX C compiler)
if [ -x "/usr/bin/qcc" ]; then
    echo "Linking with qcc..." >> "$LOG"
    /usr/bin/qcc -o "$BINDIR/uds_send" "$BINDIR/uds_send.o" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        chmod 755 "$BINDIR/uds_send" 2>/dev/null
        echo "OK: Built with qcc" >> "$LOG"
        "$BINDIR/uds_send" >> "$LOG" 2>&1
        exit 0
    fi
fi

echo "ERROR: No linker found on target" >> "$LOG"
echo "Available in /usr/bin:" >> "$LOG"
ls /usr/bin/cc /usr/bin/ld /usr/bin/qcc /usr/bin/gcc 2>&1 >> "$LOG"
echo "" >> "$LOG"
echo "Try manual link via telnet:" >> "$LOG"
echo "  /usr/bin/ld -o uds_send uds_send.o -lc" >> "$LOG"
exit 1
