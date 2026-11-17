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
#   MODE: dhcp | static (lte = dhcp)       this session only (until a restart)
#         every mode sets the default route + DNS when there is a gateway
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
if [ -z "$DRVPATH" ]; then     # (no head on the PCM: first match by loop)
    for c in "${USBROOT}"/*/"${DRV}" "${USBROOT}"/*/*/"${DRV}"; do
        [ -f "$c" ] && { DRVPATH="$c"; break; }
    done
fi
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
    sync 2>/dev/null; exit 0
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

# --- internet: default route + DNS, in every mode. The PCM has sed and grep
#     but no awk/head. /etc is read-only, so resolv.conf lives in RAM and a
#     pathname link (ln -sP) puts it at /etc/resolv.conf until the next restart.
default_gw() {
    set -- $(route -n show 2>/dev/null | sed -n 's/^default  *\([0-9][0-9.]*\).*/\1/p')
    echo "$1"
}
net_internet() {    # $1 gateway (empty: take the DHCP one)
    G="$1"; [ -z "$G" ] && G=$(default_gw)
    if [ -z "$G" ]; then
        echo "[..] internet: no gateway -- local network only (static: fill in the gateway for internet)" >> "$LOG"
        return
    fi
    route -n show 2>/dev/null | grep -q "^default" || route add default "$G" >> "$LOG" 2>&1
    { echo "nameserver $G"; echo "nameserver 8.8.8.8"; } > /dev/shmem/forge_resolv.conf
    grep -q nameserver /etc/resolv.conf 2>/dev/null || ln -sP /dev/shmem/forge_resolv.conf /etc/resolv.conf >> "$LOG" 2>&1
    echo "[..] internet: via $G (DNS $G, 8.8.8.8)" >> "$LOG"
}

# --- address: static | dhcp (lte = dhcp: every mode now sets up internet) ---
if [ -n "$IFACE" ]; then
    if [ "$MODE" = "static" ]; then
        # a DHCP client still running (the PCM's own after a DHCP boot, or an
        # earlier stick) would put its address back at the next lease renewal
        if pidin -p dhcp.client arg 2>/dev/null | grep -q "dhcp.client"; then
            slay -f -Q dhcp.client 2>/dev/null
            echo "[..] stopped the running DHCP client (static from now on)" >> "$LOG"
            sleep 1
        fi
        ifconfig "$IFACE" "$STATIC_IP" netmask "$STATIC_MASK" up
        echo "[..] static $STATIC_IP/$STATIC_MASK" >> "$LOG"
        net_internet "$STATIC_GW"
    else
        # -m: the router's DNS servers go to memory (/etc is read-only)
        dhcp.client -i "$IFACE" -m >> "$LOG" 2>&1 &
        k=0
        while [ $k -lt 6 ] && ! ifconfig "$IFACE" 2>/dev/null | grep -q "inet "; do sleep 2; k=$((k + 1)); done
        if ifconfig "$IFACE" 2>/dev/null | grep -q "inet "; then
            sleep 3        # the default route lands with the lease
            net_internet ""
        else
            ifconfig "$IFACE" 172.16.42.1 netmask 255.255.255.0 up
            echo "[..] no DHCP lease — fell back to static 172.16.42.1/24 (no internet)" >> "$LOG"
        fi
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
    sloginfo 2>/dev/null | grep -iE 'asix|devn-ax|mii|baset|duplex|transceiver|8877' | tail -25
    echo ""; echo "--- connectivity ---"
    route -n show 2>&1
    echo "resolv.conf:"; cat /etc/resolv.conf 2>&1
    GW=$(default_gw)
    # the PCM has no working ping: nettest (bin/nettest, tools/sh4-toolchain/nettest.c)
    # looks up a name and opens a TCP connection
    NT=""
    for c in "${USBROOT}/bin/nettest" "${USBROOT}/scripts/USBNet/nettest"; do [ -f "$c" ] && { NT="$c"; break; }; done
    if [ -n "$GW" ] && [ -n "$NT" ] && cp "$NT" "${TMPD}/nettest" 2>/dev/null; then
        chmod +x "${TMPD}/nettest"
        echo "internet check:"; "${TMPD}/nettest" www.google.com 80 2>&1
    fi
    echo ""
    echo "If you have an inet address: telnet <that IP>  (port 23 login root, or 2323 raw shell)."
    [ -z "$BOOT" ] && echo "This session only: re-insert the stick after a restart (or use an 'every boot' mode)."
} >> "$LOG" 2>&1

DONE="usb-net done (mode=$MODE, $IFACE)"
[ -z "$IFACE" ] && DONE="usb-net: NO ADAPTER FOUND -- the adapter has to be plugged in while the stick runs (a USB hub works: adapter + stick together), then run the stick again"
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
        else
            # no adapter plugged in (one USB port, stick in it): install with the
            # universal driver. That covers every adapter: at boot a 772/772A comes
            # up on the PCM's own driver within seconds, and forge_net.sh only loads
            # the universal one if nothing has appeared after 60 s.
            DRIVER=universal
            echo "[..] no adapter plugged in: installing with the universal driver (works for any supported adapter)" >> "$LOG"
        fi
    fi
    if [ -z "$DRIVER" ]; then
        DONE="boot setup NOT installed: no driver chosen"
    else
        ADESC=DHCP; [ "$BOOT" = "static" ] && ADESC="static $STATIC_IP"
        mkdir -p "$TMPD/forge_boot"
        cp "$SCR/forge_net.sh" "$TMPD/forge_boot/" 2>>"$LOG"
        cp "$DRVPATH" "$TMPD/forge_boot/" 2>>"$LOG"
        R=$(ksh "$SCR/net_boot_setup.sh" install "$LOG" "$DRIVER" "$BOOT" "$STATIC_IP" "$STATIC_MASK" "$STATIC_GW" "$TMPD/forge_boot" 2>>"$LOG")
        rm -rf "$TMPD/forge_boot"
        case "$R" in
            installed) DONE="boot setup installed ($DRIVER driver, $ADESC): network + telnet come back after every restart"
                       [ -z "$IFACE" ] && DONE="$DONE -- plug the adapter in and restart the PCM; it comes up about a minute after the screen" ;;
            unchanged) DONE="boot setup already installed with these settings -- nothing rewritten" ;;
            *)         DONE="boot setup FAILED: $R (see the log)" ;;
        esac
    fi
    echo "[..] $DONE" >> "$LOG"
fi
echo "$DONE" > "${USBROOT}/pcm_ran.txt"
sync 2>/dev/null
