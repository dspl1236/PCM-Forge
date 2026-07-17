#!/bin/ksh
# PCM-Forge bt-aux-fix — remove the persistent boot hook (revert to stock).
# Run on the car over SSH:  ksh /fs/usb0/scripts/bt_hook_uninstall.sh
HP=/HBpersistence; DBG="$HP/debugTools.sh"; MARK="PCM-Forge bt_fix boot hook"
if [ -f "$DBG" ]; then
    awk -v m="$MARK" '
        index($0, ">>> " m " >>>") {skip=1; next}
        index($0, "<<< " m " <<<") {skip=0; next}
        skip!=1 {print}
    ' "$DBG" > "$DBG.tmp" && mv -f "$DBG.tmp" "$DBG" && chmod +x "$DBG"
    echo "stripped hook block from $DBG"
fi
rm -f "$HP/bt_boot.sh"
echo "removed $HP/bt_boot.sh (left $HP/bt_fix; delete manually if you want)"
echo "Live patch stays until reboot. Undo now:  $HP/bt_fix \$(pidin | grep PCM3Root | head -1 | awk '{print \$1}') --revert"
sync
