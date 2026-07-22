#!/bin/ksh
# PCM-Forge bt-aux-fix — remove the persistent boot hook (revert to stock).
# Run on the car over SSH:  ksh /fs/usb0/scripts/bt_hook_uninstall.sh
HP=/HBpersistence; DBG="$HP/debugTools.sh"; MARK="PCM-Forge bt_fix boot hook"
if [ -f "$DBG" ]; then
    # shell-safe strip -- the PCM ksh has NO awk/head, so the old awk version
    # silently failed and left the hook line in debugTools.sh.
    grep -v "$MARK" "$DBG" | grep -v 'bt_boot.sh' > "$DBG.tmp" \
        && cp "$DBG.tmp" "$DBG" && rm -f "$DBG.tmp" && chmod 777 "$DBG"
    echo "stripped hook block from $DBG"
fi
rm -f "$HP/bt_boot.sh"
echo "removed $HP/bt_boot.sh (left $HP/bt_fix; delete manually if you want)"
echo "Live patch (if it ever applied) clears on reboot. To undo now, find the pid via 'pidin | grep PCM3Root' then run:  $HP/bt_fix <pid> --revert"
sync
