#!/usr/bin/env python3
"""PCM-Forge showimg baker -- convert a PNG (or any image) into a raw "PFIM"
blob that showimg.c blits onto the Porsche PCM 3.1 screen. No on-car decode.

Usage:
  python make_img.py in.png out.bin [--format NAME] [--size WxH]
    --format  bgra8888 (default) | argb8888 | rgba8888 | abgr8888 | rgb565
    --size    target WxH (default 480x240 = the component layer). Downscales
              full-screen 800x480 art to fit the safe layer.

The gf_format value is written INTO the blob header, so trying a different
on-car pixel format is a RE-BAKE, not a recompile. The gf_format_t integer
codes below are best-guess -- if the first on-car test shows swapped colors
(the diagnostic image's red<->blue corners will make it obvious), re-bake with
a different --format. Header layout (little-endian, 24 bytes) matches showimg.c:
  u32 magic('PFIM') | u32 width | u32 height | u32 gf_format | u32 stride | u32 bpp
"""
import sys, struct
from PIL import Image

MAGIC = 0x4d494650  # 'PFIM'

# name -> (gf_format_t code [TUNE ON CAR], bytes/pixel, packer(r,g,b,a)->bytes)
FORMATS = {
    "bgra8888": (0x1420, 4, lambda r, g, b, a: bytes((b, g, r, a))),  # ARGB8888 in LE memory
    "argb8888": (0x1520, 4, lambda r, g, b, a: bytes((a, r, g, b))),
    "rgba8888": (0x1620, 4, lambda r, g, b, a: bytes((r, g, b, a))),
    "abgr8888": (0x1720, 4, lambda r, g, b, a: bytes((a, b, g, r))),
    "rgb565":   (0x0565, 2, None),  # handled specially
}

def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    inp, outp = a[0], a[1]
    fmt, size = "bgra8888", (480, 240)
    i = 2
    while i < len(a):
        if a[i] == "--format":
            fmt = a[i + 1].lower(); i += 2
        elif a[i] == "--size":
            w, h = a[i + 1].lower().split("x"); size = (int(w), int(h)); i += 2
        else:
            print("unknown arg:", a[i]); sys.exit(1)
    if fmt not in FORMATS:
        print("bad --format; choose from:", ", ".join(FORMATS)); sys.exit(1)
    gffmt, bpp, pack = FORMATS[fmt]

    img = Image.open(inp).convert("RGBA")
    if size:
        img = img.resize(size, Image.LANCZOS)
    W, H = img.size
    if W > 800 or H > 480:
        print("warning: %dx%d is larger than 800x480" % (W, H))
    px = img.load()
    stride = W * bpp

    body = bytearray()
    if fmt == "rgb565":
        for y in range(H):
            for x in range(W):
                r, g, b, _ = px[x, y]
                body += struct.pack("<H", ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
    else:
        for y in range(H):
            for x in range(W):
                r, g, b, al = px[x, y]
                body += pack(r, g, b, al)

    hdr = struct.pack("<6I", MAGIC, W, H, gffmt, stride, bpp)
    with open(outp, "wb") as f:
        f.write(hdr); f.write(body)
    print("wrote %s: %dx%d %s gffmt=%s stride=%d bpp=%d total=%d bytes"
          % (outp, W, H, fmt, hex(gffmt), stride, bpp, 24 + len(body)))

if __name__ == "__main__":
    main()
