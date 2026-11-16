#!/bin/ksh
# forge_net.sh -- PCM-Forge usb-net "every boot": USB Ethernet + telnet after
# every restart, with no stick.
#
# Installed to /HBpersistence by net_boot_setup.sh, which also adds one line to
# /HBpersistence/debugTools.sh (a script the PCM runs on every boot, late, after
# the screen is up) and writes the settings to /HBpersistence/forge_net.conf.
# Remove it with the usb-net stick ("Remove the boot setup").
#
# Waits up to 5 minutes for the adapter, sets it up once, and exits. No adapter
# plugged in: does nothing. Log: /dev/shmem/forge_net.log
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

CONF=/HBpersistence/forge_net.conf
LOG=/dev/shmem/forge_net.log
SLEEP=sleep; [ -x /proc/boot/sleep ] && SLEEP=/proc/boot/sleep
DRIVER=stock; ADDR=static; IP=192.168.0.95; MASK=255.255.255.0; GW=""; SHELL2323=1
[ -f "$CONF" ] && . "$CONF"
UDRV=/HBpersistence/devn-asix-universal.so

echo "forge_net: start (driver=$DRIVER addr=$ADDR ip=$IP)" > "$LOG"

findif() {          # the adapter's interface, if one is up
    for i in en5 en0 en1 en2; do
        ifconfig $i >/dev/null 2>&1 && { echo $i; return; }
    done
}

# 1. wait for the adapter. A 772/772A is loaded by the PCM itself (en5). A
#    772B/772C is not: after giving the PCM a minute, load the universal driver.
IF=""; n=0; LOADED=0
while [ $n -lt 60 ]; do
    IF=$(findif)
    [ -n "$IF" ] && break
    if [ "$DRIVER" = "universal" ] && [ $LOADED -eq 0 ] && [ $n -ge 12 ] && [ -f "$UDRV" ] && [ -e /dev/io-net ]; then
        cp "$UDRV" /dev/shmem/devn-asix-universal.so 2>> "$LOG"
        mount -T io-net /dev/shmem/devn-asix-universal.so >> "$LOG" 2>&1
        echo "forge_net: loaded the universal driver after $((n * 5)) s" >> "$LOG"
        LOADED=1
    fi
    $SLEEP 5
    n=$((n + 1))
done
if [ -z "$IF" ]; then
    echo "forge_net: no adapter after 5 min (not plugged in?) -- nothing done" >> "$LOG"
    exit 0
fi
echo "forge_net: $IF up after $((n * 5)) s" >> "$LOG"

# 2. address
if [ "$ADDR" = "static" ]; then
    # the PCM puts its own 192.168.0.90 on a 772/772A first: wait for it to have
    # an address, set ours, and check again 30 s later (seen on a 958.2: the PCM
    # sets .90 once more after the first change)
    k=0
    while [ $k -lt 12 ] && ! ifconfig $IF 2>/dev/null | grep -q "inet "; do $SLEEP 5; k=$((k + 1)); done
    $SLEEP 5
    ifconfig $IF $IP netmask $MASK up >> "$LOG" 2>&1
    $SLEEP 30
    if ! ifconfig $IF 2>/dev/null | grep -q "inet $IP "; then
        echo "forge_net: address changed back, setting again" >> "$LOG"
        ifconfig $IF $IP netmask $MASK up >> "$LOG" 2>&1
    fi
    [ -n "$GW" ] && route add default $GW >> "$LOG" 2>&1
else
    # DHCP: for a 772/772A the PCM asks the router itself (the setup removed the
    # incar flag that forces .90); a universal-driver adapter needs a client
    if [ $LOADED -eq 1 ]; then
        dhcp.client -i $IF >> "$LOG" 2>&1 &
    fi
fi
ifconfig $IF >> "$LOG" 2>&1

# 3. root shell on port 2323 (once per boot; the file lives in RAM). Telnet on
#    23 is started by the PCM itself because /HBpersistence/DBGModeActive exists.
if [ "$SHELL2323" = "1" ]; then
    if [ ! -f /dev/shmem/inetd_2323.conf ]; then
        echo "2323 stream tcp nowait root /bin/ksh ksh -i" > /dev/shmem/inetd_2323.conf
        /usr/sbin/inetd /dev/shmem/inetd_2323.conf >/dev/null 2>&1 &
        echo "forge_net: shell on 2323 started" >> "$LOG"
    else
        echo "forge_net: shell on 2323 already running" >> "$LOG"
    fi
fi
echo "forge_net: done" >> "$LOG"
exit 0
