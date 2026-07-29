# The PCM 3.1 HMI Is Data — HBM5 `.mmi` Files

## Summary

The Porsche PCM's user interface is not compiled into the HMI binary. It is **34 `.mmi`
files** sitting beside `PCM3Reload` in IFS2, holding the screens, the element tree, and
every string the unit can display in every language it ships. `cayenne.mmi` is one car's
screens; `en_us.mmi` and `ru_ru.mmi` are the same interface in different words.

That means the whole UI can be read without emulating anything:

- **44,100 strings** across the corpus, in nine languages — ten on the instrument
  cluster, which is the only place **Chinese** appears
- **10,268 drawables** resolved to real x/y/w/h on an 800×480 display
- **68 screens**, named by their contents

`PCM-Explorer` reads them:

```
python explorer.py moccaV2Target.mmi              # what is in this HMI file
python explorer.py moccaV2Target.mmi strings X    # search every string
python explorer.py moccaV2Target.mmi langs        # keys across all languages
python explorer.py moccaV2Target.mmi screens 33616
```

---

## Where they live

`/mnt/ifs_app/HBproject/` inside IFS2:

| file | role |
|---|---|
| `moccaV2Target.mmi` (3.7 MB) | the target definition — element tree, base German |
| `cayenne.mmi`, `cayenne_e2ii.mmi`, `panamera.mmi`, `panamera_g1ii.mmi` | per-vehicle |
| `us.mmi`, `ece.mmi` | market variants |
| `cluster.mmi` | instrument cluster — 10 languages |
| `diagnosis.mmi` | |
| `en_us`, `en_gb`, `fr_fr`, `it_it`, `es_es`, `nl_nl`, `ru_ru`, `ar_sa` | locale text |

**v2 and v3 ship only `cluster` + `moccaV2Target`.** The per-vehicle and per-locale split
is new in v4 — the HMI became more data-driven over time.

## Container

Little-endian, a serialised C++ object graph, no compression at the container level:

```
0x00 'HBM5' | 0x04 u16 ver=0x0100 | 0x06 u16 nSchema
0x08 u32 schemaOff (== 0x28 + 12*nDir) | 0x0c u32 rootOff | 0x10 u32 0x28
0x14 u32 fileSize (exact) | 0x18 u32 nDir | 0x1c u32 0x28
0x20 u32 structSize (poolOff = structSize + 0x28) | 0x24 u32 opaque

directory: nDir x 12 bytes at 0x28, ids STRICTLY ASCENDING (binary-searchable)
  +0 u32 id
  +4 u32 absolute offset
  +8  u8 bit0: 1 = descriptor, 0 = payload;  bits 4-7 = k, alloc unit 16 << k
  +9  u8 class index into the schema table (FILE-LOCAL, not a global enum)
  +10 u8 ceil(blockBytes / (16 << k)) mod 256      <- the container's self-check
  +11 u8 1 = payload is compressed
```

Block size is the distance to the next **distinct** offset — identical payloads are
deduplicated and share one.

A **descriptor** is `u32 a; u32 count; count × (u32 kind, u32 payloadId)`. The `kind` is
a language or variant selector, which is how one key carries nine translations.

A **payload** is a varint length then UTF-8. Not Latin-1 — the obvious guess, and wrong;
`Zielführung` stores as `…66 c3 bc 68…`, and the Russian and Arabic files settle it.

### Varints — two schemes, and it matters

```
b < lead              -> 1 byte
(b & 0xC0) == lead    -> 2 bytes: (b & 0x3F) << 8 | next
0xC0 <= b < 0xF0      -> 3 bytes: (b & 0x3F) << 16 | next << 8 | next2
b == 0xF0             -> 4 raw big-endian bytes follow
```

`lead` is **`0x80` for lengths, counts, CSize and ordinary scalars**, but **`0x40` for
CPoint components**. Reading a CPoint with the wrong scheme slides the rest of the record
— which is exactly what once made these records look like they carried a variable-length
prefix. On single-field CPoint records, where nothing can be omitted to hide an error,
the CPoint scheme parses **473/473** exactly against 219/473 for the other.

### Language kinds

From the cluster tables, where all ten co-occur:

`1 = de · 2 = en_gb · 3 = en_us · 4 = fr · 5 = es · 6 = it · 7 = nl · 8 = ru · 10 = zh · 11 = ar`

`v4_cluster.mmi` resolves **161 of 161** descriptors in all ten.

## Compression — stock LZRW2

Some payloads are flagged compressed. The codec is **Ross Williams' LZRW2, unmodified
public-domain code**, and Harman's class name says so plainly:
`HBLZRW2Compression.cpp`. The routine at `0x088d0550` matches published `lzrw2.c` line
for line. (`HBLZRW3ACompression.cpp` is a real second codec at `0x088d5cfc`; it is not
what these payloads use.)

**4,810 of 4,810 blocks decode to exactly their declared length** — 13.5 MB in, 22.3 MB
out.

Only the framing is Harman's, and misreading it is what made the algorithm look exotic:

```
varint compressedLen | varint uncompressedLen | u8 codec | LZ stream
```

Three fields. What looks like two more header bytes is the **first control word** —
sixteen zero bits meaning sixteen literals — which is precisely why these blobs appear to
begin with readable text. `headerLen + compressedLen == blobSize` for all 5,212 flagged
blocks.

**Do not trust declared length as an oracle on its own.** Stock LZRW3-A also hits it on
every block while producing

```
von 123123456ungsanfang bis12345678901234ende abfahren
```

where the correct output reads `von Aufzeichnungsanfang bis Aufzeichnungsende abfahren`.
The `123456789012345678` you find in the binary is `START_STRING_18`, the
uninitialised-slot seed leaking through — not a self-test vector.

**402 payloads are left undecoded**, with codec bytes `0x00`/`0x01`/`0x02`/`0x80`/`0x81`,
almost all in `moccaV2Target.mmi`. Their second field cannot be an uncompressed length —
one declares 16 stored bytes expanding to 1,451, which no LZ77 with an 18-byte maximum
match can do — so they are a different record shape, not a different compressor.
Unresolved, and documented as such rather than guessed at.

## Records and geometry

Every class has a schema descriptor:

```
u8 pad ; u8 nBases ; u16 nFields ; u32 classCUID
u32 baseIndices (one byte each, low first) ; u32 moreBases
nFields x { u32 fieldCUID ; u32 typeCode }
```

`ptr + 16 + 8*nFields` lands exactly on the next descriptor for **167 of 167** across the
corpus. A record is its inherited base-class fields first, then its own — no prefix, and
trailing fields may be omitted.

**Class and field names are recoverable, not guessed.** The CUID is a hash of the name,
computed by the routine at VA `0x0889cad8` in PCM3Reload with alternating rounds:
`(h<<7)^c^(h>>3)` on even index, `~((h<<11)^c^(h>>5))` on odd. A class hashes from seed
0; a field hashes its own name — leading dot included — seeded with the class CUID. Two
independent attempts had concluded "not a hash" after testing 83 functions against 1,036
strings; disassembly found it.

Type codes: `< 0x80` = index into *this file's* schema table; `0x81/82/84/88/89` = one
varint; `0x8c` = CPoint; `0x8d` = CSize; `0xa1` = array; `0xa2` = blob; `0xa3` = string.

### ★ Position by reference

A drawable carries both an inline `mPosition` and an `mPositionResID`. **When the ResID
is set, the inline value is `(0,0)` and means nothing** — the real position is behind the
reference, and about one drawable in eight is like this. The reference usually points at
a *descriptor*, holding two CPoint variants under kinds 21 and 22 that share a y and
differ only in x: a left/right anchor pair.

This is worth stating because it is invisible to the obvious checks. Exact-closure does
not see it — the field is consumed either way. Box-plausibility does not see it —
`(0,0)` is on screen. An earlier pass concluded the indirection was used by 3 records out
of 10,268; it is **1,256**, and every one silently rendered in the top-left corner.
**Those two oracles validate parsing, not resolution.**

### ★ Build the tree from `mParentID`, not `m_childrenIDs`

`m_childrenIDs` is an array field and does not decode reliably: child ids of 0 and 8,
nodes listing themselves, 28,951 "children" for one element, 48,312 parents for another.

`mParentID` is a single scalar and comes out clean — **10,259 of 10,268 resolve**, nine
sit at top level, none is self-parented, the busiest node has 67 children. The proof it
is the right linkage is what falls out: an **800×80 bar at the top**, an **800×364
content area at y=59**, an **800×58 bar at y=422** ending precisely at 480.

### Known-good metrics

Display is **800×480**, derived from root records rather than assumed. The text-entry
keyboard reproduces independently in v2, v3 and v4:

```
text field  612x58 @ (16,10)      clear button 152x65 @ (636,7)
keys        74x65,  rows y = 78 / 149 / 220 / 291
row pitch   exactly 71            column pitch exactly 78
x from 12 to 714, right edge 788 <= 800
```

Perfectly regular pitch is not something a misparse produces. Other useful figures: list
rows **664×69**, buttons **66×57**, content area **800×364 at y=59**.

## What this does *not* give you

**No pixels.** Screens come out as labelled boxes. The bitmaps are not in these files —
four `CBitmap` records corpus-wide, all degenerate (`mWidth=0`) — so the graphics live
elsewhere. `CBitmapObject.mBmpResID` points somewhere, and PCM3Reload mentions
`binary MMI archive filename: %s`, so a separate resource archive is the likely home.
Unfound.

**No navigation.** All 36 HMI classes are `NHBHMI::NDrawing::*` — purely presentational.
There is no screen, menu, button, event, action, state or transition class anywhere in
the model. `StateMachine`, `Transition` and `CHBScreen` appear in PCM3Reload as
**compiled code**, not data: MoCCA generates the flow into the binary.

So a `.mmi` is a scene graph, not a UI-flow description. Click-through would need the
state machine — and the cheap way to get that is not disassembly but **enabling the HMI
trace channel and letting the unit narrate its own transitions**; see
`BOOT_ORDER_AND_STARTER.md`.

**No live values.** Even a perfect render draws empty chrome. The station name, the
clock, the phone status all come from the tuner, the RTC and the phone stack — not from
resources.

## What it is good for

- **Every string the unit can display**, in every language, including screens no menu
  reaches — useful for translation work and for finding hidden functionality
- **Matching OEM metrics** when building a custom app, so it looks native rather than
  bolted on
- **Documenting the HMI** without a car
