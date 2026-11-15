# USB speed test (PCM 3.1)

Why was Flash Backup so slow? `speed_test.sh` measures reading the flash and writing the USB
stick separately, at several write sizes, and again with the stick remounted `commit=low`.
It needs `bin/fcopy` on the stick (`../sh4-toolchain/fcopy.c`). It writes at most 16 MB per
test, deletes its test files, and puts the stick back to `commit=high` at the end.
Run it from a USB stick as the stick's script, with the stick's root as `$1`.

Results on a 958.2 (15245AS9, November 2026):

| Test | KB/s |
|---|---|
| read flash, 1 MB blocks | 13,107 |
| write stick, 4 KB writes | 7 |
| write stick, 16 KB writes | 30 |
| write stick, 64 KB writes | 112 |
| write stick, 1 MB writes | 910 |
| flash → stick, 1 MB writes | 819 |
| write stick, 16 KB writes, `commit=low` | 176 |
| write stick, 1 MB writes, `commit=low` | 1,170 |
| flash → stick, 1 MB writes, `commit=low` | 1,092 |

Each write costs about half a second at `commit=high` (the PCM's default for sticks),
whatever its size. So write size matters most: Flash Backup now copies in 1 MB writes with
the stick at `commit=low`, taking a backup from 30–40 minutes to about a minute.
