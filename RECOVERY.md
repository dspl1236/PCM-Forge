# Back up, check, recover — PCM 3.1 flash

Everything a PCM 3.1 runs from lives in **64 MB of NOR flash** on two Spansion S29GL256N
chips: the bootloader, the operating system images, and `/HBpersistence` (your VIN,
activations and coding). An update that goes wrong, or a failing flash sector, can leave
the unit boot-looping at the logo. This page is what we know about getting it back, most
of it worked out with **@Auto1**, who recovered a boot-looping unit himself and shared
every step ([issue #11](https://github.com/dspl1236/PCM-Forge/issues/11)). Thank you.

> **Read this before you write anything to a PCM.** Backing up and checking are
> read-only and safe. Writing flash is not: a mistake in the wrong place needs a
> chip programmer and soldering to undo.

## Flash map

| Address | Region | Notes |
|---|---|---|
| `0x0000000` | IPL | the bootloader — **never write here** |
| `0x0100000` | FPGA | emergency FPGA bitstream |
| `0x01C0000` | IFS1 | QNX boot image (kernel, drivers, PCM3Root) |
| `0x0BC0000` | EMERGENCY | the recovery image (see below) |
| `0x0FC0000` | IFS2 | HMI, navigation core, languages (`PCM3Reload`) |
| `0x3000000` | HBpersistence | **this unit's** VIN, activations, coding |
| `0x3F00000` | UpdateHistory | update records, software IDs |

The same addresses are the `ADR…` folder names on a Porsche update disc.

## 1. Back up first

Do this on a working unit, **before** any update or experiment.

**With a PCM-Forge stick (easiest, beta).** In the web app's **Toolkit** tab, pick
**Flash Backup**, save to a FAT32 stick with 70 MB free, plug it into the running PCM and
wait for DONE. You get `pcm_flash.bin` (the whole 64 MB flash) plus your activation file
and stored VIN next to it. It is read-only — the same read as the menu option below —
and needs no activation. It never overwrites an earlier backup, and a copy that comes
out short (stick full) is deleted and reported in `flash_backup.log`.

**From the engineering menu (built into the PCM).** Activate **ENGINEERING** with
PCM-Forge, open the menu with **SOURCE + OPTION**, then **System → CustomerService**
with a FAT32 USB stick inserted:

- **05 Copy 64MB flash contents to USB** — the whole flash, as one 64 MB file ending
  `_flashcontent.bin`. This is the backup that matters. (The PCM runs
  `cp /dev/fs0 /fs/usb0/…`.)
- **04 Write SW Activation info to USB** — your activations decoded to a text file
  (`PCM3UnlockInfo_<date>.txt`: each feature, its code, and whether it is active).
- **06 Copy HBpersistence & UpdHistory to USB** — your persistence and update
  history as plain files.

Keep the stick's files somewhere safe. They contain your VIN — don't post them.

**With a chip programmer** (a unit that no longer boots): read both chips. Programmers
differ in how they lay the two chips out and some add a few bytes; the tools below work
that out for you.

## 2. Check the backup

[PCM-Explorer](https://github.com/dspl1236/PCM-Explorer) checks every region of a flash
dump on its own terms — no update disc needed:

```
python explorer.py nor.bin check                     # a 64 MB dump (e.g. _flashcontent.bin)
python explorer.py nor chipA.bin chipB.bin check     # two chip files from a programmer
python explorer.py nor.bin check "D:/update-disc"    # ...and match each region to a disc
```

IFS1, EMERGENCY and IFS2 should say **OK**. A damaged IFS2 is reported the way the PCM
itself fails: on @Auto1's unit the check said *"decompresses to its end marker but 32
bytes short (68,505,572 of 68,505,604)"*, the exact numbers from his boot log
(`memifs2: Decompression failed: dsize 68505572 dstlen0 68505604`), and it named the file
the damage was in. The desktop app does the same with **Open NOR chips…** / **Open
image…**.

## 3. Restore one region

The PCM carries Harman's own flash writer, **`flashit`** (`/proc/boot/flashit`, also in
the EMERGENCY image). Cut the region you need from your backup and write only that:

```
python explorer.py nor.bin save IFS2 ifs2.bin        # on your computer
flashit -p /dev/fs0 -a 0xFC0000 -d -f /fs/usb0/ifs2.bin   # on the PCM, from a shell
```

`-d` erases the sectors the file covers; it verifies after writing. Rules:

- **Never write below `0x40000`.** That is the IPL. Harman's own flash service warns
  about it, and a bad write there is the one mistake that does need the programmer.
- **Don't raw-write HBpersistence or UpdateHistory on a running unit** — they are
  live filesystems.
- **Restore only what is damaged**, from a backup of **the same unit**. Another
  unit's persistence region carries that unit's VIN, activations and coding.
- Keep the power stable while it writes.

From a programmer instead: `tools/nor_repair.py` can splice one region into a chip dump
and split it back into chip files — see `python tools/nor_repair.py --help`.

## 4. A unit that won't boot

What @Auto1 used, from the PCM's serial console (UART). At the IPL (bootloader) you can
tell it which image to start:

- **`boot 801c0000`** — start IFS1 directly. The flash is mapped at `0x80000000`, so this
  is flash address `0x1C0000`. This got his unit out of a dark-screen emergency loop.
- **`boot 80bc0000`** — start the EMERGENCY image, the factory recovery. It brings up
  the display, the DVD drive, USB and the network, then looks for an update — **on USB
  first, then a disc in the drive** — reads its `HBUPDATE.DEF`, checks your unit's
  hardware ID, and flashes it (*"Emergency update successfully finished"*).

*Still to document: where the UART pads are on the DPEC 4.1 board, the baud rate, and
how to stop the IPL to type the command. If you know, please add it to issue #11.*

## 5. After an update

- **The release must list your unit.** Every update disc names the hardware IDs it
  installs on (e.g. `PCME02XX1221`). 4.x releases only list `02` units.
- **Check the result**: the PCM's system-info screen lists each software part with
  **VALID / INVALID**. One INVALID line means a half-applied update.
- **An update deletes some of your files**: custom boot screens, audio-mixer settings,
  trace profiles (the disc's `clean_up_app` script). Back them up first (step 1).
- **Coding may need redoing.** After @Auto1 moved a unit from 4.73 to 4.76, AUX
  (Bluetooth) and Jukebox were gone — those are coding entries (`Auxiliary_Input`,
  `Bluetooth`, `Mehrausstattung`, `Variantencodierung`), written with PIWIS or a tool
  that can code the PCM. Activations are not affected: no update module writes the
  persistence region.

## Credits

- **@Auto1** — the IPL boot commands, the emergency-update route, the engineering-menu
  flash backup, and the first real flash dump our tools were tested on.
