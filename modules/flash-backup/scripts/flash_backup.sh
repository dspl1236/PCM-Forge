#!/bin/ksh
# flash_backup.sh -- copy the PCM 3.1's whole 64 MB NOR flash to the USB stick.
#
# READ-ONLY. It is the same read the PCM's own engineering menu does
# (System > CustomerService > 05 "Copy 64MB flash contents to USB", which runs
# "cp /dev/fs0 /fs/usb0/..."), without needing the menu or the ENGINEERING
# activation. Make one before any update or experiment; check it on a computer
# with PCM-Explorer:  python explorer.py pcm_flash.bin check
# See guides/RECOVERY.md in PCM-Forge.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="${1:-/fs/usb0}"
DEV="${FLASH_DEV:-/dev/fs0}"          # override only for off-car testing
FULL=67108864                         # 64 MB: two S29GL256N chips
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
LOG="$USB/flash_backup.log"

# progress for the status splash (forge_splash v2.1) + a line in pcm_ran.txt
prog() { echo "$1" > "$TMPD/forge_progress" 2>/dev/null; }
say()  { echo "$1" >> "$LOG"; echo "  flash-backup: $1" >> "$USB/pcm_ran.txt" 2>/dev/null; }
# size of a file without awk/stat: the 5th field of ls -l
fsize() {
    ls -l "$1" > "$TMPD/.fb_ls" 2>/dev/null || { echo 0; return; }
    read _p _l _o _g _s _rest < "$TMPD/.fb_ls"
    rm -f "$TMPD/.fb_ls"
    echo "${_s:-0}"
}

echo "=== PCM-Forge Flash Backup ===" > "$LOG"
echo x > "$TMPD/.fb_now" 2>/dev/null           # no date(1): the unit's clock via a stamp
ls -la "$TMPD/.fb_now" >> "$LOG" 2>&1; rm -f "$TMPD/.fb_now"
cat /HBproject/version.txt >> "$LOG" 2>&1
prog "0/100 Flash backup: starting"

if [ ! -e "$DEV" ]; then
    say "FAILED: $DEV not found -- nothing copied"
    prog "100/100 Flash backup FAILED: no $DEV"
    exit 1
fi
ls -la "$DEV" >> "$LOG" 2>&1

# One copy at a time. Pulling the stick and plugging it back in starts the
# autorun again; the pulled run is dead by then, so a lock whose process is
# gone is taken over rather than blocking.
LOCK="$TMPD/.forge_flash_backup.pid"
if [ -f "$LOCK" ]; then
    OLD=$(cat "$LOCK" 2>/dev/null)
    if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
        say "another Flash Backup is already running (pid $OLD) -- not starting a second copy"
        exit 0
    fi
fi
echo $$ > "$LOCK"

# A copy cut short by pulling the stick is useless: remove it (and its side
# files) so the stick holds only complete backups.
for f in "$USB"/pcm_flash*.bin; do
    [ -f "$f" ] || continue
    S=$(fsize "$f")
    if [ "$S" != "$FULL" ]; then
        say "removed ${f##*/}: only $S bytes, left by an interrupted run"
        rm -f "$f" "${f%.bin}_PagSWAct.002" "${f%.bin}_vin.txt"
    fi
done

# never overwrite an earlier backup: pcm_flash.bin, then pcm_flash_2.bin ...
OUT="$USB/pcm_flash.bin"; N=2
while [ -e "$OUT" ] && [ $N -le 9 ]; do OUT="$USB/pcm_flash_$N.bin"; N=$((N + 1)); done
if [ -e "$OUT" ]; then
    say "FAILED: pcm_flash.bin .. pcm_flash_9.bin already on the stick -- move them off first"
    prog "100/100 Flash backup FAILED: stick already holds 9 backups"
    rm -f "$LOCK"
    exit 1
fi

# the activation file and stored VIN next to it: small, and what you'd want first
cp /HBpersistence/PagSWAct.002 "${OUT%.bin}_PagSWAct.002" 2>/dev/null
cp /HBpersistence/vin "${OUT%.bin}_vin.txt" 2>/dev/null

# Writing to the stick is what's slow: each write costs ~0.5 s whatever its
# size (the PCM mounts sticks commit=high), so cp's small writes manage only
# ~30 KB/s (35+ minutes). fcopy writes 1 MB at a time, and the stick is
# remounted commit=low for the copy: ~1 MB/s, about a minute (speed test on a
# 958.2, 11-2026). Without bin/fcopy it falls back to the slow cp.
FC=""
for c in "$USB/bin/fcopy" "$USB/scripts/FlashBackup/fcopy" "$USB/fcopy"; do
    [ -f "$c" ] && { cp "$c" "$TMPD/fcopy" 2>/dev/null && chmod +x "$TMPD/fcopy" && FC="$TMPD/fcopy"; break; }
done
if [ -n "$FC" ]; then                    # it must run here: with no arguments it prints usage, exit 2
    "$FC" > /dev/null 2>&1
    [ $? -eq 2 ] || { echo "bin/fcopy does not run on this unit" >> "$LOG"; FC=""; }
fi
# the PCM's own load monitor: count its "CPU Load" warnings before and after
GAU=/mnt/data/log/GauMemory
loadwarn() { _n=$(grep -c "CPU Load" "$GAU" 2>/dev/null); echo "${_n:-0}"; }
LW0=$(loadwarn)
LOWERED=0
restore_commit() {
    [ $LOWERED -eq 1 ] || return
    sync
    if mount -u -o commit=high "$USB" >> "$LOG" 2>&1; then
        echo "stick back to commit=high" >> "$LOG"
    else
        say "could not put the stick back to commit=high -- pull it and plug it back in"
    fi
    LOWERED=0
}

if [ -n "$FC" ]; then
    if mount -u -o commit=low "$USB" >> "$LOG" 2>&1; then
        LOWERED=1; echo "stick remounted commit=low for the copy" >> "$LOG"
    fi
    say "copying $DEV to ${OUT##*/} (64 MB, 1 MB writes -- about a minute or two)"
    "$FC" "$DEV" "$OUT" 1024 0 > "$TMPD/.fb_fcopy" 2>&1 &
    CP=$!
else
    say "bin/fcopy not on the stick: copying with cp (slow, 30-40 minutes)"
    cp "$DEV" "$OUT" >> "$LOG" 2>&1 &
    CP=$!
fi
SLEEP=sleep; [ -x /proc/boot/sleep ] && SLEEP=/proc/boot/sleep
T=0
if [ -n "$FC" ]; then
    # Don't poll the stick during the fast copy: with 1 MB writes it is so busy
    # that even `ls` on it blocks for many seconds (on a 958.2 the bar sat at 4 %
    # for the whole minute). The splash creeps the bar on its own instead.
    prog "3-95/100 Copying flash (about a minute)"
    wait "$CP"
    RC=$?
    R=$(cat "$TMPD/.fb_fcopy" 2>/dev/null); rm -f "$TMPD/.fb_fcopy"
    echo "fcopy: $R" >> "$LOG"
    case "$R" in *stop=eof*) ;; *) RC=1 ;; esac   # anything but a clean end = failed
    T=${R##*secs=}; T=${T%% *}                    # fcopy's own timing
    case "$T" in ''|*[!0-9]*) T=0 ;; esac
else
    # cp takes 30-40 minutes: show real progress from the file size
    prog "3/100 Copying flash: starting"
    while kill -0 "$CP" 2>/dev/null; do
        $SLEEP 5; T=$((T + 5))
        S=$(fsize "$OUT")
        MB=$((S / 1048576))
        PCT=$((3 + S / 729444))              # 3..95 over 64 MB, no 32-bit overflow
        [ $PCT -gt 95 ] && PCT=95
        prog "$PCT/100 Copying flash: $MB of 64 MB"
        if [ $((T % 60)) -eq 0 ]; then       # a log line a minute: copy speed on this unit
            echo "  ${T}s: $S bytes ($((S / 1024 / T)) KB/s)" >> "$LOG"
        fi
    done
    wait "$CP"
    RC=$?
fi
restore_commit
echo "PCM load-monitor warnings: $LW0 before, $(loadwarn) after" >> "$LOG"

prog "96/100 Checking the copy"
SIZE=$(fsize "$OUT")
if [ "$RC" -ne 0 ] || [ "$SIZE" != "$FULL" ]; then
    say "FAILED: the copy returned $RC and is $SIZE bytes, not $FULL (stick full?) -- deleted the partial file"
    rm -f "$OUT"
    prog "100/100 Flash backup FAILED (see flash_backup.log)"
    rm -f "$LOCK"
    exit 1
fi
say "OK: ${OUT##*/} is $SIZE bytes in ${T}s. Check it on a computer: python explorer.py ${OUT##*/} check"
echo "PRIVACY: this file holds the unit's VIN, activations and coding -- don't post it." >> "$LOG"
prog "100/100 Flash backup complete"
rm -f "$LOCK"
exit 0
