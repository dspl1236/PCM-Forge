#!/bin/ksh
# flash_backup.sh -- copy the PCM 3.1's whole 64 MB NOR flash to the USB stick.
#
# READ-ONLY. It is the same read the PCM's own engineering menu does
# (System > CustomerService > 05 "Copy 64MB flash contents to USB", which runs
# "cp /dev/fs0 /fs/usb0/..."), without needing the menu or the ENGINEERING
# activation. Make one before any update or experiment; check it on a computer
# with PCM-Explorer:  python explorer.py pcm_flash.bin check
# See RECOVERY.md in PCM-Forge.
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

# never overwrite an earlier backup: pcm_flash.bin, then pcm_flash_2.bin ...
OUT="$USB/pcm_flash.bin"; N=2
while [ -e "$OUT" ] && [ $N -le 9 ]; do OUT="$USB/pcm_flash_$N.bin"; N=$((N + 1)); done
if [ -e "$OUT" ]; then
    say "FAILED: pcm_flash.bin .. pcm_flash_9.bin already on the stick -- move them off first"
    prog "100/100 Flash backup FAILED: stick already holds 9 backups"
    exit 1
fi

# the activation file and stored VIN next to it: small, and what you'd want first
cp /HBpersistence/PagSWAct.002 "${OUT%.bin}_PagSWAct.002" 2>/dev/null
cp /HBpersistence/vin "${OUT%.bin}_vin.txt" 2>/dev/null

say "copying $DEV to ${OUT##*/} (64 MB)"
prog "3-95/100 Copying 64 MB flash to USB"
cp "$DEV" "$OUT" >> "$LOG" 2>&1
RC=$?
sync

prog "96/100 Checking the copy"
SIZE=$(fsize "$OUT")
if [ "$RC" -ne 0 ] || [ "$SIZE" != "$FULL" ]; then
    say "FAILED: cp returned $RC and the copy is $SIZE bytes, not $FULL (stick full?) -- deleted the partial file"
    rm -f "$OUT"
    prog "100/100 Flash backup FAILED (see flash_backup.log)"
    exit 1
fi
say "OK: ${OUT##*/} is $SIZE bytes. Check it on a computer: python explorer.py ${OUT##*/} check"
echo "PRIVACY: this file holds the unit's VIN, activations and coding -- don't post it." >> "$LOG"
prog "100/100 Flash backup complete"
exit 0
