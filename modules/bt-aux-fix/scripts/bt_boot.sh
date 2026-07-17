#!/bin/ksh
# PCM-Forge bt-aux-fix BOOT HOOK (persist mode). Installed to /HBpersistence and
# launched from debugTools.sh at each boot. Waits for PCM3Root, then re-applies the
# fail-safe FM->A2DP patch to its live memory. Reboot-reverts; never touches flash.
HP=/HBpersistence
LOG="$HP/bt_boot.log"
echo "== bt_boot $(date 2>/dev/null || echo nodate) ==" >> "$LOG"
n=0; PID=""
while [ $n -lt 40 ]; do
    PID=$(pidin 2>/dev/null | grep PCM3Root | head -1 | awk '{print $1}')
    [ -n "$PID" ] && break
    sleep 1; n=$((n+1))
done
[ -z "$PID" ] && { echo "PCM3Root not found after ${n}s" >> "$LOG"; exit 0; }
echo "PCM3Root pid=$PID (up after ${n}s)" >> "$LOG"
"$HP/bt_fix" "$PID" --apply >> "$LOG" 2>&1
sleep 3; "$HP/bt_fix" "$PID" --apply >> "$LOG" 2>&1
sleep 5; "$HP/bt_fix" "$PID" --apply >> "$LOG" 2>&1
echo "-- bt_boot done --" >> "$LOG"
