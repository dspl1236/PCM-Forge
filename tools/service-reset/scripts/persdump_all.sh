#!/bin/sh
# persdump_all.sh — Dump entire persistence address space to USB
# Uses persdump2 tool that ships on the PCM HDD
# Part of PCM-Forge: github.com/dspl1236/PCM-Forge

LOG="/fs/usb0/persdump_$(date +%H%M%S 2>/dev/null || echo scan).log"
USB="/fs/usb0"

echo "=== PCM-Forge Persistence Dump ===" > "$LOG"
echo "Date: $(date 2>/dev/null)" >> "$LOG"

# Find persdump2
PERSDUMP=""
for p in /mnt/data/tools/persdump2 /mnt/ifs1/HBbin/persdump2 /tmp/persdump2; do
    if [ -x "$p" ]; then
        PERSDUMP="$p"
        break
    fi
done

if [ -n "$PERSDUMP" ]; then
    echo "Using: $PERSDUMP" >> "$LOG"
    echo "" >> "$LOG"
    
    # Dump known address ranges
    echo "--- Service-related addresses ---" >> "$LOG"
    for addr in 0x0010001F 0x0014004E 0x00100033 0x0014007D; do
        echo "per3 $addr:" >> "$LOG"
        "$PERSDUMP" 3 "$addr" >> "$LOG" 2>&1
        echo "" >> "$LOG"
    done
    
    echo "--- Cluster range 0x0015xxxx ---" >> "$LOG"
    for i in 0 1 2 3 4 5 6 7 8 9 A B C D E F; do
        "$PERSDUMP" 3 "0x0015000$i" >> "$LOG" 2>&1
    done
    echo "" >> "$LOG"
    
    echo "--- Cluster range 0x0016xxxx ---" >> "$LOG"
    for i in 0 1 2 3 4 5 6 7 8 9 A B C D E F; do
        "$PERSDUMP" 3 "0x0016000$i" >> "$LOG" 2>&1
    done
    echo "" >> "$LOG"
    
    echo "--- Vehicle range 0x0010xxxx ---" >> "$LOG"
    for i in $(seq 0 63); do
        addr=$(printf "0x001000%02X" $i)
        "$PERSDUMP" 3 "$addr" >> "$LOG" 2>&1
    done
    echo "" >> "$LOG"
    
    echo "--- Protocol range 0x0014xxxx ---" >> "$LOG"
    for i in $(seq 0 127); do
        addr=$(printf "0x001400%02X" $i)
        "$PERSDUMP" 3 "$addr" >> "$LOG" 2>&1
    done
    echo "" >> "$LOG"
    
    # Try a broader scan
    echo "--- Broad scan: 0x0010-0x001F (step 0x1000) ---" >> "$LOG"
    for hi in 10 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 1E 1F; do
        for lo in 0000 0001 0002 0003 0004 0005; do
            addr="0x00${hi}${lo}"
            result=$("$PERSDUMP" 3 "$addr" 2>&1)
            if [ -n "$result" ] && ! echo "$result" | grep -q "error\|Error\|not found\|invalid"; then
                echo "$addr: $result" >> "$LOG"
            fi
        done
    done
    
else
    echo "persdump2 not found! Trying manual per3 read..." >> "$LOG"
    echo "" >> "$LOG"
    
    # Fallback: try to read per3 via the engineering persistence path
    echo "Listing /HBpersistence/:" >> "$LOG"
    ls -la /HBpersistence/ >> "$LOG" 2>&1
    
    echo "" >> "$LOG"
    echo "Listing /mnt/data/tools/:" >> "$LOG"
    ls -la /mnt/data/tools/ >> "$LOG" 2>&1
fi

# Also capture engineering menu state
echo "" >> "$LOG"
echo "--- Engineering state ---" >> "$LOG"
echo "DBGModeActive: $(ls -la /HBpersistence/DBGModeActive 2>&1)" >> "$LOG"
echo "PagSWAct: $(ls -la /HBpersistence/PagSWAct* 2>&1)" >> "$LOG"

# Capture ESD files currently deployed  
echo "" >> "$LOG"
echo "--- Deployed ESD files ---" >> "$LOG"
for d in /HBpersistence/engdefs /mnt/ifs1/engdefs /mnt/flash/efs1/engdefs /mnt/efs-system/engdefs; do
    if [ -d "$d" ]; then
        echo "$d:" >> "$LOG"
        ls -la "$d"/ >> "$LOG" 2>&1
    fi
done

# Try to find and dump factory ESD files
echo "" >> "$LOG"  
echo "--- Factory ESD contents ---" >> "$LOG"
for esd in /mnt/ifs1/engdefs/*.esd /mnt/flash/efs1/engdefs/*.esd; do
    if [ -f "$esd" ]; then
        echo "=== $esd ===" >> "$LOG"
        cat "$esd" >> "$LOG" 2>&1
        echo "" >> "$LOG"
    fi
done

# Copy ALL factory ESD files to USB for analysis
mkdir -p "$USB/factory_esd" 2>/dev/null
for d in /mnt/ifs1/engdefs /mnt/flash/efs1/engdefs /mnt/efs-system/engdefs; do
    if [ -d "$d" ]; then
        cp "$d"/*.esd "$USB/factory_esd/" 2>/dev/null
    fi
done

echo "" >> "$LOG"
echo "Saved: $LOG" >> "$LOG"
echo "Factory ESDs copied to: $USB/factory_esd/" >> "$LOG"
