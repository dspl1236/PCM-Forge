#!/bin/ksh
# ============================================================
# PCM-Forge  usb-net  —  Universal ASIX USB-Ethernet bring-up
# ------------------------------------------------------------
# Loads a universal devn-asix driver (AX88772 / 772A / 772B / 772C
# + 88178/Linksys/NetGear rebadges) into the running io-net, gets an
# IP, and enables telnet. Runs as root from the copie_scr.sh autorun —
# NO modification of the read-only firmware (loads from /tmp), so a
# bad run just needs a reboot. Result is written back to the USB.
#   github.com/dspl1236/PCM-Forge   (issue #7)
# ============================================================
DRV="devn-asix-universal.so"
MODE="${2:-dhcp}"                 # dhcp | static
USBROOT="$1"
[ -z "$USBROOT" ] && USBROOT="/fs/usb0"

# locate the driver (USB root, our script_dir, or any subdir)
DRVPATH=""
for c in "${USBROOT}/${DRV}" "${USBROOT}/scripts/USBNet/${DRV}" "${USBROOT}/bin/${DRV}"; do
    [ -f "$c" ] && DRVPATH="$c" && break
done
[ -z "$DRVPATH" ] && DRVPATH=$(ls "${USBROOT}"/*/"${DRV}" "${USBROOT}"/*/*/"${DRV}" 2>/dev/null | head -1)
DTSTAMP=$(date +%Y%m%d_%H%M%S 2>/dev/null || echo nodate)
LOG="${USBROOT}/pcm_usbnet_${DTSTAMP}.txt"
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs

echo "PCM-Forge usb-net (universal) — $(date 2>/dev/null)" > "$LOG"
echo "driver=$DRVPATH  mode=$MODE" >> "$LOG"
if [ -z "$DRVPATH" ]; then echo "[ERR] ${DRV} not found on USB" >> "$LOG"; exit 1; fi

# --- load the driver from a writable path (RO firmware untouched) ---
cp "$DRVPATH" "${TMPD}/${DRV}" 2>>"$LOG"
if [ -e /dev/io-net ]; then
    echo "[OK] io-net present — mounting universal ASIX driver (verbose)" >> "$LOG"
    mount -T io-net -o "verbose" "${TMPD}/${DRV}" >> "$LOG" 2>&1
elif [ -x /sbin/io-pkt-v4-hc ]; then
    echo "[OK] io-pkt present — mounting via stack" >> "$LOG"
    mount -T io-pkt -o "verbose" "${TMPD}/${DRV}" >> "$LOG" 2>&1
else
    echo "[ERR] no io-net / io-pkt network stack found" >> "$LOG"
fi
sleep 5

# --- find the interface the driver created ---
IFACE=""
for ifc in en0 en1 en2 en5; do
    ifconfig "$ifc" >/dev/null 2>&1 && IFACE="$ifc" && break
done
echo "[..] interface=${IFACE:-NONE}" >> "$LOG"
[ -n "$IFACE" ] && echo "[..] MAC: $(ifconfig "$IFACE" 2>/dev/null | sed -n 's/.*address: *//p')" >> "$LOG"

# --- address: static | dhcp | lte (= dhcp + DNS/hosts for internet/online services) ---
if [ -n "$IFACE" ]; then
    if [ "$MODE" = "static" ]; then
        ifconfig "$IFACE" 172.16.42.1 netmask 255.255.255.0 up
        echo "[..] static 172.16.42.1/24 (direct-cable; set your PC to 172.16.42.x)" >> "$LOG"
    else
        dhcp.client -i "$IFACE" >> "$LOG" 2>&1 &
        sleep 6
        if ! ifconfig "$IFACE" 2>/dev/null | grep -q "inet "; then
            ifconfig "$IFACE" 172.16.42.1 netmask 255.255.255.0 up
            echo "[..] no DHCP lease — fell back to static 172.16.42.1/24" >> "$LOG"
        fi
    fi
    if [ "$MODE" = "lte" ]; then
        # internet/online-services use: set DNS + map the gateway hostname (avoids
        # reverse-DNS stalls). /etc may be RO -> write where the resolver looks and fall
        # back to /tmp; harmless if the unit ignores it.
        GW=$(route -n show 2>/dev/null | grep default | awk '{print $2}')
        for RC in /etc/resolv.conf /tmp/resolv.conf; do
            echo "nameserver 8.8.8.8" >  "$RC" 2>/dev/null
            echo "nameserver 8.8.4.4" >> "$RC" 2>/dev/null
        done
        [ -n "$GW" ] && echo "$GW gateway" >> /etc/hosts 2>/dev/null
        echo "[..] lte mode: DNS 8.8.8.8/8.8.4.4 set, gateway=${GW:-none}" >> "$LOG"
    fi
fi

# --- enable telnet: inetd (port 23) + raw root shell on 2323 (session only) ---
slay -f inetd 2>/dev/null; sleep 1
/usr/sbin/inetd 2>/dev/null &
echo "2323 stream tcp nowait root /bin/ksh ksh -i" > /dev/shmem/inetd_2323.conf
/usr/sbin/inetd /dev/shmem/inetd_2323.conf 2>/dev/null &

# --- record result back to the USB ---
{
    echo ""; echo "--- ifconfig ---"; ifconfig 2>&1
    echo ""; echo "--- driver log ---"
    sloginfo 2>/dev/null | grep -iE 'asix|devn-ax|mii|media|baset|duplex|transceiver|8877' | tail -25
    echo ""; echo "--- connectivity ---"
    GW=$(route -n show 2>/dev/null | grep default | awk '{print $2}')
    [ -n "$GW" ] && { echo "ping gateway $GW:"; ping -c 3 "$GW" 2>&1; }
    echo ""
    echo "If you have an inet address: telnet <that IP>  (port 23 login root, or 2323 raw shell)."
    echo "/etc is read-only — re-insert the stick after each reboot to re-enable."
} >> "$LOG" 2>&1

echo "usb-net done (mode=$MODE)" > "${USBROOT}/pcm_ran.txt"
sync
