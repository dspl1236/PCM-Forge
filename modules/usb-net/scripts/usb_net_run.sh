#!/bin/ksh
# ============================================================
# PCM-Forge  usb-net  —  Universal ASIX USB-Ethernet bring-up
# ------------------------------------------------------------
# Loads a universal devn-asix driver (AX88772 / 772A / 772B / 772C
# + 88178/Linksys/NetGear rebadges) into the running io-net, gets an
# IP, and enables telnet. Runs as root from the copie_scr.sh autorun —
# NO modification of the read-only firmware (loads from /tmp), so a
# bad run just needs a reboot. Result is written back to the USB.
#
#   usb_net_run.sh USBROOT MODE [IP] [MASK] [GATEWAY] [ADAPTER]
#   MODE: dhcp | static | lte              this session only (until a restart)
#         boot-dhcp | boot-static          also at every boot, with no stick
#                                          (net_boot_setup.sh: small files in
#                                          /HBpersistence, undone by "remove")
#         remove                           undo the boot setup
#   ADAPTER (boot modes): auto | stock (772/772A) | universal (772B/772C)
#   github.com/dspl1236/PCM-Forge   (issue #7)
# ============================================================
DRV="devn-asix-universal.so"
MODE="${2:-dhcp}"
STATIC_IP="${3:-${STATIC_IP:-172.16.42.1}}"   # static: address, netmask, optional gateway
STATIC_MASK="${4:-${STATIC_MASK:-255.255.255.0}}"
STATIC_GW="${5:-${STATIC_GW:-}}"
ADAPTER="${6:-auto}"
BOOT=""
case "$MODE" in
    boot-dhcp)   BOOT=dhcp;   MODE=dhcp ;;
    boot-static) BOOT=static; MODE=static ;;
esac
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

SCR="${USBROOT}/scripts"
[ -f "$SCR/net_boot_setup.sh" ] || SCR="${USBROOT}/scripts/USBNet"
if [ "$MODE" = "remove" ]; then
    R=$(ksh "$SCR/net_boot_setup.sh" remove "$LOG" 2>>"$LOG")
    case "$R" in
        removed)      M="boot setup removed: after the next restart the PCM is back to how it was" ;;
        notinstalled) M="no boot setup on this PCM -- nothing to remove" ;;
        *)            M="remove FAILED: $R (see the log)" ;;
    esac
    echo "[..] $M" >> "$LOG"
    echo "usb-net: $M" > "${USBROOT}/pcm_ran.txt"
    sync; exit 0
fi
if [ -z "$DRVPATH" ]; then echo "[ERR] ${DRV} not found on USB" >> "$LOG"; exit 1; fi

# --- an AX88772 / 772A is loaded by the PCM itself on plug-in (its own
#     devn-asix.so, netif=5 -> en5, 192.168.0.90): then use that, load nothing ---
STOCK_IF=""
ifconfig en5 >/dev/null 2>&1 && STOCK_IF=en5
# --- otherwise load the driver from a writable path (RO firmware untouched) ---
cp "$DRVPATH" "${TMPD}/${DRV}" 2>>"$LOG"
if [ -n "$STOCK_IF" ]; then
    echo "[OK] $STOCK_IF already up: the PCM's own driver has the adapter -- not loading the universal one" >> "$LOG"
    ifconfig "$STOCK_IF" >> "$LOG" 2>&1
elif [ -e /dev/io-net ]; then
    echo "[OK] io-net present — mounting universal ASIX driver (verbose)" >> "$LOG"
    mount -T io-net -o "verbose" "${TMPD}/${DRV}" >> "$LOG" 2>&1
elif [ -x /sbin/io-pkt-v4-hc ]; then
    echo "[OK] io-pkt present — mounting via stack" >> "$LOG"
    mount -T io-pkt -o "verbose" "${TMPD}/${DRV}" >> "$LOG" 2>&1
else
    echo "[ERR] no io-net / io-pkt network stack found" >> "$LOG"
fi
[ -z "$STOCK_IF" ] && sleep 5
LOADED_UNIVERSAL=0; [ -z "$STOCK_IF" ] && LOADED_UNIVERSAL=1

# --- find the interface the driver created ---
IFACE="$STOCK_IF"
[ -z "$IFACE" ] && for ifc in en0 en1 en2 en5; do
    ifconfig "$ifc" >/dev/null 2>&1 && IFACE="$ifc" && break
done
echo "[..] interface=${IFACE:-NONE}" >> "$LOG"
[ -n "$IFACE" ] && echo "[..] MAC: $(ifconfig "$IFACE" 2>/dev/null | sed -n 's/.*address: *//p')" >> "$LOG"

# --- address: static | dhcp | lte (= dhcp + DNS/hosts for internet/online services) ---
if [ -n "$IFACE" ]; then
    if [ "$MODE" = "static" ]; then
        ifconfig "$IFACE" "$STATIC_IP" netmask "$STATIC_MASK" up
        echo "[..] static $STATIC_IP/$STATIC_MASK" >> "$LOG"
        if [ -n "$STATIC_GW" ]; then
            route add default "$STATIC_GW" >> "$LOG" 2>&1
            echo "[..] default route via $STATIC_GW" >> "$LOG"
        fi
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
    [ -z "$BOOT" ] && echo "This session only: re-insert the stick after a restart (or use an 'every boot' mode)."
} >> "$LOG" 2>&1

DONE="usb-net done (mode=$MODE)"
if [ -n "$BOOT" ]; then
    # which driver the adapter needs at boot
    DRIVER="$ADAPTER"
    if [ "$DRIVER" = "auto" ]; then
        DRIVER=""
        if [ -n "$STOCK_IF" ]; then
            # up before we loaded anything: the PCM's own driver -- unless the
            # universal one is what io-net has loaded (an earlier stick or boot setup)
            DRIVER=stock
            pidin -p io-net mem 2>/dev/null | grep -q "asix-universal" && DRIVER=universal
        elif [ -n "$IFACE" ] && [ $LOADED_UNIVERSAL -eq 1 ]; then
            DRIVER=universal
        fi
    fi
    if [ -z "$DRIVER" ]; then
        DONE="boot setup NOT installed: no adapter found -- plug it in and run the stick again"
    else
        ADESC=DHCP; [ "$BOOT" = "static" ] && ADESC="static $STATIC_IP"
        mkdir -p "$TMPD/forge_boot"
        cp "$SCR/forge_net.sh" "$TMPD/forge_boot/" 2>>"$LOG"
        cp "$DRVPATH" "$TMPD/forge_boot/" 2>>"$LOG"
        R=$(ksh "$SCR/net_boot_setup.sh" install "$LOG" "$DRIVER" "$BOOT" "$STATIC_IP" "$STATIC_MASK" "$STATIC_GW" "$TMPD/forge_boot" 2>>"$LOG")
        rm -rf "$TMPD/forge_boot"
        case "$R" in
            installed) DONE="boot setup installed ($DRIVER driver, $ADESC): network + telnet come back after every restart" ;;
            unchanged) DONE="boot setup already installed with these settings -- nothing rewritten" ;;
            *)         DONE="boot setup FAILED: $R (see the log)" ;;
        esac
    fi
    echo "[..] $DONE" >> "$LOG"
fi
echo "$DONE" > "${USBROOT}/pcm_ran.txt"
sync
