#!/bin/ksh
# ============================================================
# PCM-Forge  bt-aux-fix  —  universal FM->A2DP boot fix
# ------------------------------------------------------------
# Args (from the toolkit run.sh):  $1 = USBROOT   $2 = mode (runtime|persist|revert)
#
# Finds the FM source-map instruction in the LIVE PCM3Root by a unique
# signature (version/region/model independent) and flips the FM index (01)
# to A2DP (07). Fail-safe: bt_fix only writes on exactly one signature match
# with the byte currently 0x01. Runtime = live patch (reboot reverts).
# Persist = also drop a /HBpersistence boot hook that re-applies each boot.
# Never modifies the read-only firmware.  github.com/dspl1236/PCM-Forge
# ============================================================
USBROOT="$1"; [ -z "$USBROOT" ] && USBROOT="/fs/usb0"
MODE="${2:-runtime}"
LOG="${USBROOT}/bt_fix.txt"
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs

echo "== PCM-Forge bt-aux-fix ($MODE) -- $(date 2>/dev/null || echo nodate) ==" > "$LOG"

# locate bt_fix (builder flattens bin files to bin/)
BF=""
for c in "${USBROOT}/bin/bt_fix" "${USBROOT}/bt_fix" "${USBROOT}/scripts/bt_fix"; do
    [ -f "$c" ] && BF="$c" && break
done
[ -z "$BF" ] && { echo "[ERR] bt_fix binary not found on USB" >> "$LOG"; exit 1; }

find_pid() { pidin 2>/dev/null | grep PCM3Root | head -1 | awk '{print $1}'; }

if [ "$MODE" = "persist" ]; then
    HP=/HBpersistence; DBG="$HP/debugTools.sh"; MARK="PCM-Forge bt_fix boot hook"
    cp "$BF" "$HP/bt_fix" && chmod +x "$HP/bt_fix"
    for c in "${USBROOT}/scripts/bt_boot.sh" "${USBROOT}/bt_boot.sh"; do
        [ -f "$c" ] && cp "$c" "$HP/bt_boot.sh" && chmod +x "$HP/bt_boot.sh" && break
    done
    [ -f "$DBG" ] || { echo "#!/bin/ksh" > "$DBG"; chmod +x "$DBG"; }
    if grep -q "$MARK" "$DBG" 2>/dev/null; then
        echo "[OK] boot hook already present in $DBG" >> "$LOG"
    else
        echo "" >> "$DBG"
        echo "# >>> $MARK >>>" >> "$DBG"
        echo "[ -x $HP/bt_boot.sh ] && $HP/bt_boot.sh &" >> "$DBG"
        echo "# <<< $MARK <<<" >> "$DBG"
        echo "[OK] installed boot hook -> $DBG (re-applies every boot)" >> "$LOG"
    fi
    # apply once now so it takes effect without waiting for a reboot
    PID=$(find_pid)
    if [ -n "$PID" ]; then echo "[..] applying now to pid=$PID" >> "$LOG"; "$HP/bt_fix" "$PID" --apply >> "$LOG" 2>&1
    else echo "[..] PCM3Root not up yet; hook will apply on next boot" >> "$LOG"; fi
    echo "[i] to undo later: run this module again in 'revert' mode" >> "$LOG"
elif [ "$MODE" = "revert" ]; then
    # ---- full revert to stock: strip hook, remove staged files, undo live patch ----
    HP=/HBpersistence; DBG="$HP/debugTools.sh"; MARK="PCM-Forge bt_fix boot hook"
    if [ -f "$DBG" ]; then
        awk -v m="$MARK" 'index($0, ">>> " m " >>>"){skip=1;next} index($0, "<<< " m " <<<"){skip=0;next} skip!=1{print}' "$DBG" > "$DBG.tmp" \
            && mv -f "$DBG.tmp" "$DBG" && chmod +x "$DBG" \
            && echo "[OK] stripped boot hook from $DBG" >> "$LOG"
    else
        echo "[i] $DBG not present (nothing to strip)" >> "$LOG"
    fi
    rm -f "$HP/bt_boot.sh" "$HP/bt_boot.log" "$HP/bt_fix"
    echo "[OK] removed $HP/bt_boot.sh + $HP/bt_fix (persistence gone)" >> "$LOG"
    # undo the live patch now (07 -> 01) so this session is stock immediately
    cp "$BF" "$TMPD/bt_fix" && chmod +x "$TMPD/bt_fix"
    PID=$(find_pid)
    if [ -n "$PID" ]; then
        echo "[..] reverting live PCM3Root pid=$PID (07 -> 01)" >> "$LOG"
        "$TMPD/bt_fix" "$PID" --revert >> "$LOG" 2>&1
    else
        echo "[i] PCM3Root not up; live memory reverts on reboot anyway" >> "$LOG"
    fi
    echo "[OK] REVERTED TO STOCK -- fix removed, will not apply at boot" >> "$LOG"
else
    cp "$BF" "$TMPD/bt_fix" && chmod +x "$TMPD/bt_fix"
    PID=$(find_pid)
    if [ -n "$PID" ]; then
        echo "[..] PCM3Root pid=$PID -- applying (fail-safe)" >> "$LOG"
        "$TMPD/bt_fix" "$PID" --apply >> "$LOG" 2>&1
        echo "[i] reboot to undo, or re-run bt_fix with --revert" >> "$LOG"
    else
        echo "[ERR] PCM3Root not running" >> "$LOG"
    fi
fi
sync
echo "== bt-aux-fix done ($MODE) ==" >> "$LOG"
