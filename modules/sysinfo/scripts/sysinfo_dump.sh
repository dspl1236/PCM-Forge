#!/bin/sh
# sysinfo_dump.sh — Complete PCM 3.1 system diagnostic
# Read-only, no changes to car. Dumps everything to USB.
#
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/sysinfo.log"
DUMPDIR="$USB/sysinfo_dump"
rm -rf "$DUMPDIR" 2>/dev/null; mkdir -p "$DUMPDIR" 2>/dev/null

echo "=== PCM-Forge System Info ===" > "$LOG"
# There is no date(1) on this shell, so stamp a file and read its mtime back --
# that is "now" by the unit's own clock. Without it every mtime in this report is
# uninterpretable, and telling "written this boot" from "written months ago" is
# the whole game for amp/persistence questions.
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
echo x > "$TMPD/.forge_now" 2>/dev/null
echo "Now (unit clock):" >> "$LOG"
ls -la "$TMPD/.forge_now" >> "$LOG" 2>&1
rm -f "$TMPD/.forge_now" 2>/dev/null
# Kernel release, CPU, free memory and BOOT TIME. Boot time vs now = uptime,
# which is how a reset loop shows itself.
echo "System:" >> "$LOG"
pidin info < /dev/null >> "$LOG" 2>&1
echo "Hardware variant marker:" >> "$LOG"
cat /etc/pcm31* >> "$LOG" 2>&1
ls -la /etc/pcm31* >> "$LOG" 2>&1
echo "" >> "$LOG"

# The system log is a RAM ring buffer that a reboot empties and that keeps
# rolling while we work. Grab it FIRST -- section 16 analyses the file. If this
# script dies partway, this is the artefact we would most regret losing.
sloginfo < /dev/null > "$DUMPDIR/sloginfo.txt" 2>&1
sloginfo -s 3 < /dev/null > "$DUMPDIR/sloginfo-errors.txt" 2>&1

# === 1. FIRMWARE VERSION ===
echo "--- 1. Firmware ---" >> "$LOG"
cat /mnt/ifs1/HBproject/version.txt >> "$LOG" 2>&1
cat /HBproject/version.txt >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 2. PROCESS LIST ===
echo "--- 2. Processes ---" >> "$LOG"
pidin ar >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 3. DISK SPACE ===
echo "--- 3. Disk Space ---" >> "$LOG"
df >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 4. DISPLAY STACK ===
echo "--- 4. Display Stack ---" >> "$LOG"
echo "  /dev/layermanager:" >> "$LOG"
ls -la /dev/layermanager >> "$LOG" 2>&1
echo "  Display config:" >> "$LOG"
cat /etc/system/config/display.conf >> "$LOG" 2>&1
echo "  Image codecs:" >> "$LOG"
cat /etc/system/config/img.conf >> "$LOG" 2>&1
for cfg in /etc/system/config/carmine*.conf; do
    [ -f "$cfg" ] && {
        echo "  === ${cfg##*/} ===" >> "$LOG"
        cat "$cfg" >> "$LOG" 2>&1
        cp "$cfg" "$DUMPDIR/" 2>/dev/null
    }
done
echo "" >> "$LOG"

# === 5. BOOT SCREENS ===
echo "--- 5. Boot Screens ---" >> "$LOG"
echo "  HDD (/mnt/share/bootscreens/):" >> "$LOG"
ls -la /mnt/share/bootscreens/ >> "$LOG" 2>&1
echo "  Active (/HBpersistence/):" >> "$LOG"
ls -la /HBpersistence/CustomBootscreen* >> "$LOG" 2>&1
echo "  IFS fallback:" >> "$LOG"
ls -la /proc/boot/PCM31_bootScreenPorscheLogo.jpg >> "$LOG" 2>&1
for bs in /HBpersistence/CustomBootscreen_*.bin; do
    [ -f "$bs" ] && cp "$bs" "$DUMPDIR/" 2>/dev/null
done
echo "" >> "$LOG"

# === 6. PERSISTENCE ===
echo "--- 6. Persistence ---" >> "$LOG"

# persdump2 usage
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2; do
    [ -x "$p" ] && PERSDUMP="$p" && break
done
if [ -n "$PERSDUMP" ]; then
    echo "  persdump2: $PERSDUMP" >> "$LOG"
    # < /dev/null so an unknown no-arg behavior can never block on the console-less autorun
    "$PERSDUMP" < /dev/null >> "$LOG" 2>&1
    # Verbose dump first CVALUE file
    for cv in /HBpersistence/CVALUE*.CVA; do
        if [ -f "$cv" ]; then
            echo "  Test: $PERSDUMP ${cv##*/} v" >> "$LOG"
            "$PERSDUMP" "$cv" v < /dev/null >> "$LOG" 2>&1
            break
        fi
    done
fi
echo "" >> "$LOG"

# Copy all CVALUE files
echo "  CVALUE files:" >> "$LOG"
COUNT=0
for f in /HBpersistence/CVALUE*.CVA; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/" 2>/dev/null && COUNT=$((COUNT + 1))
done
echo "  Copied $COUNT CVALUE files" >> "$LOG"
echo "" >> "$LOG"

# Full HBpersistence listing
echo "--- 7. /HBpersistence/ ---" >> "$LOG"
ls -laR /HBpersistence/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# Copy key persistence files
echo "--- 8. Persistence Files ---" >> "$LOG"
mkdir -p "$DUMPDIR/Early" "$DUMPDIR/Normal" 2>/dev/null
for f in /HBpersistence/EarlyPersistencyFiles/*; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/Early/" 2>/dev/null
done
for f in /HBpersistence/NormalPersistencyFiles/*; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/Normal/" 2>/dev/null
done
NE=$(ls "$DUMPDIR/Early/" 2>/dev/null | grep -c "^")
NN=$(ls "$DUMPDIR/Normal/" 2>/dev/null | grep -c "^")
echo "  Copied $NE Early + $NN Normal persistence files" >> "$LOG"
echo "" >> "$LOG"

# === 9. DEBUG TOOLS ===
# NB: the PCM autorun shell has NO awk/head/find on PATH, so the old
# `find /mnt ... | head -1` + `awk '{print $5}'` produced nothing. Scan the
# known tool dirs directly and print the `ls -la` line (already shows size).
echo "--- 9. Debug Tools ---" >> "$LOG"
for t in taco persdump2 showScreen mmecli mmexplore vi ping qdbc qconn sqlite_console find fdisk dinit hbhogs ipgrabber which cksum; do
    for d in /mnt/data/tools /mnt/ifs1/HBbin /HBbin /usr/sbin /usr/bin /proc/boot /HBpersistence/QNXTools; do
        [ -f "$d/$t" ] && ls -la "$d/$t" >> "$LOG" 2>&1
    done
done
echo "" >> "$LOG"

# === 10. NETWORK ===
echo "--- 10. Network ---" >> "$LOG"
ifconfig -a >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [interface counters -- Ierrs/Oerrs/Coll reveal a bad link]" >> "$LOG"
netstat -in >> "$LOG" 2>&1
echo "  [routes]" >> "$LOG"
netstat -rn >> "$LOG" 2>&1
echo "" >> "$LOG"
cat /etc/inetd.conf >> "$LOG" 2>&1
echo "" >> "$LOG"
cat /etc/hosts >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 11. VIN & ACTIVATION ===
echo "--- 11. VIN & Activation ---" >> "$LOG"
echo "  VIN:" >> "$LOG"
cat /HBpersistence/vin >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  PagSWAct.002 (activation records, 28 bytes each):" >> "$LOG"
ls -la /HBpersistence/PagSWAct.002 >> "$LOG" 2>&1
# The 16-char activation codes are plain hex text inside the record table, so
# grep alone recovers them -- no decoder needed on-car.
echo "  [unlock codes present]:" >> "$LOG"
grep -aoE "[0-9a-f]{16}" /HBpersistence/PagSWAct.002 >> "$LOG" 2>&1
echo "  [other activation artefacts]:" >> "$LOG"
ls -la /HBpersistence/PagSWAct* /HBpersistence/diskid.txt /HBpersistence/CsiConfig1.csi /HBpersistence/PDL.dat >> "$LOG" 2>&1
for f in /HBpersistence/PagSWAct.csv /HBpersistence/diskid.txt; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/" 2>/dev/null
done
echo "  DBGModeActive:" >> "$LOG"
ls -la /HBpersistence/DBGModeActive >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 12. HYBRID DATA ===
echo "--- 12. hybrid.bin ---" >> "$LOG"
[ -f "/HBpersistence/hybrid.bin" ] && {
    ls -la /HBpersistence/hybrid.bin >> "$LOG" 2>&1
    cp /HBpersistence/hybrid.bin "$DUMPDIR/" 2>/dev/null
}
echo "" >> "$LOG"

# === 13. BT/AUX FIX STATE + AUDIO SOURCE (support diagnosis) ===
echo "--- 13. BT/AUX Fix State + Audio Source ---" >> "$LOG"
echo "  [boot hook] /HBpersistence/debugTools.sh" >> "$LOG"
echo "  A 'PCM-Forge bt_fix' block below = the patch RE-APPLIES every boot" >> "$LOG"
echo "  (Revert did not fully take -- this alone explains a stuck AUX/no-BT):" >> "$LOG"
echo "  .................................................................." >> "$LOG"
cat /HBpersistence/debugTools.sh >> "$LOG" 2>&1
echo "  .................................................................." >> "$LOG"
echo "  [fix files] should ALL be absent after a clean Revert:" >> "$LOG"
ls -la /HBpersistence/bt_boot.sh /HBpersistence/bt_fix /HBpersistence/bt_boot.log >> "$LOG" 2>&1
[ -f /HBpersistence/debugTools.sh ] && cp /HBpersistence/debugTools.sh "$DUMPDIR/" 2>/dev/null
[ -f /HBpersistence/bt_boot.log ]  && cp /HBpersistence/bt_boot.log  "$DUMPDIR/" 2>/dev/null
echo "" >> "$LOG"
echo "  [audio / source / bluetooth persistence]:" >> "$LOG"
ls -la /HBpersistence/*ource* /HBpersistence/*udio* /HBpersistence/*luetooth* /HBpersistence/*Mode* /HBpersistence/*edia* /HBpersistence/*uner* >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [SOURCE-PERSISTENCE blobs -- the suspected STALE last-source root cause a Revert does NOT touch]:" >> "$LOG"
ls -la /HBpersistence/NormalPersistencyFiles/*SoundPresCtrl* /HBpersistence/NormalPersistencyFiles/*MediaPresCtrl* /HBpersistence/NormalPersistencyFiles/*AuxIn* /HBpersistence/NormalPersistencyFiles/*Tuner* >> "$LOG" 2>&1
echo "  [any lingering PCM-Forge / bt-fix artifact by name (catches earlier-version filenames too)]:" >> "$LOG"
ls -la /HBpersistence/*bt_* /HBpersistence/*fix* /HBpersistence/*orge* >> "$LOG" 2>&1
echo "  (full Normal/EarlyPersistencyFiles copied to sysinfo_dump/ for offline decode of last-source + pairing state)" >> "$LOG"
echo "" >> "$LOG"

# === 14. HARDWARE / IPC / CAN / DSI PROBE ===
# (folded in from the standalone "Enhanced Diagnostic + CAN Probe" so sysinfo is
#  the single comprehensive diag. The /dev/ipc, /dev/dsi, /dev/name and /srv
#  nodes below are what the SPHKeyInput / SPHSound DSI work maps against.)
echo "--- 14. Hardware / IPC / CAN / DSI Probe ---" >> "$LOG"
echo "" >> "$LOG"
echo "  [mount points]" >> "$LOG"
mount >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/dev/ipc/  (IOC / CAN channels)]" >> "$LOG"
ls -laR /dev/ipc/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/dev/dspipc/]" >> "$LOG"
ls -laR /dev/dspipc/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/dev/dsi/  (DSI service bus)]" >> "$LOG"
ls -laR /dev/dsi/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/dev/name/  (registered service names)]" >> "$LOG"
ls -laR /dev/name/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/srv/  (service broker)]" >> "$LOG"
ls -la /srv/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [full /dev listing]" >> "$LOG"
ls /dev/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [device nodes: ser/can/spi/i2c/hd/fs]" >> "$LOG"
ls /dev/ser* /dev/can* /dev/spi* /dev/i2c* /dev/hd* /dev/fs* >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [sysregs / FPGA -- VALUES, not just node names. These are the audio muxes," >> "$LOG"
echo "   amp enables and reset lines; the driver returns each field as 0x%04X.]" >> "$LOG"
ls -la /dev/sysregs/ >> "$LOG" 2>&1
for r in $(ls /dev/sysregs/ 2>/dev/null); do
    echo "    $r = $(cat /dev/sysregs/$r 2>/dev/null)" >> "$LOG"
done
echo "" >> "$LOG"
echo "  [MOST]" >> "$LOG"
ls -la /dev/most* >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [io-display / pv]" >> "$LOG"
ls -la /dev/io-display/ /dev/pv/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [flash / HDD partitions]" >> "$LOG"
ls -la /dev/fs0* /dev/hd0* >> "$LOG" 2>&1
echo "" >> "$LOG"

# --- STORAGE MAP (read-only) --------------------------------------------
# The full picture of every block device and its partition table. This is what
# a drive upgrade has to be designed against: which partition holds the jukebox,
# how big each one is, and how much slack exists. Everything here is a query --
# nothing is written to any disk.
echo "  [storage: all block devices]" >> "$LOG"
ls -la /dev/hd* /dev/fs* >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [storage: external / USB-attached (umass)]" >> "$LOG"
ls -laR /dev/umass* >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [storage: free space]" >> "$LOG"
df -k >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [storage: partition tables -- read-only fdisk queries]" >> "$LOG"
FDISK=""
for c in /tools/fdisk /mnt/data/tools/fdisk /mnt/ifs1/tools/fdisk; do
    [ -x "$c" ] && FDISK="$c" && break
done
if [ -n "$FDISK" ]; then
    echo "    using $FDISK" >> "$LOG"
    for dev in /dev/hd0 /dev/hd1 /dev/hd2 /dev/umass0 /dev/umass1; do
        [ -e "$dev" ] || continue
        echo "    --- $dev ---" >> "$LOG"
        echo "    total cylinders:" >> "$LOG"
        "$FDISK" "$dev" query -T < /dev/null >> "$LOG" 2>&1
        echo "    geometry (heads / sectors-per-track):" >> "$LOG"
        "$FDISK" "$dev" info < /dev/null >> "$LOG" 2>&1
        echo "    partition table:" >> "$LOG"
        "$FDISK" "$dev" show < /dev/null >> "$LOG" 2>&1
    done
else
    echo "    (fdisk not found; partition tables unavailable)" >> "$LOG"
fi
echo "" >> "$LOG"
# Drive model/serial as the EIDE driver saw it at boot. Capacity in sectors is
# cylinders x heads x sectors-per-track from the fdisk output above.
echo "  [storage: drive identity from the EIDE driver]" >> "$LOG"
sloginfo 2>/dev/null | grep -iE "eide_display_devices|eide_init_devices|devb-eide|MK[0-9]|SSD|ATA" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [/hbsystem/]" >> "$LOG"
ls -laR /hbsystem/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [IFS/EFS mount paths]" >> "$LOG"
ls -d /mnt/ifs1/ /mnt/flash/ /mnt/efs-system/ /mnt/efs-extended/ /mnt/data/ /mnt/share/ /mnt/nav/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [engineering ESD / engdefs]" >> "$LOG"
ls /mnt/flash/efs1/engdefs/ /HBpersistence/engdefs/ /mnt/ifs1/engdefs/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [FSC files]" >> "$LOG"
ls -la /HBpersistence/FSC/ /mnt/efs-persist/FSC/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [screensaver.conf]" >> "$LOG"
cat /HBpersistence/screensaver.conf >> "$LOG" 2>&1
[ -f /HBpersistence/screensaver.conf ] && cp /HBpersistence/screensaver.conf "$DUMPDIR/" 2>/dev/null
echo "" >> "$LOG"
echo "  [test.html / test1.html]" >> "$LOG"
cat /HBpersistence/test.html  >> "$LOG" 2>&1
cat /HBpersistence/test1.html >> "$LOG" 2>&1
[ -f /HBpersistence/test.html ]  && cp /HBpersistence/test.html  "$DUMPDIR/" 2>/dev/null
[ -f /HBpersistence/test1.html ] && cp /HBpersistence/test1.html "$DUMPDIR/" 2>/dev/null
echo "" >> "$LOG"
echo "  [vin + PagSWAct.002 copied to dump]" >> "$LOG"
cp /HBpersistence/vin "$DUMPDIR/vin" 2>/dev/null
[ -f /HBpersistence/PagSWAct.002 ] && cp /HBpersistence/PagSWAct.002 "$DUMPDIR/PagSWAct.002.bak" 2>/dev/null
echo "" >> "$LOG"

# === 16. SYSTEM LOG (sloginfo) ===
# The single richest diagnostic on the unit: the whole boot sequence, every
# service that started or failed, amplifier detection, watchdog events. It is
# RAM-resident and cleared on every reboot, so this is the only chance to keep
# it. Saved whole as its own file, with the highlights inlined here.
echo "--- 16. System log ---" >> "$LOG"
# sloginfo reads a RAM ring buffer that keeps rolling, so capture it ONCE to a
# file and grep that file. Reading the ring repeatedly gives views of different
# instants, and a reboot mid-script would empty it between reads.
SLOG="$DUMPDIR/sloginfo.txt"
echo "  full log -> sysinfo_dump/sloginfo.txt ($(grep -c '^' "$SLOG" 2>/dev/null) lines)" >> "$LOG"
echo "  severity-filtered (the system's own rating, not our keyword guess) ->" >> "$LOG"
echo "    sysinfo_dump/sloginfo-errors.txt ($(grep -c '^' "$DUMPDIR/sloginfo-errors.txt" 2>/dev/null) lines)" >> "$LOG"
echo "" >> "$LOG"
echo "  [boot sequence: packages, processes, terminations]" >> "$LOG"
grep -E "Package ?\[|Process ?\[|PSState|startProcess|terminated|restarted|Shut down System|POST_STARTING" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [boot gates: interfaces the starter waits on -- a MISSING one names the hang]" >> "$LOG"
grep -E "Interface \[|AVAIL|waitfor" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [errors / warnings / watchdog / resets]" >> "$LOG"
grep -iE "error|fail|watchdog|reset|abnormal|corrupt|denied|timeout|panic|assert" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [amplifier detection + audio routing]" >> "$LOG"
echo "   NOTE: no matches here is itself a result -- it means no detection ran this" >> "$LOG"
echo "   boot and the existing audioAmp* flag was simply honored." >> "$LOG"
grep -iE "amptype|amplifier|MOSTDevice|storeAmp|setExtAmp|copyConfig|Burmest|SGTLAM|SoundPres|audio connection" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [hardware enumeration: drives, USB, FPGA, tuner, GPS, MOST]" >> "$LOG"
grep -iE "eide_|devb-|hbfpga|FPGA|io-usb|umass|tuner|flexgps|MOST|mops|hddmounter|MOUNT" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [vehicle identity as the software saw it]" >> "$LOG"
grep -iE "VIN|HardwareType|serial|variant|voltage|NavDB|language|metric" "$SLOG" >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 16b. CRASH RECORD ===
# The SOP starter runs two `dumper` instances -- one to /mnt/data/log and an
# early-boot one to /HBpersistence (before the HDD mounts) -- plus libbacktrace
# and libmalloc text dumps. Empty on a healthy unit; when not, this is the answer.
echo "--- 16b. Crash record ---" >> "$LOG"
mkdir -p "$DUMPDIR/crash" 2>/dev/null
echo "  [is the dumper attached? if /proc/dumper is absent no core is EVER written," >> "$LOG"
echo "   and an empty dump directory below proves nothing]" >> "$LOG"
ls -la /proc/dumper >> "$LOG" 2>&1
for d in /mnt/data/log /HBpersistence /dev/shmem; do
    echo "  [$d]" >> "$LOG"
    ls -la "$d" 2>/dev/null | grep -iE "core|dump|backtrace|malloc|watchdog" >> "$LOG" 2>&1
done
# Copy the small text artefacts only; raw .core files can be hundreds of KB each.
for f in /mnt/data/log/*backtrace* /mnt/data/log/*malloc* /mnt/data/log/*.txt \
         /HBpersistence/*backtrace* /HBpersistence/*malloc*; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/crash/" 2>/dev/null
done
echo "  (text artefacts -> sysinfo_dump/crash/; raw cores listed, not copied)" >> "$LOG"
echo "" >> "$LOG"

# === 17. AUDIO / AMPLIFIER STATE ===
# Which amplifier profile the unit resolved to, and the files that decide it.
# Checksums rather than contents: the mixer files are several KB each and only
# their identity matters for comparing one car against another.
echo "--- 17. Audio / amplifier ---" >> "$LOG"
CKSUM=""
for c in /HBpersistence/QNXTools/cksum /mnt/data/tools/cksum /usr/bin/cksum; do
    [ -x "$c" ] && CKSUM="$c" && break
done
echo "  [amp type flag -- existence IS the setting]" >> "$LOG"
ls -la /HBpersistence/audioAmp* >> "$LOG" 2>&1
echo "  [active + per-type mixer files]" >> "$LOG"
ls -la /HBpersistence/audiomixer*.txt >> "$LOG" 2>&1
if [ -n "$CKSUM" ]; then
    echo "  [checksums -- active file should match one of the per-type files]" >> "$LOG"
    "$CKSUM" /HBpersistence/audiomixer.txt /HBpersistence/audiomixer-ann-levels.txt \
             /HBpersistence/audiomixer_*.txt /HBpersistence/audiomixer-ann-levels_*.txt >> "$LOG" 2>&1
fi
# The decisive question for the amp feature: the flag file says one thing, the
# ACTIVE mixer content says another. cmp tells us which per-type profile the live
# file was actually copied from -- and whether a per-type SOURCE has been swapped.
echo "  [RESOLUTION: which profile is really live]" >> "$LOG"
FLAG="(none)"
for t in BOSE BURMESTER ASK; do
    [ -e "/HBpersistence/audioAmp$t" ] && FLAG="$t"
done
echo "    flag file says      : $FLAG" >> "$LOG"
MATCH="(matches no per-type file -- content has been modified)"
for t in BOSE BURMESTER ASK; do
    if cmp -s /HBpersistence/audiomixer.txt "/HBpersistence/audiomixer_$t.txt" 2>/dev/null; then
        MATCH="$t"
    fi
done
echo "    active mixer matches: $MATCH" >> "$LOG"
if [ "$FLAG" != "$MATCH" ]; then
    echo "    *** MISMATCH: the flag and the live audio profile disagree." >> "$LOG"
    echo "        Either a per-type source file was overwritten, or the flag was" >> "$LOG"
    echo "        changed without the mixer being re-copied." >> "$LOG"
fi
echo "    [are the per-type sources still distinct from each other?]" >> "$LOG"
if cmp -s /HBpersistence/audiomixer_BOSE.txt /HBpersistence/audiomixer_BURMESTER.txt 2>/dev/null; then
    echo "    NOTE: audiomixer_BOSE.txt and audiomixer_BURMESTER.txt are IDENTICAL" >> "$LOG"
    echo "          -- one has been overwritten with the other's content." >> "$LOG"
else
    echo "    BOSE and BURMESTER sources differ (stock)." >> "$LOG"
fi
echo "" >> "$LOG"
echo "  [sss DSP config -- the addon symlink encodes the selected profile]" >> "$LOG"
ls -la /HBpersistence/sss/ >> "$LOG" 2>&1
ls -la /HBpersistence/sss/config/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 18. VEHICLE DATA (odometer / logbook) ===
# Odometer lives in the driver's-logbook database in 0.1 km units.
# Queried on a COPY so the live database is never locked or touched.
echo "--- 18. Vehicle data ---" >> "$LOG"
LB=/HBpersistence/logbook/LogBookSql.db
ls -la /HBpersistence/logbook/ >> "$LOG" 2>&1
if [ -f "$LB" ]; then
    TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs
    cp "$LB" "$TMPD/lb_ro.db" 2>/dev/null
    SQL=""
    for c in /mnt/data/tools/sqlite_console /tools/sqlite_console /usr/bin/sqlite3; do
        [ -x "$c" ] && SQL="$c" && break
    done
    if [ -n "$SQL" ]; then
        echo "  [odometer -- raw value is 0.1 km units; miles = raw / 16.0934]" >> "$LOG"
        "$SQL" "$TMPD/lb_ro.db" "SELECT MAX(DestMileage) FROM trips;" < /dev/null >> "$LOG" 2>&1
        echo "  [trip count]" >> "$LOG"
        "$SQL" "$TMPD/lb_ro.db" "SELECT count(*) FROM trips;" < /dev/null >> "$LOG" 2>&1
    else
        echo "  (no sqlite tool found; LogBookSql.db is in the backup for offline reading)" >> "$LOG"
    fi
    rm -f "$TMPD/lb_ro.db" 2>/dev/null
fi
echo "" >> "$LOG"

# === 19. SERVICE MANAGER + LISTENING PORTS ===
echo "--- 19. Service manager / open ports ---" >> "$LOG"
echo "  [SOP process manager]" >> "$LOG"
ls -la /dev/starter/ >> "$LOG" 2>&1
cat /dev/starter/version /dev/starter/variant /dev/starter/packages /dev/starter/status >> "$LOG" 2>&1
echo "  NOTE: /dev/starter/start is a CONTROL node -- writing to it stops/starts" >> "$LOG"
echo "        packages. This script only ever reads." >> "$LOG"
echo "" >> "$LOG"
echo "  [listening sockets -- qconn 8000, MonitorService 2021, telnet 23, ksh 2323]" >> "$LOG"
netstat -an >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 20. SOFTWARE IDENTITY / UPDATE HISTORY ===
# /UpdateHistory is a flash partition holding the unit's reflash record: which
# software and nav packages were written, when, and with what result. version.txt
# says what it runs now; this says how it got there.
echo "--- 20. Software identity / update history ---" >> "$LOG"
echo "  [/UpdateHistory]" >> "$LOG"
ls -laR /UpdateHistory/ >> "$LOG" 2>&1
for f in /UpdateHistory/release.cfg /UpdateHistory/upd_filename /UpdateHistory/upd_hwids /UpdateHistory/versioninfolist; do
    [ -f "$f" ] && { echo "  --- ${f##*/} ---" >> "$LOG"; cat "$f" >> "$LOG" 2>&1; cp "$f" "$DUMPDIR/" 2>/dev/null; }
done
echo "" >> "$LOG"
echo "  [nav / speech / media package identity]" >> "$LOG"
cat /mnt/nav/MasterHDD.info >> "$LOG" 2>&1
cat /HBdata/sss-version.txt >> "$LOG" 2>&1
cat /mnt/ifs_app/etc/mme.version >> "$LOG" 2>&1
ls /mnt/nav/pkgdb/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [IFS / boot image inventory -- stock builds share one timestamp;" >> "$LOG"
echo "   an odd date or size is the cheap 80% of an integrity check]" >> "$LOG"
ls -la /proc/boot/ >> "$LOG" 2>&1
ls -la /mnt/ifs1/HBproject/ /mnt/ifs_app/HBproject/ >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "  [stray executables in writable areas -- where third-party mods land]" >> "$LOG"
ls -la /HBpersistence/ /HBpersistence/QNXTools/ /tools/ /mnt/data/tools/ >> "$LOG" 2>&1
echo "" >> "$LOG"

# === 21. PERSONAL DATA IN THIS DUMP ===
# Say plainly what leaves the car, so the owner can decide what to share.
echo "--- 21. Personal data notice ---" >> "$LOG"
echo "  This dump contains personal information. Before sharing it publicly:" >> "$LOG"
echo "    - vin                          your VIN" >> "$LOG"
echo "    - PagSWAct.002 / .csv          activation codes tied to your VIN" >> "$LOG"
echo "    - logbook/LogBookSql.db        trips: streets, towns, GPS, odometer" >> "$LOG"
echo "    - Normal/*NavAppCtrl*          saved destinations and last routes" >> "$LOG"
echo "    - Normal/*CommunicationPres*   paired phones and call history" >> "$LOG"
echo "    - Normal/*PHTelephone*         phonebook data" >> "$LOG"
echo "    - sysinfo.log itself           contains the VIN (above)" >> "$LOG"
echo "  For support, sysinfo.log alone is usually enough -- redact the VIN line." >> "$LOG"
echo "" >> "$LOG"

# === 15. FULL /HBpersistence BACKUP (recovery snapshot) ===
# Complete, restorable copy of /HBpersistence so the owner can roll back ANY
# change (amp/audio config, CVALUE coding, BT pairings, nav, VIN, flags). It
# lives on YOUR stick only -- nothing is uploaded. It DOES contain personal data
# (nav destinations, phone pairings, VIN) -- and so does sysinfo.log -- so keep
# BOTH private and redact the VIN before sharing for support. No tar/gzip/sync on
# the unit, so this is a plain recursive copy (~4MB; fine even on a tiny stick).
echo "--- 15. Full /HBpersistence backup ---" >> "$LOG"
BK="$USB/HBpersistence_backup"
rm -rf "$BK" 2>/dev/null
# FAT can't store symlinks -> cp -R exits non-zero but STILL copies the target
# files; capture the warnings instead of treating them as a failure. (Redirect
# to a temp on $USB first because $BK does not exist until cp creates it.)
cp -R /HBpersistence "$BK" 2>"$USB/hbpers_cp_warn.txt"
mv "$USB/hbpers_cp_warn.txt" "$BK/_cp_warnings.txt" 2>/dev/null
# list every symlink + target FAT dropped (the targets themselves ARE copied)
ls -laR /HBpersistence 2>/dev/null | grep " -> " > "$BK/_SYMLINKS.txt" 2>/dev/null
# cp -R aborts the sss/ subtree on FAT (its symlinks can't be created there) and
# drops sss/config with it -- copy that DSP-config dir explicitly so the backup is
# complete and the regular-file count below does not false-trip "INCOMPLETE".
if [ -d /HBpersistence/sss/config ]; then
    mkdir -p "$BK/sss" 2>/dev/null
    cp -R /HBpersistence/sss/config "$BK/sss/config" 2>>"$BK/_cp_warnings.txt"
fi
# REAL truncation check: count REGULAR files only (grep "^-" ignores dir headers,
# blank lines, symlinks and FAT cluster inflation). On success DST = SRC + the two
# report files written above; DST < SRC means cp ran out of space mid-copy.
SRC=$(ls -laR /HBpersistence 2>/dev/null | grep -c "^-")
DST=$(ls -laR "$BK" 2>/dev/null | grep -c "^-")
echo "  /HBpersistence -> $BK" >> "$LOG"
if [ "$DST" -lt "$SRC" ] 2>/dev/null; then
    echo "  *** BACKUP INCOMPLETE: only $DST of ~$SRC files copied -- USB likely FULL. ***" >> "$LOG"
    cat "$BK/_cp_warnings.txt" >> "$LOG" 2>&1
    echo "  *** removing partial backup so it is not mistaken for a good one. ***" >> "$LOG"
    rm -rf "$BK" 2>/dev/null; BK=""
else
    echo "  backup OK: $DST files (source $SRC + 2 report files)." >> "$LOG"
    echo "  dropped symlinks recorded in $BK/_SYMLINKS.txt (targets ARE in the backup)" >> "$LOG"
fi
echo "  PRIVACY: this backup AND sysinfo.log both hold your VIN + a full persistence" >> "$LOG"
echo "           listing -- keep them private; redact the VIN before sharing." >> "$LOG"
echo "" >> "$LOG"

# === 22. DRIVE HEALTH ===
# A failing 2.5" drive is the most common hardware fault on these units, and the
# reason most people end up replacing one. Best-effort: the tool is not on every
# build.
echo "--- 22. Drive health ---" >> "$LOG"
SMART=""
for c in /tools/readsmart /mnt/data/tools/readsmart /usr/sbin/readsmart /proc/boot/readsmart; do
    [ -x "$c" ] && SMART="$c" && break
done
if [ -n "$SMART" ]; then
    for dev in /dev/hd0 /dev/hd1; do
        [ -e "$dev" ] && { echo "  --- $dev ---" >> "$LOG"; "$SMART" "$dev" < /dev/null >> "$LOG" 2>&1; }
    done
else
    echo "  (no readsmart on this build; drive model/geometry is in section 14)" >> "$LOG"
fi
ls -la /HBpersistence/HBProdSMARTData*.txt >> "$LOG" 2>&1
for f in /HBpersistence/HBProdSMARTData*.txt; do
    [ -f "$f" ] && cp "$f" "$DUMPDIR/" 2>/dev/null
done
echo "" >> "$LOG"

echo "=== System Info complete ===" >> "$LOG"
ls -la "$DUMPDIR"/ >> "$LOG" 2>&1
[ -n "$BK" ] && echo "  (full recovery backup: $USB/HBpersistence_backup/)" >> "$LOG"

# A run that stops early still leaves a plausible-looking log, so mark the end.
# If this line is missing the report is TRUNCATED and must not be read as complete.
echo "" >> "$LOG"
echo "=== END OF REPORT -- if you do not see this line, the run was cut short ===" >> "$LOG"
