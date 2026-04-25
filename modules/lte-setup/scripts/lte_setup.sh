#!/bin/ksh
# PCM-Forge LTE Setup — DHCP networking via USB ethernet
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USBROOT="${1:-/fs/usb0}"
LTE_MODE="${2:-dhcp}"

echo "======== LTE Setup ========"
echo "Config: $LTE_MODE"
echo "Detecting network stack..."

NETOK=0
# Try io-net first (PCM3.1 Cayenne uses io-net from boot)
if [ -e /dev/io-net ]; then
    echo "[OK] io-net running — mounting ASIX driver"
    mount -T io-net /lib/dll/devn-asix.so 2>&1
    NETOK=1
else
    echo "[INFO] io-net not found, trying io-pkt-v4-hc..."
    for cmd in /sbin/io-pkt-v4-hc /usr/sbin/io-pkt-v4-hc; do
        if [ -x "$cmd" ]; then
            echo "[OK] Found: $cmd"
            $cmd -d asix verbose &
            NETOK=1
            break
        fi
    done
fi

if [ $NETOK -eq 0 ]; then echo "[ERROR] No network stack found"; fi
sleep 3

# Detect interface name (io-net=en0, io-pkt=en5)
IFACE=""
for ifc in en0 en5 en1; do
    ifconfig $ifc >/dev/null 2>&1 && IFACE=$ifc && break
done
echo "Detected interface: ${IFACE:-NONE}"

# Add gateway/PC to hosts (prevents reverse DNS timeout on telnet)
GWIP=$(route -n show 2>/dev/null | grep default | awk '{print $2}')
if [ -n "$GWIP" ]; then
    echo "$GWIP gateway" >> /etc/hosts 2>/dev/null
    echo "[OK] Added $GWIP to /etc/hosts"
fi

# Restart inetd to bind to all interfaces
slay -f inetd 2>/dev/null; sleep 1
/usr/sbin/inetd 2>/dev/null &
echo "inetd restarted (now listens on $IFACE)"

if [ "$LTE_MODE" = "static" ]; then
    # Static IP mode
    echo "Waiting for adapter..."
    N=0
    while [ $N -lt 60 ]; do
        ifconfig $IFACE >/dev/null 2>&1 && break
        N=$((N + 1)); sleep 2
    done
    if ifconfig $IFACE >/dev/null 2>&1; then
        ifconfig $IFACE 172.16.42.1 netmask 255.255.255.0 up
        echo "Static IP configured: 172.16.42.1"
    else
        echo "en5 not detected after 120s"
    fi
else
    # DHCP mode — background waiter
    echo "Background DHCP waiter started — swap USB for adapter now"
    ( N=0; while [ $N -lt 60 ]; do
        ifconfig $IFACE >/dev/null 2>&1 && break
        N=$((N + 1)); sleep 2
    done
    if [ -n "$IFACE" ] && ifconfig $IFACE >/dev/null 2>&1; then
        dhcp.client -i $IFACE &
        sleep 5
        # Fix DNS
        echo "nameserver 8.8.8.8" > /tmp/resolv.conf
        echo "nameserver 8.8.4.4" >> /tmp/resolv.conf
        ifconfig $IFACE >> "${USBROOT}/pcm_lte_ready.txt" 2>&1
        echo "DNS: 8.8.8.8" >> "${USBROOT}/pcm_lte_ready.txt" 2>&1
        echo "LTE ready" >> "${USBROOT}/pcm_lte_ready.txt" 2>&1
    fi ) &
fi

echo "Network:"
ifconfig 2>&1
echo "Route:"
route -n show 2>&1
echo "DNS:"
cat /etc/resolv.conf 2>&1

echo "lte-setup done" >> "${USBROOT}/pcm_ran.txt"
