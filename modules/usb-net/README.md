# usb-net — Universal ASIX USB-Ethernet for HN+ (PCM 3.1 / MMI3G+ / RNS-850)

Gets a **USB-to-Ethernet adapter working** on the Harman HN+ head units (Porsche PCM 3.1,
Audi MMI3G+, VW RNS-850) so you can reach the unit over the network (telnet/qconn) for
diagnostics, coding, and LTE/router connectivity — **without modifying the read-only
firmware**.

## What's new here
Older units' built-in `devn-asix.so` only recognizes **AX88772 / 772A**. Modern cheap
adapters are **AX88772B / 772C**, which fail to initialize on the old driver (they attach,
the link comes up, but **transmit is broken** — RX works, ping doesn't).

This module ships **`devn-asix-universal.so`** — taken from a *later* HN+ firmware (MU9498)
that contains Harman's **own `ax_enable_88772B` init code**, with its dormant 772B match
**activated**. One driver now covers:

| Chip | USB ID | Status |
|------|--------|--------|
| AX88772  | `0b95:7720` | ✅ |
| AX88772A | `0b95:772a` | ✅ |
| **AX88772B / 772C** | `0b95:772b` | ✅ (the fix — proper TX/medium-mode init) |
| AX88178 + Linksys/NetGear rebadges | various | ✅ (carried over) |
| AX88172 (USB 1.1) | `0b95:1720` | ❌ dropped (obsolete; its table slot was reused for 772B) |
| AX88772D / AX88179 (gigabit) | `0b95:772d` / `179x` | ❌ not yet (different init; needs a source build) |

Confirmed working on a real Porsche **PCM 3.1 (io-net)** with an AX88772C adapter — and the
same driver loads on MMI3G+/RNS-850 (identical QNX 6.3 io-net SH4 ABI).

## Why it's brick-safe
The driver is **loaded from the USB stick into the running io-net** (`mount -T io-net
/tmp/...`). It **never touches the read-only flash/IFS** — so if anything misbehaves, a
reboot returns the unit to bone stock. (This is the *opposite* of editing the RO filesystem,
which is how units get bricked.)

## Use
1. Build the USB stick with the PCM-Forge web app (or copy these three to a FAT32 stick root):
   `copie_scr.sh` (autorun trigger) + `usb_net_run.sh` (renamed to `run.sh`) +
   `devn-asix-universal.so`.
2. Plug the USB-Ethernet adapter into the unit (to your router/switch for DHCP, or straight to
   a PC for static).
3. **Boot the unit fully**, then **insert the stick** (it must be an insert *event* after boot).
4. Wait ~60–90 s, pull the stick, read `pcm_usbnet_<timestamp>.txt`.
5. If it shows an `inet` address: `telnet <that IP>` — port 23 (login `root`) or 2323 (raw shell).
   If the PCM already had the adapter up (a 772 / 772A, which it loads itself), the stick uses
   that interface and doesn't load the universal driver over it.

## This session, or every boot

In the web app's Toolkit, **What to do** picks one of:

| Choice | What it does |
|---|---|
| **This session only**: DHCP / Static / LTE | Loads from the stick, nothing written to the PCM. A restart undoes it; insert the stick again after each restart. |
| **Every boot**: Auto adapter · DHCP / Auto adapter · static (beta, PCM 3.1) | The same, and it stays after every restart with no stick. |
| **Remove the boot setup** | Undoes *Every boot* and puts the PCM's own settings back. |

Static shows the IP address, netmask and an optional gateway. Under **Advanced**, the adapter
driver can be forced (Auto-detect is the default).

**How *Every boot* works.** The PCM runs `/HBpersistence/debugTools.sh` on every boot. The
stick (`scripts/net_boot_setup.sh`) adds one line to it that starts `forge_net.sh`, and keeps
the settings in `forge_net.conf`. At each boot, `forge_net.sh` waits up to 5 minutes for the
adapter, sets the address, opens the 2323 shell, and exits.
- **772 / 772A:** the PCM loads its own driver on plug-in, as en5.
  - Static: the PCM first gives it 192.168.0.90, then `forge_net.sh` sets your address in its
    place. The PCM also adds its in-car address 172.16.250.252, which stays, so `ifconfig en5`
    lists yours as `inet alias`.
  - DHCP: the PCM asks the router itself.
  - The `/HBpersistence/incar` flag decides between the two, so the stick sets or clears it.
- **772B / 772C:** the PCM doesn't recognise these, so the stick also copies the universal
  driver to `/HBpersistence`, and `forge_net.sh` loads it when no adapter has come up after a
  minute. These need the adapter plugged in at boot.
- **Telnet at boot:** the stick creates `/HBpersistence/DBGModeActive` if it's missing. That
  flag is what makes the PCM start telnet.
- **Writes only what changed:** inserting the stick again with the same settings rewrites
  nothing. With new settings it updates in place.
- **Remove puts it back:** the first install records how `DBGModeActive` and `incar` were
  (`forge_net.orig`), and Remove restores them that way.

### When a second module needs a boot hook

Today usb-net is the only PCM-Forge feature that runs at boot, and it owns the setup: one line
in `debugTools.sh`, its own files, and the `DBGModeActive` / `incar` flags. Its Remove deletes
only lines that mention `forge_net.sh`, so a line another module adds would survive. But Remove
also puts `DBGModeActive` back the way it found it, which would turn off telnet for a module
that needs it, and it deletes the shared backup `debugTools.sh.forge-orig`.

So the first time another module needs to run at boot, move to a shared layout:
- **One hook line for all of PCM-Forge**: `debugTools.sh` runs every script in
  `/HBpersistence/forge_boot.d/`.
- **Each module owns one file there** (usb-net: `forge_boot.d/net.sh`). Install drops it in;
  Remove deletes only that file.
- **The last module out takes the hook line with it**: when `forge_boot.d/` is empty, the line
  comes out, and `debugTools.sh` is back to factory.
- **Shared flags have owners**: each module records which flags it needed (`DBGModeActive`
  for telnet). A flag goes only when no installed module still needs it, and goes back to the
  car's own original state.

Moving existing usb-net installs over is a normal reinstall: `net_boot_setup.sh` already writes
only what changed. Teach it to replace the old `forge_net.sh` line with the shared one.

Only the firmware images are never touched. **Every boot leaves telnet (23) and a root shell
(2323) open with no password** on whatever network the adapter is cabled to; use it only on a
network you trust.

Tested on a 958.2 (PCM 3.1, 15245AS9) with an AX88772A: cold boots with no stick bring up the
static address, telnet at ~30 s and 2323 at ~60 s after the screen.

## Blank-EEPROM clones
A few ultra-cheap clones ship with **no MAC programmed**, so *any* driver reads a garbage MAC
(no ARP). For those, use the **MAC-fix variant** (`devn-asix-772b-macfix.so`), which forces a
valid MAC. Adapters with a real MAC (the vast majority, incl. genuine D-Link/Apple) don't
need it.

## Rebuild it yourself
`tools/asix_universal_patch.py` regenerates this driver from any 772B-capable HN+
`devn-asix.so` (e.g. extracted from MU9498/8R0906961FE firmware) — no proprietary binary
required if you have your own firmware. It auto-locates the match table and activates 772B.

## Credit
Reverse-engineered and validated via PCM-Forge issue #7 (thanks to **dougie996** for the
on-car testing). Right-to-repair / owner-diagnostics use on hardware you own.
