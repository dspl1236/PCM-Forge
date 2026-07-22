#!/bin/sh
# ============================================================
# PCM-Forge  service-reset  ->  SERVICE INTERVAL TEST  (READ-ONLY / DRY-RUN)
# ------------------------------------------------------------
# Reads your VIN + odometer (km AND miles) from the car, shows past service
# history, and DRY-RUNS the oil/inspection reset: it logs the EXACT UDS frames
# it WOULD send but SENDS NOTHING. This payload ships NO uds_send binary, so it
# is physically incapable of touching the instrument cluster. Safe for anyone
# to run. It never modifies the car -- only writes a report to the USB stick.
#
# The real (armed) reset is a separate, Autel-confirmed step in tools/.
# github.com/dspl1236/PCM-Forge
# ============================================================
ARM=0                                 # HARD SAFETY: 0 = dry-run. Never raised in this file.
USB="${1:-/fs/usb0}"
case "$USB" in /fs/usb*) : ;; *) USB=/fs/usb0 ;; esac   # clamp: writes can only land on the USB mount
REPORT="$USB/service_test_report.txt"
SLOG="$USB/service_log.txt"
DB="/HBpersistence/logbook/LogBookSql.db"
VINF="/HBpersistence/vin"
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs

echo "==================================================" > "$REPORT"
echo " PCM-Forge  Service Interval TEST   (READ-ONLY)"    >> "$REPORT"
echo " Dry-run only -- nothing is sent to the cluster."   >> "$REPORT"
echo "==================================================" >> "$REPORT"
echo "" >> "$REPORT"

# ---------- VIN ----------
echo "-- Vehicle --" >> "$REPORT"
if [ -f "$VINF" ]; then
    VIN=$(cat "$VINF" 2>/dev/null)
    echo "  VIN: $VIN" >> "$REPORT"
else
    echo "  VIN: (not found at $VINF)" >> "$REPORT"
fi

# ---------- Odometer (logbook SQLite, 0.1 km steps) ----------
# km = raw/10 ; miles = raw/16.0934  (two-step integer math = 32-bit-overflow safe)
RAW=""
if [ -f "$DB" ]; then
    LB="$TMPD/forge_lb.db"
    cp "$DB" "$LB" 2>/dev/null         # query a COPY so we never lock the live DB
    for SQL in /mnt/data/tools/sqlite_console /mnt/data/tools/sqlite3 \
               /usr/bin/sqlite3 /HBbin/sqlite_console /proc/boot/sqlite3; do
        [ -x "$SQL" ] || continue
        V=$("$SQL" "$LB" "SELECT MAX(DestMileage) FROM trips;" < /dev/null 2>/dev/null | grep -oE "[0-9]+")
        case "$V" in ""|*[!0-9]*) : ;; *) RAW="$V"; echo "  (odometer read via ${SQL##*/})" >> "$REPORT"; break ;; esac
    done
    rm -f "$LB" 2>/dev/null
fi

if [ -n "$RAW" ]; then
    KM=$(( RAW / 10 ))
    TH=$(( KM / 1000 )); LO=$(( KM % 1000 ))
    MI=$(( TH * 62137 / 100 + LO * 62137 / 100000 ))
    echo "  Odometer: $KM km  /  $MI mi    (raw $RAW = 0.1 km units)" >> "$REPORT"
    ODO_MI="$MI"
else
    echo "  Odometer: UNAVAILABLE -- logbook DB or on-car sqlite tool not readable here." >> "$REPORT"
    echo "            (VIN + history below still valid; we pin the exact reader on-car.)" >> "$REPORT"
    ODO_MI="?"
fi
echo "" >> "$REPORT"

# ---------- Service history (seed sample rows the first time) ----------
if [ ! -f "$SLOG" ]; then
    echo "# PCM-Forge service log  --  SAMPLE rows (delete once you log real ones)" > "$SLOG"
    echo "2019-05-01   32000 mi   OIL          (sample)" >> "$SLOG"
    echo "2021-08-15   44500 mi   OIL          (sample)" >> "$SLOG"
    echo "2023-06-20   56000 mi   INSPECTION   (sample)" >> "$SLOG"
fi
echo "-- Past service ($SLOG) --" >> "$REPORT"
cat "$SLOG" >> "$REPORT" 2>/dev/null
echo "" >> "$REPORT"

# ---------- Dry-run of the reset (LOG ONLY -- never transmitted) ----------
echo "-- Reset that WOULD run (SIMULATED, NOT SENT) --" >> "$REPORT"
echo "  target: instrument cluster, UDS physical address 0x17" >> "$REPORT"
echo "  [1] DiagnosticSessionControl Extended     : 10 03" >> "$REPORT"
echo "  [2] Oil service reset   (IDE00342 0x0156) : 2E 01 56 00" >> "$REPORT"
echo "  [3] Inspection distance (IDE03351 0x0D17) : 2E 0D 17 00 00 00 00" >> "$REPORT"
echo "  [4] Inspection time     (IDE03352 0x0D18) : 2E 0D 18 00 00 00 00" >> "$REPORT"
echo "  ARM=$ARM -> DRY-RUN: no frames transmitted, and no uds_send binary is shipped." >> "$REPORT"
echo "" >> "$REPORT"

# ---------- Append a test marker to the service log ----------
echo "----------   $ODO_MI mi   TEST-DRYRUN   (no reset sent)" >> "$SLOG"

echo "-- Done. Open $REPORT on this stick. Nothing on the car was changed. --" >> "$REPORT"
