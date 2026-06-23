# Tools

Pure-Python (3.x), no external dependencies. Written because `python-lzo` / `libucl`
won't build on Windows + Python 3.14; these run anywhere.

**Run against your own firmware.** Each script has the firmware path hard-coded near the
top — edit it to point at your extracted update. No firmware is shipped in this repo.

| Script | What it does |
|--------|--------------|
| `lzo1x.py` | LZO1X decompressor (faithful port of Linux `lib/lzo/lzo1x_decompress_safe.c`). Imported by the others. |
| `ifs_extract.py` | Decompress + walk a QNX6 **IFS** (LZO, big-endian 2-byte block lengths → 0x10000 blocks). E.g. RCC `ifs-root.ifs`. |
| `efs_extract.py` | Decompress + walk a QNX **EFS/F3S** flash image (`QSSL_F3S`, little-endian metadata; per-file UCL/LZO). Includes a pure-Python **UCL NRV2B** decompressor. E.g. RCC `efs-system.efs`. |
| `enumerate_elfs.py` | Locate/fingerprint the uncompressed ARM ELFs inside `app.img` by ELF header. |
| `extract_persistence_pair.py`, `carve_rcc_bins.py` | Targeted ELF carvers (string-search → backward ELF scan → size from section headers → dump). |

Format details: [`../docs/FILE_FORMATS.md`](../docs/FILE_FORMATS.md).

These are research/extraction utilities for firmware **you own**. See the repo README
disclaimer.
