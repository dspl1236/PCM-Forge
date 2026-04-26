# PCM 3.1 System Information — Andrew's Cayenne 958

## System Info Screen (INFO + SOURCE)

| Field | Value |
|-------|-------|
| System Version | V4.76 |
| Platform | PCM3.1 |
| Serial Number | BE9632G5671071 |
| XM Radio | Active (Ch 52 BPM) |

## Current System Details

| Component | ID | Status |
|-----------|-----|--------|
| HWID_PCM3 | PCME02XX1221 | — |
| SWID_PCM31APP | PCM31APP0115245A | VALID |
| SWID_PCM31EMR | PCM31EMR0113155E | VALID |

## Hardware ID Decoded

- `PCME` = PCM variant E (matches PCME01XX firmware in update ISO)
- `02` = Hardware revision 2
- `XX` = Wildcard/generic
- `1221` = Board revision

## Software ID Decoded

- `PCM31APP0115245A` = PCM 3.1 Application, version 01-15245A
  - ISO has PCM31APP0114183A (older)
  - Car has newer firmware than the update disc!

- `PCM31EMR0113155E` = PCM 3.1 Emergency/Recovery, version 01-13155E

## IOC Firmware from Update ISO

Multiple IOC variants for different hardware revisions:

| Directory | File | Size | For HW Rev |
|-----------|------|------|------------|
| IOC_B1 | (TBD) | — | Early hardware |
| IOC_B3 | (TBD) | — | Rev B3 |
| IOC_C0 | (TBD) | — | Rev C0 |
| IOC_D1 | 9600_UPD.bin | 703 KB | Rev D1 |
| IOC_E2_B3 | (TBD) | — | E2 variant B3 |
| IOC_E2_C0 | (TBD) | — | E2 variant C0 |
| IOC_E2_D1 | 9608_UPD.bin | 703 KB | E2 variant D1 |
| IOC_9x1_B3 | (TBD) | — | 9x1 (911/Boxster) B3 |
| IOC_9x1_C0 | (TBD) | — | 9x1 (911/Boxster) C0 |
| IOC_9x1_D1 | (TBD) | — | 9x1 (911/Boxster) D1 |

## IOC Firmware String Analysis

Key strings found in 9600_UPD.bin:

```
9600_App                          — App identifier
Copyright (c) 1993-1997 CMX-RTX   — CMX RTOS on the V850!
Gateway                            — CAN gateway function
CfIpc                              — IPC (Inter-Processor Communication)
CfMost                             — MOST bus interface
CfPowerM                           — Power management
Diag                               — Diagnostic handler
AMFMTuner                          — FM/AM tuner control
TunerMost                          — Tuner via MOST bus
TunerProcess                       — Tuner processing
MOST_MO / MOST_ST                  — MOST bus states
cfDiagMost                         — Diagnostics over MOST

WUR_DIAGNOSIS_SESSION              — Wake-Up Reason: Diag session
WUR_DOOR                           — Wake-Up Reason: Door open
WUR_DWA_INACTIVE                   — Wake-Up Reason: Alarm inactive
WUR_ECU_RESET                      — Wake-Up Reason: ECU reset
WUR_HU_ON_REQ                      — Wake-Up Reason: Head Unit on
WUR_IGNITION                       — Wake-Up Reason: Ignition
WUR_ON_BUTTON                      — Wake-Up Reason: Button press
WUR_PRODUCTIONMODE                 — Production mode
WUR_START_IN_FLASHMODE             — Flash mode boot

FR_GET_HW_VERSION                  — Framework: Get HW version
FR_GET_SW_VERSION                  — Framework: Get SW version
FR_GET_STATUS                      — Framework: Get status
FR_GETTEMP                         — Framework: Get temperature
FR_GETLSENS                        — Framework: Get light sensor
FR_GETPWM1                         — Framework: Get PWM channel
FR_SET_IOC_INFO                    — Framework: Set IOC info

Version %x.%02x.%02x              — Version format string
E2PVer A:%05d C:%05d              — EEPROM version

TskHandlHigh / TskHandlLow        — Task handlers (RTOS tasks)
Jul 08 2009                        — Compile date
```

## Key Differences from MMI3G V850app.bin

| Aspect | MMI3G V850app.bin | PCM 9600_UPD.bin |
|--------|-------------------|-------------------|
| Size | 589,760 bytes | 720,334 bytes |
| RTOS | Custom/bare-metal | CMX-RTX RTOS |
| Bus names | Antrieb, Dashboard, etc. | Not found (different naming) |
| MOST support | No | Yes (AMFMTuner, TunerMost) |
| Compile date | Unknown | Jul 08 2009 |
| Gateway string | cfappgateway | Gateway |
| IPC | HPIPC references | CfIpc |
| Diagnostics | PERS subsystem | Diag, cfDiagMost |

## Notable Findings

1. **CMX-RTX RTOS** — The PCM's V850 uses a commercial RTOS (CMX-RTX by
   CMX Company), unlike the MMI3G which appears to use a custom scheduler.
   This means the V850 has proper task management, priorities, and scheduling.

2. **MOST bus integration** — The PCM's IOC handles the MOST (Media Oriented
   Systems Transport) fiber optic bus for audio, which the MMI3G doesn't have
   in its V850. This is used for Bose/Burmester amplifier communication.

3. **Wake-Up Reasons (WUR)** — The IOC manages vehicle wake-up, including
   a diagnostic session wake (WUR_DIAGNOSIS_SESSION) which means the PCM
   can be woken up by a PIWIS diagnostic request.

4. **Flash mode** — WUR_START_IN_FLASHMODE confirms the IOC can boot into
   a flash/update mode, which is how the firmware gets updated.

5. **Production mode** — WUR_PRODUCTIONMODE suggests a factory/test mode
   exists, potentially useful for debugging.

---

## /mnt/data/tools/ — Harman Development Tools (HDD)

Found on PCM HDD at /mnt/data/tools/. These are factory development/debug
tools left on the drive. World-writable, executable.

### Key Tools
| Tool | Size | Purpose |
|------|------|---------|
| NavigationNdrInfo | 563KB | NDR/CAN diagnostic — CONFIRMS NDR access works |
| taco | 5.3MB | Harman trace/diagnostic suite (taco.hbtc config) |
| find | 79KB | Standard find utility (missing from IFS) |
| vi | 122KB | Text editor |
| persdump2 | 278KB | Persistence data dump |
| sqlite_console | 60KB | SQLite CLI |
| mmecli | 232KB | Multimedia explorer CLI |
| mmexplore | 85KB | Multimedia explorer |
| ping | 39KB | Network ping |
| fdisk | 119KB | Disk partitioning |
| which | 7KB | Command finder |
| hbhogs | 202KB | Process resource monitor |
| showmetadata | 613KB | Metadata viewer |
| upd_history_reader | 198KB | Update history reader |
| ipgrabber | 21KB | Instruction pointer grabber (profiling) |
| flashinfo | 7KB | Flash information |
| chkqnx6fs | 44KB | QNX6 filesystem checker |

### NavigationNdrInfo Output (confirmed working)
Queries NDR message IDs:
- 0x000203b3: Database version requirements
- 0x000203b4: Available database files (nav maps)
- 0x000203b5: Available database packages
- 0x0002064d: LVM mount options

Proves the NDR devctl() interface is accessible from userspace.

### Usage
```
export PATH=$PATH:/mnt/data/tools
NavigationNdrInfo          # query nav database info via NDR
find / -name "*.esd"       # search for files
vi /tmp/test.sh            # edit files
persdump2                  # dump persistence data
sqlite_console             # SQLite access
```

### Implications for Oil Service Reset
NavigationNdrInfo proves that NDR devctl() works from userspace.
Our uds_send.c uses the same interface. If we can cross-compile it,
the CAN communication path is confirmed viable.

---

## QNX Prefix Tree Overlay — Bypassing Read-Only /etc/

### The Problem
PCM 3.1's `/etc/` is in the IFS boot image (read-only). Can't modify:
- `/etc/hosts` (DNS timeout fix)
- `/etc/inetd.conf` (add port 2323)
- `/etc/resolv.conf` (DNS servers)

### The Solution: QNX Prefix/Mount Overlay
QNX's namespace uses a prefix tree with longest-match resolution.
New mounts go "on top of" existing ones. We can mount a writable
RAM filesystem over `/etc/`:

```bash
# Step 1: Save current /etc contents to RAM
mkdir -p /dev/shmem/etc_overlay
cp /etc/* /dev/shmem/etc_overlay/ 2>/dev/null

# Step 2: Create a writable RAM filesystem mounted at /etc
# Option A: Use devf-ram
devf-ram -s0,1m -i10,1   # Create /dev/fs10 (1MB RAM disk)
mount -t qnx4 /dev/fs10 /etc

# Option B: Just bind a tmpfs directory over /etc
# (QNX 6.3.2 might support this via io-fs-media or similar)

# Step 3: Copy saved contents back
cp /dev/shmem/etc_overlay/* /etc/

# Step 4: Now /etc is writable!
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "2323 stream tcp nowait root /bin/ksh ksh -i" >> /etc/inetd.conf
echo "192.168.0.91 pc" >> /etc/hosts
```

### Alternative: devf-ram Already Running!
The PCM already has `devf-ram` running:
```
462926 devf-ram -s0,8m -i4,1     ← 8MB RAM disk, instance 4
266306 devf-ram -s0,1m -i1,3     ← 1MB RAM disk, instance 1 (from IFS)
```

We might be able to reuse one or start a new instance.

### QNX Prefix Resolution Rule
When multiple filesystems are mounted at the same prefix, QNX uses
the **most recently mounted** one first (LIFO). So mounting a
writable filesystem at `/etc` will shadow the read-only IFS `/etc`.

### Investigation Commands (from PuTTY)
```bash
# Check current mounts
mount
df

# Try the overlay
mkdir -p /dev/shmem/etc_save
cp /etc/* /dev/shmem/etc_save/ 2>/dev/null
ls /dev/shmem/etc_save/

# Check if we can start a new devf-ram
devf-ram -s0,512k -i20,1 2>&1
ls /dev/fs20*

# Try mounting over /etc
mount /dev/fs20 /etc 2>&1
```

### Impact if Successful
- `/etc/hosts` writable → fix telnet DNS timeout
- `/etc/inetd.conf` writable → persistent port 2323 within session  
- `/etc/resolv.conf` writable → DNS for internet access
- All within session (RAM disk, not persistent across reboot)
- But toolkit script can set it up each time!
