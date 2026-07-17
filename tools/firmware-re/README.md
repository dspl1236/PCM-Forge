# firmware-re — PCM 3.1 firmware extraction & analysis

Host-side Python for pulling `PCM3Root` out of a Porsche field-update package
and analysing it. **No firmware is included here** — these operate on update
archives you supply yourself.

## The extraction chain

```
PCM31<REGION><VER>.rar                    Porsche field-update package
  └─ PCM3_IFS1[_MOPF][_model].ifs         application IFS (LZO1X inside Harman hbcifs)
      └─ inflate  ->  raw QNX imagefs      (PCM4/tools/lzo1x.py, pure Python)
          └─ carve_pcm3root.py  ->  PCM3Root   (~6 MB SH4 LE ELF)
              └─ scan_pcm3root.py  ->  BT/AUX patch verdict
```

## Tools

| file | what it does |
|------|--------------|
| `carve_pcm3root.py` | carve the `PCM3Root` SH4 ELF out of a decompressed IFS1 (finds SH4 LE ELFs, sizes them by program headers, picks the one carrying `CPSoundPresCtrl` + the fallback string). `python carve_pcm3root.py <raw_ifs> <out>` |
| `scan_pcm3root.py` | **portable, dependency-free** — find the universal BT/AUX signature in a `PCM3Root` and report the exact patch verdict (mirrors `bt_fix.c`'s on-car algorithm). `python scan_pcm3root.py <PCM3Root> …` |
| `scan_all_firmware.py` | the full batch harness that produced the 31-build tested matrix (UnRAR × inflate × carve × scan over every package/model). Environment-coupled (Windows + WSL + WinRAR + liblzo2); configured via env vars — see its header. |
| `decompile_keyinput.py` | Ghidra post-script (Jython) that decompiles the `KeyInput` code region so the DSI subscribe/notify `updateId` constants become readable. Run inside Ghidra. |

## Quick start

```sh
# 1. decompress an IFS1 to a raw image (any hbcifs LZO inflater; we ship one)
python ../../PCM4/tools/lzo1x.py PCM3_IFS1_MOPF.ifs raw.img     # (see that tool's usage)

# 2. carve PCM3Root out of it
python carve_pcm3root.py raw.img PCM3Root

# 3. check the BT/AUX boot bug + what bt_fix would do
python scan_pcm3root.py PCM3Root
#   PCM3Root   PATCH (flip 01->07)   FM-map addr=0x082b2a78 byte=0x1
```

## The BT/AUX signature

The "defaults to FM at startup" bug is one instruction that stores the FM
source-index (`1`) into the BT source descriptor. It has a unique 6-byte
signature that is **byte-identical across every region/model/facelift build**
that has the bug — only the address moves:

```
signature :  05 1e 01 e1 15 1e     (SH4 LE: mov.l r?,@(5,Rn); mov #1,r1; mov.l r1,@(5,Rn))
patch     :  the 0x01 at +2  ->  0x07     (FM index -> A2DP index)
```

`scan_pcm3root.py` and the runtime patcher `../sh4-toolchain/bt_fix.c` both key
off this. Full write-up and the 31-build matrix: `research/BT_AUX_BOOT_FIX.md`.

## Copyright

Porsche/Harman firmware is **not** redistributed in this repo. Bring your own
update package (the region/version matching your car). These tools only read and
analyse what you already have.
