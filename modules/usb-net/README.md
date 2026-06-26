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

`/etc` is read-only, so this is session-only — re-insert the stick after each reboot to
re-enable.

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
