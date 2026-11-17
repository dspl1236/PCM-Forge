#!/bin/ksh
# net_boot_setup.sh -- install or remove usb-net's "every boot" setup.
#
#   net_boot_setup.sh install LOG DRIVER ADDR IP MASK GW SRCDIR
#   net_boot_setup.sh remove  LOG
#
# DRIVER = stock (772/772A, loaded by the PCM itself) | universal (772B/772C)
# ADDR   = dhcp | static
# SRCDIR = where forge_net.sh (and devn-asix-universal.so) are on the stick
#
# Writes only to /HBpersistence, and only what is missing or changed, so a stick
# left in (or inserted again) rewrites nothing. What it changes:
#   forge_net.sh, forge_net.conf          the boot script and its settings
#   devn-asix-universal.so                only for a 772B/772C
#   debugTools.sh                         one line added (backup: debugTools.sh.forge-orig)
#   DBGModeActive                         created if missing (it starts telnet at boot)
#   incar                                 removed for DHCP, created for static
# forge_net.orig records how DBGModeActive and incar were before the first
# install; "remove" puts them back that way and deletes everything else.
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

P="${FORGE_P:-/HBpersistence}"          # override only for off-car testing
T="${FORGE_TMP:-/dev/shmem}"
ACT="$1"; LOG="${2:-/dev/null}"
HOOK="[ -f $P/forge_net.sh ] && /bin/ksh $P/forge_net.sh > /dev/null 2>&1 &   # PCM-Forge usb-net: network at every boot (remove with the usb-net stick)"
CHANGED=0
note() { echo "[boot] $1" >> "$LOG"; }

# write $2 to file $1 only when different; text files only
put() {
    if [ -f "$1" ] && [ "$(cat "$1" 2>/dev/null)" = "$2" ]; then return 0; fi
    echo "$2" > "$1.forge-new" && mv -f "$1.forge-new" "$1" && CHANGED=1 && note "wrote ${1##*/}"
}
fsize() {
    ls -l "$1" > $T/.nbs_ls 2>/dev/null || { echo 0; return; }
    read _p _l _o _g _s _rest < $T/.nbs_ls; rm -f $T/.nbs_ls; echo "${_s:-0}"
}
# copy text file $1 to $2 only when the contents differ (cp, so nothing is
# re-interpreted on the way)
puttext() {
    [ -f "$2" ] && [ "$(cat "$2" 2>/dev/null)" = "$(cat "$1" 2>/dev/null)" ] && return 0
    cp "$1" "$2" && CHANGED=1 && note "copied ${2##*/}"
}
# a copy of file $1 to $2 only when the size differs (the driver: a binary)
putbin() {
    [ -f "$2" ] && [ "$(fsize "$1")" = "$(fsize "$2")" ] && return 0
    cp "$1" "$2" && CHANGED=1 && note "copied ${2##*/}"
}

case "$ACT" in
install)
    DRIVER="$3"; ADDR="$4"; IP="$5"; MASK="${6:-255.255.255.0}"; GW="$7"; SRC="$8"
    [ -f "$SRC/forge_net.sh" ] || { note "FAILED: forge_net.sh not on the stick"; exit 1; }

    # how the car was before the very first install (kept across reinstalls)
    if [ ! -f $P/forge_net.orig ]; then
        D=0; [ -f $P/DBGModeActive ] && D=1
        I=0; [ -f $P/incar ] && I=1
        echo "DBG_WAS=$D
INCAR_WAS=$I" > $P/forge_net.orig && CHANGED=1
        note "recorded the car's own state: DBGModeActive=$D incar=$I"
    fi

    puttext "$SRC/forge_net.sh" $P/forge_net.sh
    chmod 755 $P/forge_net.sh 2>/dev/null
    put $P/forge_net.conf "# PCM-Forge usb-net boot settings (read by forge_net.sh)
DRIVER=$DRIVER
ADDR=$ADDR
IP=$IP
MASK=$MASK
GW=$GW
SHELL2323=1"
    if [ "$DRIVER" = "universal" ]; then
        if [ -f "$SRC/devn-asix-universal.so" ]; then putbin "$SRC/devn-asix-universal.so" $P/devn-asix-universal.so
        else note "FAILED: devn-asix-universal.so not on the stick"; exit 1; fi
    elif [ -f $P/devn-asix-universal.so ]; then
        rm -f $P/devn-asix-universal.so && CHANGED=1 && note "removed the universal driver (not needed for this adapter)"
    fi

    # the hook: once, at the end of the PCM's own boot script
    if ! grep -q "forge_net.sh" $P/debugTools.sh 2>/dev/null; then
        [ -f $P/debugTools.sh.forge-orig ] || cp $P/debugTools.sh $P/debugTools.sh.forge-orig 2>/dev/null
        if [ -f $P/debugTools.sh ]; then echo "$HOOK" >> $P/debugTools.sh
        else echo "#!/bin/ksh
$HOOK" > $P/debugTools.sh; fi
        CHANGED=1; note "added the boot line to debugTools.sh"
    fi

    # telnet at boot, and how a 772/772A gets its address
    [ -f $P/DBGModeActive ] || { touch $P/DBGModeActive && CHANGED=1 && note "created DBGModeActive (telnet at boot)"; }
    if [ "$ADDR" = "dhcp" ]; then
        [ -f $P/incar ] && { rm -f $P/incar && CHANGED=1 && note "removed incar: the PCM now asks the router for an address"; }
    else
        [ -f $P/incar ] || { touch $P/incar && CHANGED=1 && note "created incar: the PCM uses a fixed address"; }
    fi
    sync 2>/dev/null
    if [ $CHANGED -eq 1 ]; then echo installed; else echo unchanged; fi
    ;;

remove)
    if [ ! -f $P/forge_net.sh ] && [ ! -f $P/forge_net.conf ] && ! grep -q "forge_net.sh" $P/debugTools.sh 2>/dev/null; then
        echo "notinstalled"; exit 0
    fi
    if grep -q "forge_net.sh" $P/debugTools.sh 2>/dev/null; then
        grep -v "forge_net.sh" $P/debugTools.sh > $T/.nbs_dt && cp $T/.nbs_dt $P/debugTools.sh
        rm -f $T/.nbs_dt
        note "removed the boot line from debugTools.sh"
    fi
    rm -f $P/debugTools.sh.forge-orig $P/forge_net.sh $P/forge_net.conf $P/devn-asix-universal.so
    if [ -f $P/forge_net.orig ]; then
        . $P/forge_net.orig
        [ "$DBG_WAS" = "0" ] && rm -f $P/DBGModeActive && note "removed DBGModeActive (the car didn't have it)"
        [ "$INCAR_WAS" = "1" ] && [ ! -f $P/incar ] && touch $P/incar && note "put incar back"
        [ "$INCAR_WAS" = "0" ] && [ -f $P/incar ] && rm -f $P/incar && note "removed incar (the car didn't have it)"
        rm -f $P/forge_net.orig
    fi
    sync 2>/dev/null
    echo removed
    ;;
*)
    echo "usage: net_boot_setup.sh install|remove ..."; exit 2 ;;
esac
exit 0
