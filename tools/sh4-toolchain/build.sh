#!/bin/bash
# ============================================================================
# PCM-Forge SH4/QNX cross-build -- turn one .c into a runnable QNX SH4 binary
# using ONLY the Linux sh4-linux-gnu toolchain + SONAME stub libs. No QNX SDK.
#
# How it works: the PCM's real libc.so.2 / libgf.so.1 are symbol-stripped, so we
# link against tiny STUB shared objects that export just the names + SONAME. At
# load time ldqnx.so.2 on the unit binds those imports to the real libraries.
# A bare crt.S provides _start (argc/argv off the stack -> main -> _exit).
#
# Usage:   ./build.sh <source.c> [output_name]
# Example: ./build.sh app_oil.c        # -> ./app_oil  (QNX SH4 LE ELF)
#          ./build.sh bt_fix.c
#
# Requires: gcc-sh4-linux-gnu + binutils  (Debian/Ubuntu/WSL:
#           sudo apt install gcc-sh4-linux-gnu)
# The libgf stub is added automatically when the source calls gf_* (graphics).
# ============================================================================
set -eu
SRC="${1:?usage: build.sh <source.c> [output_name]}"
OUT="${2:-$(basename "${SRC%.c}")}"
CC="${CC:-sh4-linux-gnu-gcc}"
LD="${LD:-sh4-linux-gnu-ld}"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p stub
# stub libc.so.2 -- names + SONAME only (bound to the real libc.so.2 on the PCM)
"$CC" -shared -nostdlib -fPIC -Wl,-soname,libc.so.2 "$HERE/stub_libc.c" -o stub/libc.so.2
LIBS="stub/libc.so.2"

# add the libgf stub only if the program draws (uses gf_* from libgf.so.1)
if grep -q 'gf_' "$SRC"; then
  "$CC" -shared -nostdlib -fPIC -Wl,-soname,libgf.so.1 "$HERE/stub_libgf.c" -o stub/libgf.so.1
  LIBS="$LIBS stub/libgf.so.1"
  echo "[build] libgf stub included (source uses gf_*)"
fi

"$CC" -c -O2 -fno-stack-protector -ffreestanding -fno-builtin "$SRC" -o "${OUT}.o"
"$CC" -c "$HERE/crt.S" -o crt.o
"$LD" -o "$OUT" -e _start --dynamic-linker=/usr/lib/ldqnx.so.2 crt.o "${OUT}.o" $LIBS

echo "[build] $OUT:"
file "$OUT" | cut -d: -f2-
readelf -h "$OUT" 2>/dev/null | grep -iE "Machine|Type:"
echo "[build] imports (bound on-car):"
readelf --dyn-syms "$OUT" 2>/dev/null | grep UND | awk '{print $8}' | sort -u | tr '\n' ' '; echo
echo "[build] size: $(ls -la "$OUT" | awk '{print $5}') bytes"
echo "[build] deploy: copy '$OUT' to a FAT32 USB, run from the PCM shell as root."
