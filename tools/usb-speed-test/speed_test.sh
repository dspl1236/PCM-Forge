#!/bin/ksh
# speed_test.sh -- why does Flash Backup write to USB at only ~29 KB/s?
#
# Measures, one thing at a time:
#   1. reading the flash with nothing written       (fcopy /dev/fs0 -> /dev/null)
#   2. writing the stick from RAM, 4 KB / 16 KB / 64 KB / 1 MB writes (fcopy /dev/zero -> stick)
#   3. the same after `mount -u -o commit=low` on the stick (the PCM mounts sticks
#      commit=high = every write goes straight through), then back to commit=high
#
# Nothing on the PCM changes: the remount only affects this stick, and is undone
# at the end (pulling the stick or a reboot undoes it too). Test files are deleted.
# About 8 minutes. Results: speed_test.log on the stick, summary in pcm_ran.txt.
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="${1:-/fs/usb0}"
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
LOG="$USB/speed_test.log"
SLEEP=sleep; [ -x /proc/boot/sleep ] && SLEEP=/proc/boot/sleep
SECS=40                      # per write test
CAP=16384                    # KB: never write more than 16 MB per test

prog() { echo "$1" > "$TMPD/forge_progress" 2>/dev/null; }
say()  { echo "$1" >> "$LOG"; echo "  speed: $1" >> "$USB/pcm_ran.txt" 2>/dev/null; }
fsize() {
    ls -l "$1" > "$TMPD/.st_ls" 2>/dev/null || { echo 0; return; }
    read _p _l _o _g _s _rest < "$TMPD/.st_ls"; rm -f "$TMPD/.st_ls"; echo "${_s:-0}"
}
mountline() { mount 2>/dev/null | grep " on $USB " ; }

echo "=== PCM-Forge USB speed test ===" > "$LOG"
cat /HBproject/version.txt >> "$LOG" 2>&1
mountline >> "$LOG"
FC="$TMPD/fcopy"
cp "$USB/bin/fcopy" "$FC" 2>> "$LOG" && chmod +x "$FC"
if [ ! -x "$FC" ]; then say "FAILED: bin/fcopy missing"; exit 1; fi
ZERO=/dev/zero; [ -e "$ZERO" ] || ZERO=/dev/fs0

# fcopy prints: bytes=N secs=S kbps=R block_kb=B stop=...
fc() {   # label src dst block_kb secs [max_kb]
    L="$1"; shift
    R=$("$FC" "$@" 2>&1)
    say "$L: $R"
}

# Every write test is fcopy in the foreground: it times itself and stops on
# its own. (Runs 1 and 2 used a background cp stopped after 40 s; the script
# hung there both times, with cp still writing at 29 KB/s -- which already
# gives the cp number, so that test is gone.)
mark() { echo "-- starting: $1" >> "$LOG"; }

rm -f "$USB/st_cp.bin" "$USB/st_w.bin"          # left by the hung runs

mark "1 read"
prog "2/100 Speed test: reading the flash"
fc "1 read flash, 1 MB blocks"   /dev/fs0 /dev/null 1024 60
fc "1 read flash, 64 KB blocks"  /dev/fs0 /dev/null 64 60

N=0
for B in 4 16 64 1024; do
    N=$((N + 1))
    mark "3 RAM -> stick ${B} KB"
    prog "$((5 + N * 10))/100 Speed test: writing from RAM, ${B} KB writes"
    fc "3 write stick from RAM, ${B} KB writes" "$ZERO" "$USB/st_w.bin" $B $SECS $CAP
    rm -f "$USB/st_w.bin"
done
mark "3 flash -> stick 1 MB"
prog "50/100 Speed test: flash to stick, 1 MB writes"
fc "3 flash -> stick, 1024 KB writes" /dev/fs0 "$USB/st_w.bin" 1024 $SECS $CAP
rm -f "$USB/st_w.bin"

mark "4 remount commit=low"
prog "60/100 Speed test: remounting the stick commit=low"
if mount -u -o commit=low "$USB" >> "$LOG" 2>&1; then
    say "4 remount commit=low: OK"
    mountline >> "$LOG"
    for B in 16 1024; do
        mark "4 RAM -> stick ${B} KB, commit=low"
        prog "$((60 + B / 64))/100 Speed test: ${B} KB writes with commit=low"
        fc "4 write stick from RAM, ${B} KB writes, commit=low" "$ZERO" "$USB/st_w.bin" $B $SECS $CAP
        rm -f "$USB/st_w.bin"
    done
    mark "4 flash -> stick 1 MB, commit=low"
    prog "85/100 Speed test: flash to stick with commit=low"
    fc "4 flash -> stick, 1024 KB writes, commit=low" /dev/fs0 "$USB/st_w.bin" 1024 $SECS $CAP
    rm -f "$USB/st_w.bin"
    sync
    mark "4 back to commit=high"
    if mount -u -o commit=high "$USB" >> "$LOG" 2>&1; then
        say "4 back to commit=high: OK"
    else
        say "4 back to commit=high FAILED -- pull the stick and plug it back in"
    fi
    mountline >> "$LOG"
else
    say "4 remount commit=low: refused (see speed_test.log) -- skipped"
fi
sync
say "done"
prog "100/100 Speed test complete"
exit 0
