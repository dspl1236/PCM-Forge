#!/bin/sh
# cluster_scan.sh — Scan all cluster per 3 addresses via CVALUE reads
# Reads actual persistence values and logs to USB
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

USB="/fs/usb0"
LOG="$USB/cluster_scan.log"

echo "=== PCM-Forge Cluster Address Scan ===" > "$LOG"
echo "Date: $(date 2>/dev/null || echo unknown)" >> "$LOG"
echo "" >> "$LOG"

# Dump ALL CVALUE files with persdump2
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2; do
    [ -x "$p" ] && PERSDUMP="$p" && break
done

echo "--- CVALUE Verbose Dump ---" >> "$LOG"
if [ -n "$PERSDUMP" ]; then
    for cv in /HBpersistence/CVALUE*.CVA; do
        if [ -f "$cv" ]; then
            echo "=== $(basename $cv) ===" >> "$LOG"
            "$PERSDUMP" "$cv" v >> "$LOG" 2>&1
            echo "" >> "$LOG"
        fi
    done
else
    echo "persdump2 not found, dumping raw hex" >> "$LOG"
    for cv in /HBpersistence/CVALUE*.CVA; do
        if [ -f "$cv" ]; then
            echo "=== $(basename $cv) ($(ls -la "$cv" | awk '{print $5}') bytes) ===" >> "$LOG"
            # Use cksum as fingerprint since od/xxd may not exist
            cksum "$cv" >> "$LOG" 2>&1
            echo "" >> "$LOG"
        fi
    done
fi

echo "" >> "$LOG"

# Dump ALL EarlyPersistencyFiles
echo "--- EarlyPersistencyFiles ---" >> "$LOG"
for f in /HBpersistence/EarlyPersistencyFiles/*; do
    if [ -f "$f" ]; then
        SIZE=$(ls -la "$f" | awk '{print $5}')
        NAME=$(basename "$f")
        echo "$NAME ($SIZE bytes)" >> "$LOG"
        cp "$f" "$USB/ioc_dump/" 2>/dev/null
    fi
done
echo "" >> "$LOG"

# Dump ALL NormalPersistencyFiles
echo "--- NormalPersistencyFiles ---" >> "$LOG"
for f in /HBpersistence/NormalPersistencyFiles/*; do
    if [ -f "$f" ]; then
        SIZE=$(ls -la "$f" | awk '{print $5}')
        NAME=$(basename "$f")
        echo "$NAME ($SIZE bytes)" >> "$LOG"
        cp "$f" "$USB/ioc_dump/" 2>/dev/null
    fi
done
echo "" >> "$LOG"

# Specifically grab CombiPresCtrl and PTripPresCtrl (cluster/trip data)
echo "--- Key Persistence Files (hex dump) ---" >> "$LOG"
for target in CombiPresCtrl PTripPresCtrl PSportChronoPresCtrl PLogBookPresCtrl DiagnosisPresCtrl FSCSysCtrl GlobalSettingsPresCtrl SwdlPresCtrl; do
    for f in /HBpersistence/EarlyPersistencyFiles/*${target}* /HBpersistence/NormalPersistencyFiles/*${target}*; do
        if [ -f "$f" ]; then
            echo "=== $(basename $f) ===" >> "$LOG"
            # Hex dump via cksum + raw byte analysis
            SIZE=$(ls -la "$f" | awk '{print $5}')
            echo "  Size: $SIZE bytes" >> "$LOG"
            echo "  Modified: $(ls -la "$f" | awk '{print $6, $7, $8}')" >> "$LOG"
            # Copy to USB for analysis
            cp "$f" "$USB/ioc_dump/" 2>/dev/null
            echo "  Copied to USB" >> "$LOG"
            echo "" >> "$LOG"
        fi
    done
done

# Check hybrid.bin (updated today — live vehicle data)
echo "--- hybrid.bin ---" >> "$LOG"
if [ -f "/HBpersistence/hybrid.bin" ]; then
    SIZE=$(ls -la /HBpersistence/hybrid.bin | awk '{print $5}')
    echo "  Size: $SIZE bytes" >> "$LOG"
    echo "  Modified: $(ls -la /HBpersistence/hybrid.bin | awk '{print $6, $7, $8}')" >> "$LOG"
    cp /HBpersistence/hybrid.bin "$USB/ioc_dump/" 2>/dev/null
    echo "  Copied to USB" >> "$LOG"
fi

# VIN
echo "" >> "$LOG"
echo "--- VIN ---" >> "$LOG"
cat /HBpersistence/vin >> "$LOG" 2>&1

# Check if taco exists (the Harman diagnostic tool)
echo "" >> "$LOG"
echo "--- taco (Harman diag tool) ---" >> "$LOG"
TACO=""
for t in /mnt/data/tools/taco /mnt/ifs1/HBbin/taco /HBbin/taco; do
    [ -x "$t" ] && TACO="$t" && break
done
if [ -n "$TACO" ]; then
    echo "  Found: $TACO" >> "$LOG"
    echo "  Usage:" >> "$LOG"
    "$TACO" >> "$LOG" 2>&1
    echo "" >> "$LOG"
    "$TACO" --help >> "$LOG" 2>&1
    echo "" >> "$LOG"
    "$TACO" -h >> "$LOG" 2>&1
else
    echo "  Not found" >> "$LOG"
fi

echo "" >> "$LOG"
echo "=== Scan complete ===" >> "$LOG"
