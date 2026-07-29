# PCM 3.1 Boot Order, the Starter, and Why It Comes Up on FM

## Summary

The PCM does not boot into FM because Bluetooth is slow. It boots into FM because
**Bluetooth is not started at boot at all** — the package that owns it ships in the
`STOP` state and is demand-started later. When the audio source is chosen, A2DP
genuinely does not exist yet, so choosing FM is correct. The defect is that nothing
re-evaluates once the phone connects.

That single fact rules out an entire family of attempted fixes (see
`BT_AUX_BOOT_FIX.md`) and points at the one that can work.

It also explains something that has confused every module we ship: **`debugTools.sh`
does not run at boot.**

---

## The launcher

`/proc/boot/srv-starter-QNX` (173,296 bytes) reads an XML config,
`/proc/boot/pcm3_sop_starter.cfg` — `DynamicConfig version="24"`, **67 processes,
48 interfaces, 50 packages**.

Processes do not run in a fixed order. Each declares the filesystem paths it needs and
the ones it provides:

```xml
<Process>
  <Number>24</Number>
  <Name>/HBbin/PSSBSSProcess</Name>
  <RequiresInterface>…/tmp/phone_db_ready…</RequiresInterface>
  <ProvidesInterface>…/dev/scp_pss…</ProvidesInterface>
  <StartParam>DETACHED_DAEMON_SILENCE</StartParam>
</Process>
```

An "interface" is literally a path the starter waits to appear. Other fields:
`Partition`, `VariantCode`/`VariantMask`, `OnTerminate`, `MaxProcessRestarts`,
`KeepInterface`, `FinalAction`; each `Interface` entry carries a polling
`CheckInterval` in ms.

## ★ Packages gate everything, and half of them are STOP

Above processes sit **50 packages**, each with a `RequestState` and its own
`RequiresPackage` list. **A process whose package is `STOP` never launches**, no matter
how satisfied its interfaces are.

| pkg | name | state | requires |
|---|---|---|---|
| 5 | `PCM3ROOT` | RUN | 8 NDR, 10 SER_FPGA, 31 FLASH, 34 INIT_PCI_2, 45 SERVICEBROKER |
| 10 | `SER_FPGA` | RUN | 4 PCM3BOOT, 34 INIT_PCI_2 |
| 11 | `USB` | **STOP** | 0 MEMIFS |
| 12 | `MEDIALAUNCH` | **STOP** | 11 USB, 19 IO_NET, 34 INIT_PCI_2 |
| 20 | `PHONE_AND_BLUETOOTH` | **STOP** | 10 SER_FPGA, 29 PIPE, 39 PREPARE_PHONE_DB |
| 22 | `NETWORK` | RUN | 0 MEMIFS, **12 MEDIALAUNCH**, 19 IO_NET |
| 39 | `PREPARE_PHONE_DB` | RUN | 10 SER_FPGA, 31 FLASH, 40 IO_FS_TMP |
| 41 | `HDD_READY` | RUN | 0 MEMIFS, 13 MOUNT_HDD, 31 FLASH |
| 44 | `SCRIPT_LAUNCHER` | RUN | **12 MEDIALAUNCH** |

## Consequence 1 — Bluetooth is demand-started

Package 20 is `STOP`. Its two processes are:

- **24** `/HBbin/PSSBSSProcess` → provides `/dev/scp_pss`
- **55** `/usr/sbin/io-fs-media -d mediabt,verbose=5` → the A2DP media driver

Neither runs at startup. PCM3Root (package 5, `RUN`) comes up and picks a source while
they are still parked.

Cross-checked against the Audi MMI 3G+ (`8R0906961ES`, config `mmi3g-srv-starter.cfg`,
**same launcher binary, same schema version 24**): its package 13 `PHONE` is also
`STOP`, with the same `PSSBSSProcess` and `io-fs-media -d mediabt` inside. Same design,
different badge.

One genuine difference is worth recording. The MMI's phone database is its own flash
partition, **mounted**:

```
flashctl -p /dev/fs4p1 -e -f -m -n /mnt/phonedb        # constant time
```

The PCM instead **copies** it, in `/proc/boot/prepare_phone_db.sh`, in full:

```sh
/proc/boot/cp /HBpersistence/addressbookSql.db* /fs/tmpfs
/usr/bin/touch /tmp/phone_db_ready
```

That copy is on the path to the phone stack, and its cost scales with how many contacts
the owner has synced. It is not the cause of booting to FM — the package being `STOP`
is — but it is a real latency term once something does request the package, and it is
why `sysinfo` now reports the address-book size.

## ★ Consequence 2 — `debugTools.sh` does not run at boot

Process 34 is `ksh /HBpersistence/debugTools.sh`, and its only interface requirement is
`/etc/ifs2ready` — which looks early. But it is hosted by package **22 `NETWORK`**,
whose `RequiresPackage` includes **12 `MEDIALAUNCH`**, which is `STOP`, which in turn
needs **11 `USB`**, also `STOP`.

So `debugTools.sh` runs when the USB chain is demand-started — in practice **when a
stick is inserted** — not at key-on. It does run (telnet comes up, which is why this
went unnoticed), just late, and only in sessions where something wakes USB.

The same gate sits under **44 `SCRIPT_LAUNCHER`** (`proc_scriptlauncher`), the autorun
handler. Which gives a strong lead on the long-standing report of a unit that ignores
every USB stick — byte-clean payload, no splash, no log: **if package 11 never leaves
`STOP` on that unit, nothing downstream runs at all.** Testable directly, below.

**For a hook that genuinely runs every boot, use `/HBpersistence/hdd_ready.sh`** —
process 53, package 41 `HDD_READY`, `RequestState=RUN`, no `STOP` anywhere in its
chain. The firmware `if-test -f`s for it and runs it only if present, so creating it is
low-risk and deleting it is a complete revert. **Check whether it already exists before
writing** — append, never replace.

## The starter's control surface

`srv-starter-QNX` serves a writable resmgr:

```
/dev/starter/start      /dev/starter/status     /dev/starter/packages
/dev/starter/variant    /dev/starter/version
```

`io_write_debug` accepts the literal words `start` and `stop`, logging
`Debug START package #%d (%s)` / `Debug STOP package #%d (%s)`, and routes them through
`startmgr_requestPackages`. A **12-byte little-endian write** of `{state, package}`:

```
02 00 00 00 | 14 00 00 00     request RUN  on package 20 (PHONE_AND_BLUETOOTH)
03 00 00 00 | 14 00 00 00     request STOP on package 20
02 00 00 00 | 0b 00 00 00     request RUN  on package 11 (USB)
```

**It is a request, not an override.** Disassembly of `startmgr_requestPackages`
(`0x08043de8`) shows it writes exactly one field — `pkg->requestedState` at +4 of a
72-byte struct — rejects `(cmd-2) > 1`, and retriggers the scheduler. The normal state
machine still runs: `smStartPackage` (`0x0804658c`) walks the required-package list and
bails unless every one is RUN, and `checkProcessIFs` (`0x08045d88`) plus `startProcess`
(`0x080447d8`) each re-check the interface list before spawning.

Also settled by disassembly: **the starter launches a process even if the interface it
provides already exists.** `smStartProcess` (`0x08046320`) calls `startProcess` *first*
and only then `ctrlProcessProvIFs`; a pre-existing interface merely selects state
`RUN`(3) instead of `POST_STARTING`(2). So pre-creating `/tmp/phone_db_ready` does not
skip the copy — it changes bookkeeping, nothing else.

## What to measure

`sysinfo` v3.2.0 §19c captures all of this read-only:

- `/dev/serfpga4`, `/tmp/phone_db_ready`, `/dev/scp_pss`, `/tmp/graphicready`, `/fs/tmpfs`
- `/HBpersistence/addressbookSql.db*` size
- whether `debugTools.sh` / `hdd_ready.sh` already exist
- `TraceProfiles/` contents

If `/dev/scp_pss` is present when the report is written, Bluetooth is already up and the
problem is purely that nothing re-evaluated the source — go straight to the DSI switch.

## Two tests worth running on a bench unit

**1. Does forcing the package work?** Write `02 00 00 00 14 00 00 00` to
`/dev/starter/start` and watch for `/dev/scp_pss`. By the time a shell exists its
prerequisites (10 `SER_FPGA`, 29 `PIPE`, 39 `PREPARE_PHONE_DB`) are all RUN, so it
should take effect within a second. This buys A2DP *existing*; it does not un-make a
source decision already taken.

**2. Does the USB package explain a dead autorun?** On a unit that ignores sticks, write
`02 00 00 00 0b 00 00 00` (package 11 `USB`) and see whether the autorun fires. If it
does, the fault is upstream of every payload anyone has tried.

## Trace profiles — the HMI will narrate itself

`PCM3Reload` contains

```
%sEntering state %s
%sTransition %s --> %s (substates of %s)
```

so the HMI state machine logs its own transitions **by name**. Trace levels are
configured by `.hbtc` profiles under `/HBpersistence/TraceProfiles/` (and
`Specific/`) — writable persistence, no flash. The factory profile
`PCM3PersistentTraces.hbtc` is 28 bytes: the ASCII header
`HBTracePersistence 1.0.0\n` and a `ff ff ff` terminator, i.e. tracing present and
switched off. **Porsche ships ready-made profiles in the update package**, including
`A2DP_Traces.hbtc`, `AudioTraces.hbtc`, `BasicTraces.hbtc` and
`EmptyTracesForStartPerformance.hbtc`, so a profile may not even need authoring.

`CHBTraceHelper_storePersistent` means the unit can write these files itself, so the
format can be learned by setting levels once and reading back what it produced.

This is the cheap route to the screen-transition graph: enable the channel, walk the UI,
and the log gives you the state names and edges — ground truth, without disassembling a
generated state machine.

## Boot dependency depths (for reference)

Longest provider chain before a process *could* start, ignoring package state. Useful
for reasoning about ordering, but **it is not launch order** — that was the mistake that
produced the first version of this analysis:

| depth | proc | |
|---|---|---|
| 1 | 11 | `memifs` → `/etc/ifs2ready` |
| 2 | 34 | `ksh /HBpersistence/debugTools.sh` *(package STOPped — never at boot)* |
| 2 | 39 | `io-fs-media` → `/fs/tmpfs` |
| 5 | 23 | `devc-ser8250hb` → `/dev/serfpga4` (also provided by 65) |
| 6 | 9 | **PCM3Root** — picks the audio source |
| 6 | 52 | `prepare_phone_db.sh` → `/tmp/phone_db_ready` |
| 7 | 24 | `PSSBSSProcess` → `/dev/scp_pss` *(package STOPped)* |
| 8 | 55 | `io-fs-media -d mediabt` — A2DP *(package STOPped)* |

## Sources

`D:\PCM\ifs1_rootfs\proc\boot\pcm3_sop_starter.cfg`,
`D:\PCM\ifs1_rootfs\proc\boot\srv-starter-QNX`,
`D:\PCM\ifs1_rootfs\proc\boot\prepare_phone_db.sh`;
MMI comparison from `8R0906961ES` → `MU9411/ifs-root/41/default/ifs-root.ifs` →
`/mnt/ifs-root/etc/mmi3g-srv-starter.cfg`.
