#!/bin/ksh
# PCM-Forge Telnet Enabler — Root shell on port 23 + 2323
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge
#
# PCM /etc/ is READ-ONLY (IFS boot image). Changes are session-only.
# Re-run after each reboot.

USBROOT="${1:-/fs/usb0}"

echo "======== Telnet Enabler ========"

# Mount ASIX USB ethernet driver
if [ -e /dev/io-net ]; then
    mount -T io-net /lib/dll/devn-asix.so 2>&1
elif [ -x /sbin/io-pkt-v4-hc ]; then
    /sbin/io-pkt-v4-hc -d asix verbose &
fi
sleep 3

# Detect interface
IFACE=""
for ifc in en0 en5 en1; do
    ifconfig $ifc >/dev/null 2>&1 && IFACE=$ifc && break
done

if [ -n "$IFACE" ]; then
    echo "[OK] Interface: $IFACE"
else
    echo "[WARN] No new interface — using existing"
fi

# Restart inetd to bind to all interfaces (port 23 telnet)
slay -f inetd 2>/dev/null; sleep 1
/usr/sbin/inetd 2>/dev/null &

# Start raw ksh shell on port 2323 (session only, /etc is read-only)
TMPCONF=/dev/shmem/inetd_extra.conf
echo "2323 stream tcp nowait root /bin/ksh ksh -i" > $TMPCONF
/usr/sbin/inetd $TMPCONF 2>/dev/null &

echo "[OK] inetd restarted (port 23 telnet on all interfaces)"
echo "[OK] Port 2323 raw shell active (session only)"
echo ""
echo "Root shell access:"
echo "  Port 23:   telnet <IP> (login: root)"
echo "  Port 2323: telnet <IP> 2323 (raw shell, no login)"
ifconfig 2>&1

echo "telnet done" >> "${USBROOT}/pcm_ran.txt"
