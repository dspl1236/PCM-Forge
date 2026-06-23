# Reverse-Engineered File Formats (MIB2 / QNX)

Format notes recovered while building the unpackers in `tools/`. Useful for anyone parsing
Harman MIB2 / QNX Neutrino 6.5 images. All offsets little-endian unless noted.

---

## 1. `app.img` (MMX application image)

- Custom header `EB 10 90 00 …` (looks like a FAT BPB but the values are garbage). **Not a
  standard filesystem** — do not try to mount it.
- Contains **788 uncompressed 32-bit ARM ELFs** back-to-back. Scan for
  `7F 45 4C 46 01 01 01` (`\x7fELF`, 32-bit LE) with `e_machine == 0x28` (ARM); compute size
  from `max(e_shoff + e_shnum*e_shentsize, e_phoff + e_phnum*e_phentsize)` and dump.
- Binaries are QNX (`interpreter /usr/lib/ldqnx.so.2`); version strings read
  `qnx-armv7-650sp1` → QNX Neutrino 6.5.0 SP1, ARMv7-LE.
- The GEM script library is plaintext shell in the region ~`0x16D90000–0x16E90000`.

See `tools/enumerate_elfs.py`.

---

## 2. QNX6 IFS (`ifs-root.ifs`) — LZO, block-framed

Layout: 8-byte ARM trampoline, then a `startup_header` at file offset `0x08`
(signature `EB 7E FF 00`). Field map (from the header, verified by
`ram_size == startup_size + imagefs_size`):

| off (from 0x08) | field | value (example) |
|-----|-------|-------|
| 0x00 | signature | `0x00FF7EEB` |
| 0x06 | flags1 | `0x09` (compression bits → LZO) |
| 0x0A | machine | `0x28` (ARM) |
| 0x20 | startup_size | `0x22108` |
| 0x24 | stored_size | `0x65DC08` (compressed, on-disk) |
| 0x2C | imagefs_size | `0xE86908` (uncompressed) |

The compressed **imagefs** begins right after the startup (`0x08 + startup_size = 0x22110`)
and is a series of **blocks**:

```
[ 2-byte BIG-ENDIAN compressed length ][ LZO1X stream → 0x10000 uncompressed ] ...
```

Each block decompresses to 64 KiB (last smaller); the stream ends with the LZO1X EOF marker.
Decompressed result is a standard QNX **image filesystem** (image_header `imagefs`, then
dirents with file offset/size). See `tools/ifs_extract.py`.

### LZO1X gotcha (the one that bites everyone)
A from-scratch LZO1X decoder must implement the **`state` machine** exactly. The trap: the
**post-literal-run short match (`state == 4`) copies 3 bytes, not 2.** Getting this wrong
silently corrupts output a few KB in (back-references drift). `tools/lzo1x.py` is a faithful
port of the Linux kernel `lib/lzo/lzo1x_decompress_safe.c`.

---

## 3. QNX EFS / F3S (`efs-system.efs`) — UCL/LZO, **little-endian**

QNX flash filesystem (`devf` driver). Magic **`QSSL_F3S`**. **Important:** the public
`efsdump.c` reference assumes **big-endian** (`ntohs`); the Harman/ARM images are
**little-endian** — read all metadata LE, no byte-swap.

- `boot_info` at file `0xC0` (`struct_size`, `rev`, `sig[8]="QSSL_F3S"`, `unit_index`,
  **`unit_total` @ +14**, `unit_spare` @ +16, `align_pow2` @ +18, `root extptr` @ +20).
- N units of `2^unit_pow2` (here 192 × `0x20000`). `extptr = { logi_unit:u16, index:u16 }`,
  `logi = physical+1` for a freshly-built image.
- **Heads** (32-byte extent records) grow **down** from each unit's end:
  `head[i] = unit_end − 32*(i+1)`. In the LE layout the **extent type is byte+1 of the
  status word** (`& 3`: FILE=3, DIR=2, SYS=1, XIP=0) — *not* the field the BE struct implies.
- Extent data: `data_offset = phys*unit_size + (hi*0x10000 + lo) << align_pow2`
  (`align_pow2 = 6` → ×0x40 here), length `text_size`, chained via `next`.
- A DIR head's text points to a `dirent` (`struct_size, moves, namelen, first extptr,
  name[4-aligned], stat{struct_size, mode, uid, gid, mtime, ctime}`); `mode & 0xF000`:
  dir `0x4000`, file `0x8000`.

### Per-file compression
File data may start with magic **`iwlyfmbp`** + `deflate_filehdr { sig[8], usize:u32,
blksize:u16, cmptype:u8 (0=LZO,1=UCL), flags }`, then blocks framed by
`cmphdr { prev, next, pusize, usize }` (all LE); compressed length = `next − 8`, decode to
the block's `usize`. The MHI2 RCC EFS uses **UCL (NRV2B)**. `tools/efs_extract.py` includes
a pure-Python `ucl_nrv2b_8` decompressor.

---

## 4. Software-update `metainfo` (SWDL)

INI-style, section names case-folded to lowercase. Key sections:

- `[common]` — release/variant/region metadata + **`MetafileChecksum`** (SHA1).
- per-device/`[…\File]` sections — `Source`, `Destination`, `FileSize`, `CheckSumSize`,
  `CheckSum`/`CheckSum1…` (SHA1 per `CheckSumSize` chunk).
- `[Signature]` — `signature1…8`, each 16 hex bytes → concatenated **128-byte = RSA-1024**
  signature over the metainfo SHA1, verified with the per-OEM Metainfo public key.

**Integrity quirk (CVE-2020-28656):** the metainfo checksum is computed over only
`[start → MetafileChecksum line]` + `[next line → "[Signature]" line]`. Since `[Signature]`
is the last section, **anything appended after it is parsed but unsigned.** See
[`FINDINGS.md` §5](FINDINGS.md#5-sd-card-delivery--cve-2020-28656-confirmed-on-this-firmware).

---

### Package layout (Porsche/MHI2)
The SD/USB update is **not** a 7-zip archive (the Polo/MIB2-STD used 7z). The card root holds
`metainfo2.txt` plus a set of `update61852-*.dat` containers with a custom magic
**`UPD\x00`** (`55 50 44 00`, then a small version/size header). The metainfo's `[…\File]`
sections describe the payloads via `FileName` / `Source` / `Destination`. The append-after-
`[Signature]` technique (above) adds an unsigned `[…\File]` section pointing at a file you
place on the card.

---

## 5. FEC / Data / Metainfo public-key blob (`*_public_signed.bin`, 288 bytes)

```
[ modulus n : 128 bytes (RSA-1024, big-endian) ]
[ exponent  : 32 bytes  (big-endian, == 3) ]
[ signature : 128 bytes (the blob signed by a VAG root key) ]
```

One per trust chain (FEC / DK / MI) per OEM (AU, BY, PO, SE, SK, VW, + generic). Public
halves only — not factorable in practice, and verification is OpenSSL-strict (see FINDINGS §2).
