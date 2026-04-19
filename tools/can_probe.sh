#!/bin/ksh
# PCM-Forge CAN/IOC Probe — https://github.com/dspl1236/PCM-Forge
# Investigates the V850 IOC interface for CAN bus access
# READ-ONLY — no writes to any device
USBROOT="$1"
[ -z "$USBROOT" ] && USBROOT="/fs/usb0"
LOG="${USBROOT}/can_probe.log"
DUMPDIR="${USBROOT}/can_dump"
mkdir -p "$DUMPDIR" 2>/dev/null
{
    echo "============================================"
    echo "  PCM-Forge CAN/IOC Probe"
    echo "============================================"
    echo ""

    echo "=== IPC Devices ==="
    ls -la /dev/ipc/ 2>&1
    ls -laR /dev/ipc/ioc/ 2>&1
    echo ""

    echo "=== DSP IPC Devices ==="
    ls -laR /dev/dspipc/ 2>&1
    echo ""

    echo "=== All /dev entries ==="
    ls /dev/ 2>&1
    echo ""

    echo "=== /dev/ipc/ioc channel info ==="
    for ch in /dev/ipc/ioc/ch /dev/ipc/ioc/ch2 /dev/ipc/ioc/ch6 /dev/ipc/ioc/ch8; do
        if [ -e "$ch" ]; then
            echo "--- $ch ---"
            ls -la "$ch" 2>&1
            # Try to get device info via devctl/stat
            stat "$ch" 2>&1
        fi
    done
    echo ""

    echo "=== /hbsystem ==="
    ls -laR /hbsystem/ 2>&1
    echo ""

    echo "=== Multicore/DSI Services ==="
    ls -la /hbsystem/multicore/ 2>&1
    echo ""

    echo "=== Service Broker ==="
    ls -la /srv/ 2>&1
    ls -la /srv/servicebroker 2>&1
    echo ""

    echo "=== Sysregs (FPGA) ==="
    ls -la /dev/sysregs/ 2>&1
    echo ""

    echo "=== MOST network ==="
    ls -la /dev/most* 2>&1
    echo ""

    echo "=== PCM3Root loaded libraries ==="
    pidin -p PCM3Root mem 2>&1 | grep ".so" | head -20
    echo ""

    echo "=== GEM Engineering ESD files ==="
    # Check multiple possible paths
    for dir in /mnt/flash/efs1/engdefs /HBpersistence/engdefs /mnt/ifs1/engdefs /mnt/share/engdefs; do
        if [ -d "$dir" ]; then
            echo "Found: $dir"
            ls "$dir" 2>&1
        fi
    done
    echo ""

    echo "=== Kombi/Instrument Cluster CAN messages ==="
    # Search slogger for CAN-related messages
    sloginfo 2>&1 | grep -i "CAN\|combi\|Kombi\|cluster\|IOC\|ioc\|service\|interval" | tail -30
    echo ""

    echo "=== GEM/Engineering Config ==="
    cat /HBpersistence/sqlite.xml 2>&1
    echo ""
    # screensaver.conf!
    echo "=== screensaver.conf ==="
    cat /HBpersistence/screensaver.conf 2>&1
    echo ""
    od -c /HBpersistence/screensaver.conf 2>&1
    echo ""

    echo "=== hybrid.bin ==="
    od -A x -t x1z /HBpersistence/hybrid.bin 2>&1 | head -20
    echo ""

    echo "=== test.html / test1.html ==="
    cat /HBpersistence/test.html 2>&1
    echo ""
    cat /HBpersistence/test1.html 2>&1
    echo ""

    echo "=== inetd.conf ==="
    cat /etc/inetd.conf 2>&1
    echo ""

    echo "=== Environment ==="
    env 2>&1
    echo ""

    echo "=== QNX System Info ==="
    sysinfo 2>&1 | head -30
    echo ""

    echo "=== PCM3Root DSI bindings ==="
    # Try to find service connections
    ls -la /dev/dsi/ 2>&1
    ls -la /dev/name/ 2>&1
    echo ""

    echo "=== Probe complete ==="
} > "$LOG" 2>&1

# Copy key files
cp /HBpersistence/screensaver.conf "$DUMPDIR/" 2>/dev/null
cp /HBpersistence/hybrid.bin "$DUMPDIR/" 2>/dev/null
cp /HBpersistence/test.html "$DUMPDIR/" 2>/dev/null
cp /HBpersistence/test1.html "$DUMPDIR/" 2>/dev/null

echo "CAN probe done" > "${USBROOT}/pcm_ran.txt" 2>/dev/null
