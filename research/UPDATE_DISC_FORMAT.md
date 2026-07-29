# PCM 3.1 Update Discs — Format, Version Locks, and Why Custom Modules Cannot Install

## Summary

Decoded from a real Porsche field-update disc, `PCM_NA_20150721.ISO` (volume
`PCM_20150721`, 4.58 GB, built 2015-07-21), which carries **all 13 release variants** in
one image.

Three things worth knowing:

1. **The version ceilings are a dispatch table, not a check.** A unit whose hardware ID
   has no entry simply has nothing to run.
2. **Modules are RSA-signed.** A modified module cannot be made installable. This closes
   the flash route for custom software.
3. **Porsche delivers persistence content the same way we do** — the update carries a
   158-file `/HBpersistence` overlay, including `debugTools.sh`. An official update
   therefore *overwrites* our boot hook and wipes several things people modify.

`PCM-Explorer` reads these discs directly, including from the `.ISO` with no extraction:

```
python explorer.py PCM_NA_20150721.ISO          # what is this disc
python explorer.py <disc> units                 # which units will it install on
python explorer.py <disc> crc                   # verify every payload
python explorer.py <disc> sigs                  # signature inventory
```

---

## Layout

```
<disc root>/
├── pcm_update.disc          29 bytes, literally "This is a PCM3.x update disc."
├── HBUPDATE.DEF             top-level definition
├── PCM31<REG><VER>.def      one definition per release variant
└── PCM31<REG><VER>/
    ├── ASK/ BOSE/ TVTUNER/  amplifier and tuner payloads
    └── HEADUNIT/
        ├── ADR<ADDR>/       flash payloads -- the directory name IS the address
        ├── CRC/             *.CRC32 integrity records
        ├── SCR/             install-time shell scripts
        ├── FIL/HBpersistence/   the persistence overlay (158 files)
        ├── BTH/ GSM/ DVD/ HDD/ IOC_*/ BUP_*/ FPG*/
        ├── REQUIREDNAVDB.CFG
        └── <UNITID>_<MODULE>.sig     RSA signature per unit x module
```

`REG` ∈ {RDW (RoW/NA), CHN, ARB, LOW}; `VER` is the software line × 100. **LOW is the
no-hard-drive variant** and is the only release shipping no `PCM31HDD` module at all.

## Flash memory map

The `ADR` directory names are NOR-flash destination addresses, cross-checked against
`CRC/*.CRC32`:

| Address | Payload | Stock size |
|---|---|---|
| `0x00000000` | `ipl-pcm31_9600.bin` — IPL / bootloader | |
| `0x00100000` | `EM_9600_D_FPGA.hbbin` | |
| `0x001C0000` | `PCM3_IFS1*.ifs` — QNX boot image, PCM3Root | 9,305,764 |
| `0x00BC0000` | `PCM3_Emergency.ifs` — recovery IFS | |
| `0x00FC0000` | `PCM3_IFS2.ifs` — HMI, PCM3Reload, NavCore | 33,575,204 |
| `0x03000000` | `PCM3_HBpersistence.efs` | 15,728,640 |
| `0x03F00000` | `PCM3_UpdateHistory.efs` | |

**`/HBpersistence` is a 15 MB region in NOR flash, not on the hard drive** — which is
why persistence survives a drive swap.

## `.CRC32` records — reproducible

```
/dev/fs0, 001C0000, 008DFEA4, 26D8DF73
#File,  startadr, length, CRC
```

Device, start address, length, CRC — hex. The algorithm is **plain zlib/PKZIP CRC-32
over the whole image file**, and `length` is the exact byte count. Verified:

| image | length | declared | computed |
|---|---|---|---|
| `PCM3_IFS1_MOPF.ifs` | 9,305,764 | `26D8DF73` | `26D8DF73` ✓ |
| `PCM3_IFS2.ifs` | 33,575,204 | `19A52393` | `19A52393` ✓ |
| `PCM3_HBpersistence.efs` | 15,728,640 | `48EF377F` | `48EF377F` ✓ |

## Definition grammar

```
DISCID          = 12-JUN-2015-D;
SYSTEMRELEASEID = PCM31MOPF_V476_RDW;
CONTENTS
{
   <UNITID>=
   {
      REQUIREDNAVDB=\<REL>\HEADUNIT\REQUIREDNAVDB.CFG;
      <MODULEID>=
      {
         MODULETYPE=c;
         MODULESIZE=77851;                                 <- constant, not a size
         CRCFILE=\<REL>\HEADUNIT\<UNITID>_<MODTYPE>.sig;   <- points at the .sig
         BASEDIR=\<REL>\HEADUNIT;
         FILES={ .\ADR01C0000\PCM3_IFS1_MOPF.ifs; .\CRC\IFS1_MOPF.CRC32; ... };
      };
   };
}
CONTROL
{
   STARTUPDATE <UNITID>;  UPDATE <MODULEID>; ...  ENDUPDATE;
}
```

## ★ The version lock is a dispatch table

`CONTROL` holds one `STARTUPDATE <unit-id>` block per supported unit. The unit announces
its ID; **if that ID has no block, the disc has nothing to run for it.** No refusal, no
check — absence.

**Unit ID** = `PCM` + `{G|E|S|C}` + `{01|02}` + `XX` + `YYWW`:

- letter — market/feature variant, accumulating by generation (v1 has G only; v2 adds E; v3 adds S; v4 adds C)
- **`01` / `02` — the hardware generation**, pre-facelift and MOPF
- `YYWW` — date code (`0709`…`0920` = 2007–2009; `1220`/`1221` = 2012)

Ceilings, straight from `SYSTEMRELEASEID`: `PCM31_V247_RDW` (2.47), `PCM31_V343_RDW`
(3.43), `PCM31MOPF_V476_RDW` (4.76) — note v4's ID literally says **MOPF**.

**No 4.xx release dispatches to any `01`-series unit.** Across all 13 definitions, every
v1/v2/v3 release targets only `01`-series and every v4 release only `02`-series, with
**zero overlap**:

```
v3 (RDW300) accepts : PCM{E,G,S}01XX0919/0920
v4 (RDW400) accepts : PCM{C,E,G,S}02XX1221
in both             : none
```

**Read this precisely.** It is a *distribution* fact: Porsche never shipped a package
mapping old hardware to 4.xx. It is **not** evidence that `01`-series hardware cannot run
4.xx — nobody ever tested that, because no package would attempt it.

## ★ Modules are RSA-signed

Every `<UNITID>_<MODULE>.sig` is 264 bytes of ASCII:

```
[RSA]=9f055e872f6fabf40762b85754543fb67781476afa1b7b69e918faa5b8…622687;
```

`[RSA]=` + **256 hex characters (128 bytes → RSA-1024)** + `;`. There are 2,943 of them
on this disc. The `.def` refers to them through the confusingly-named `CRCFILE=` field.

**Consequence: a modified module cannot be signed, so the OEM updater will not install
custom firmware.** Three honest options:

1. **Overlay delivery (recommended).** Ship persistence content and tooling by the USB
   autorun route. No signature needed, no flash touched, revert by deleting files.
   Everything PCM-Forge does today works this way.
2. **Establish whether the signature is actually enforced.** The field being named
   `CRCFILE` hints the mechanism predates the RSA content, and a verifier absent from the
   unit cannot enforce anything. Settling it means finding the update tool in IFS1 and
   checking whether it parses `[RSA]=`. **Until then, assume enforced.**
3. **Reuse stock modules unchanged** — a valid recovery/reflash disc that carries no
   changes.

## Module types

| Module | Writes | Risk |
|---|---|---|
| `PCM31IPL` / `PCM31BOL` | bootloader at `0x0` | **highest — unrecoverable** |
| `PCM31EMR` | emergency IFS + FPGA | high |
| `PCM31IOC` | I/O-controller MCU + FPGA | high |
| `PCM31APP` | IFS1 + IFS2 + `SCR/clean_up_app` + the persistence overlay | high |
| `PCM31HDD` / `PCM31HDA` | hard-disk content | moderate |
| `PCM31CFG` | configuration | low |
| `PCM31FDC` / `PCM31PWC` | front-display / power controllers | moderate |
| `HDDCHECK` | pre-flight disk check | read-only |
| `PCM3KILL` / `PCM3KILL_MOPF` | *no payload on this disc — `.sig` stubs only* | — |

`HDDCHECK` runs only on the 2009-code `01` units in v2/v3 releases; it is absent from
every v4 release and from the 2008 units.

Module IDs are `PCM31<TYPE>` + `01` + `<5-digit build>` + `<variant letter>`, e.g.
`PCM31APP0115245A` — build 15245, variant A.

## ⚠️ `SCR/clean_up_app` deletes things people modify

The APP module runs a `/bin/sh` script *before* its payload lands (stock header:
`executing clean_up_app 04/11/2011`). Among its `rm -f` list:

```
/HBpersistence/audiomixer_BOSE.txt
/HBpersistence/audiomixer_BURMESTER.txt
/HBpersistence/audiomixer_ASK.txt
/HBpersistence/audiomixer-ann-levels_*.txt
/HBpersistence/CustomBootscreen_*
/HBpersistence/*.core
/HBpersistence/persistTrace*   /HBpersistence/TraceProfiles/*
```

**An official update wipes any amplifier-profile modification and any custom
bootscreen**, and clears trace profiles. Anything we ship into those files must be
re-applied afterwards.

## Porsche ships a persistence overlay too

`FIL/HBpersistence/` inside the APP module is **158 files** — including
**`debugTools.sh`** and `QNXTools/cksum`, plus the audiomixer set, `CVALUE*.CVA`,
`CsiConfig1.csi`, ipod configs, navi grammars, `check_HDD.sh`,
`emergencyPartition{MOPF,SOP}`, `TouchCalib.bin`, `PagSWAct.csv`, and the
`TraceProfiles/` set (`A2DP_Traces.hbtc`, `AudioTraces.hbtc`, `BasicTraces.hbtc`,
`DefaultTraces.hbtc`, `EmptyTracesForStartPerformance.hbtc`, …).

So the OEM updater delivers persistence content through **exactly the hook our modules
use** — which validates the approach, and means an official update replaces
`debugTools.sh` wholesale.

## Reading a disc

Plain ISO9660: PVD at sector 16, root dirent at PVD+156, 2048-byte sectors, directory
records never spanning a sector. `PCM-Explorer` walks it in place; no extraction step and
no `7z` needed.
