#!/usr/bin/env python3
"""nor_repair.py -- check and repair a PCM 3.1 NOR flash dump taken off the
two chips with an external programmer.

The PCM 3.1 (DPEC board) carries its whole flash in two 32 MB Spansion
S29GL256N chips that together form one 64 MB /dev/fs0. This tool never talks
to hardware: it reads the two chip dumps, works on files, and writes new chip
files for you to program yourself.

  merge   two chip dumps -> one 64 MB image (layout auto-detected, saved
          next to the image as <image>.layout.json)
  check   walk every region of a merged image and say whether it is intact.
          IFS1/Emergency and IFS2 checksum themselves, so this works even on a
          build we have no update disc for. --disc also matches each region
          against the OEM CRC records of an extracted update disc.
  splice  replace ONE region with a known-good copy (an OEM .ifs file or the
          same region of a donor image). Unit-specific regions are refused.
  split   merged image -> two chip files, the exact inverse of merge.

Typical repair (corrupt IFS2):

  python nor_repair.py merge chipA.bin chipB.bin -o mine.bin
  python nor_repair.py check mine.bin
  python nor_repair.py splice mine.bin IFS2 --image PCM3_IFS2.ifs -o fixed.bin
  python nor_repair.py check fixed.bin
  python nor_repair.py split fixed.bin -o fixedA.bin fixedB.bin
  # keep the original dumps; program fixedA/fixedB to the same chips they came from

Flash map (from the ADR<address> folders of the OEM update disc):

  0x0000000 IPL          0x0100000 FPGA         0x01C0000 IFS1
  0x0BC0000 EMERGENCY    0x0FC0000 IFS2         0x3000000 HBPERSISTENCE
  0x3F00000 UPDATEHISTORY
  (the no-HDD LOW variant has DEBUG at 0x2B40000 and HBPERSISTENCE at 0x2E00000)

HBPERSISTENCE holds this unit's own VIN, activation and coding. Never copy it
from another unit -- splice refuses unless --force-unit-data is given.
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "PCM4" / "tools"))
from lzo1x import decompress_stream  # noqa: E402  (pure Python, MIT, same author)

CHIP_SIZE = 32 * 1024 * 1024
FULL_SIZE = 2 * CHIP_SIZE

QNX_STARTUP = b"\xeb\x7e\xff\x00"     # startup_header signature 0x00ff7eeb (LE)
HBCIFS = b"hbcifs\x00\x00"
EFS = b"\x10\x00\x4c\xff"
FPGA = b".HDG"

# name, start, end, magic (None = no magic known), unit_specific
MAP_STD = [
    ("IPL",           0x0000000, 0x0100000, None,        False),
    ("FPGA",          0x0100000, 0x01C0000, FPGA,        False),
    ("IFS1",          0x01C0000, 0x0BC0000, QNX_STARTUP, False),
    ("EMERGENCY",     0x0BC0000, 0x0FC0000, QNX_STARTUP, False),
    ("IFS2",          0x0FC0000, 0x3000000, HBCIFS,      False),
    ("HBPERSISTENCE", 0x3000000, 0x3F00000, EFS,         True),
    ("UPDATEHISTORY", 0x3F00000, 0x4000000, EFS,         True),
]
MAP_LOW = [
    ("IPL",           0x0000000, 0x0100000, None,        False),
    ("FPGA",          0x0100000, 0x01C0000, FPGA,        False),
    ("IFS1",          0x01C0000, 0x0BC0000, QNX_STARTUP, False),
    ("EMERGENCY",     0x0BC0000, 0x0FC0000, QNX_STARTUP, False),
    ("IFS2",          0x0FC0000, 0x2B40000, HBCIFS,      False),
    ("DEBUG",         0x2B40000, 0x2E00000, EFS,         True),
    ("HBPERSISTENCE", 0x2E00000, 0x3F00000, EFS,         True),
    ("UPDATEHISTORY", 0x3F00000, 0x4000000, EFS,         True),
]
# Every magic both maps share, used to score candidate layouts.
PROBES = [(0x0100000, FPGA), (0x01C0000, QNX_STARTUP), (0x0BC0000, QNX_STARTUP),
          (0x0FC0000, HBCIFS), (0x3000000, EFS), (0x2E00000, EFS), (0x3F00000, EFS)]


def flash_map(img):
    return MAP_LOW if img[0x2E00000:0x2E00004] == EFS and img[0x3000000:0x3000004] != EFS else MAP_STD


# ---------------------------------------------------------------- layouts
# A layout is (kind, width, first, swap16):
#   kind "interleave": units of `width` bytes alternate between the chips,
#                      chip `first` supplies the lower address of each pair
#   kind "concat":     chip `first` is the low 32 MB, the other the high 32 MB
#   swap16:            each chip dump has its bytes swapped within 16-bit
#                      words (some programmers read x16 parts big-endian)

def _swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def combine(chips, layout):
    kind, width, first, swap = layout
    a, b = chips[first], chips[1 - first]
    if swap:
        a, b = _swap16(a), _swap16(b)
    if kind == "concat":
        return a + b
    out = bytearray(len(a) + len(b))
    step = 2 * width
    for k in range(width):
        out[k::step] = a[k::width]
        out[width + k::step] = b[k::width]
    return bytes(out)


def separate(img, layout):
    kind, width, first, swap = layout
    half = len(img) // 2
    if kind == "concat":
        a, b = img[:half], img[half:]
    else:
        a, b = bytearray(half), bytearray(half)
        step = 2 * width
        for k in range(width):
            a[k::width] = img[k::step]
            b[k::width] = img[width + k::step]
        a, b = bytes(a), bytes(b)
    if swap:
        a, b = _swap16(a), _swap16(b)
    chips = [None, None]
    chips[first], chips[1 - first] = a, b
    return chips


def candidate_layouts():
    for swap in (False, True):
        for first in (0, 1):
            yield ("concat", 0, first, swap)
            for width in (1, 2, 4):
                yield ("interleave", width, first, swap)


def score(chips, layout):
    """Count the known magics a layout puts in the right place, without
    building the full image: fetch just the probed bytes."""
    kind, width, first, swap = layout
    hits = 0
    for addr, magic in PROBES:
        got = bytearray()
        for i in range(len(magic)):
            p = addr + i
            if kind == "concat":
                c, off = (first, p) if p < CHIP_SIZE else (1 - first, p - CHIP_SIZE)
            else:
                unit, within = divmod(p, width)
                c = first if unit % 2 == 0 else 1 - first
                off = (unit // 2) * width + within
            if swap:
                off ^= 1
            got.append(chips[c][off])
        hits += bytes(got) == magic
    return hits


def describe(layout):
    kind, width, first, swap = layout
    names = "AB"[first] + "AB"[1 - first]
    s = f"concat ({names[0]} low, {names[1]} high)" if kind == "concat" else \
        f"{width * 8}-bit interleave ({names[0]} at even units)"
    return s + (", 16-bit byte swap" if swap else "")


def chip_location(addr, layout):
    """Which input chip, and where in it, a flash address came from."""
    kind, width, first, swap = layout
    if kind == "concat":
        c, off = (first, addr) if addr < CHIP_SIZE else (1 - first, addr - CHIP_SIZE)
    else:
        unit, within = divmod(addr, width)
        c = first if unit % 2 == 0 else 1 - first
        off = (unit // 2) * width + within
    if swap:
        off ^= 1
    return "AB"[c], off


# ---------------------------------------------------------------- checks

def wordsum(buf):
    n = len(buf) // 4 * 4
    try:
        import numpy as np
        return int(np.frombuffer(buf[:n], "<u4").sum(dtype=np.uint64) & 0xFFFFFFFF)
    except ImportError:
        return sum(struct.unpack(f"<{n // 4}I", buf[:n])) & 0xFFFFFFFF


def check_region(img, name, start, end, magic):
    """Return (status, detail, used_len). status: OK / BAD / ERASED / UNVERIFIED."""
    reg = img[start:end]
    if reg.count(0xFF) == len(reg):
        return "ERASED", "all 0xFF", 0
    if magic is not None and reg[:len(magic)] != magic:
        return "BAD", f"expected magic {magic.hex()} at 0x{start:07X}, found {reg[:8].hex()}", 0

    if magic == QNX_STARTUP:
        stored = struct.unpack_from("<I", reg, 0x24)[0]
        if not 0 < stored <= len(reg):
            return "BAD", f"startup stored_size 0x{stored:X} does not fit the region", 0
        s = wordsum(reg[:stored])
        if s:
            return "BAD", f"QNX word checksum over 0x{stored:X} bytes is 0x{s:08X}, must be 0", stored
        return "OK", f"QNX image 0x{stored:X} bytes, checksum good", stored

    if magic == HBCIFS:
        dsize, csize = struct.unpack_from("<II", reg, 8)
        if not 0 < csize <= len(reg) - 0x40:
            return "BAD", f"hbcifs compressed size 0x{csize:X} does not fit the region", 0
        out, ip, why = decompress_stream(reg, 0x40)
        used = 0x40 + csize
        if why.startswith("error") or len(out) != dsize:
            at = start + ip
            return "BAD", (f"LZO stream broke ({why}) after {len(out):,} of {dsize:,} bytes; "
                           f"input stopped at flash 0x{at:07X} -- the damage is at or a little "
                           f"before that address"), used
        isz = struct.unpack_from("<I", out, 8)[0] if out[:7] == b"imagefs" else 0
        if not isz:
            return "BAD", "decompressed data does not start with an imagefs header", used
        s = wordsum(bytes(out[:isz]))
        if s:
            return "BAD", f"decompressed imagefs word checksum is 0x{s:08X}, must be 0", used
        return "OK", f"hbcifs {csize:,} -> {dsize:,} bytes, decompresses and checksums", used

    if magic == EFS:
        return "UNVERIFIED", "QNX EFS (flash filesystem); no image checksum to test", 0
    return "UNVERIFIED", "no self-check known; use --disc to compare with an OEM image", 0


def load_disc(disc):
    """{start_address: [(crc, length, label)]} from <disc>/*/HEADUNIT/CRC/*.CRC32."""
    recs = {}
    for f in Path(disc).rglob("*.CRC32"):
        for line in f.read_text(errors="replace").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if line.startswith("#") or len(parts) != 4 or not parts[0].startswith("/dev/fs0"):
                continue
            try:
                start, length, crc = (int(p, 16) for p in parts[1:])
            except ValueError:
                continue
            label = f"{f.parent.parent.parent.name}/{f.stem}"
            recs.setdefault(start, []).append((crc, length, label))
    # The disc has no CRC record for some regions (IPL, FPGA): hash the image
    # files in the ADR<address> folders themselves.
    for d in Path(disc).rglob("ADR*"):
        try:
            start = int(d.name[3:], 16)
        except ValueError:
            continue
        for f in d.iterdir():
            if f.is_file():
                data = f.read_bytes()
                label = f"{d.parent.parent.name}/{f.name}"
                recs.setdefault(start, []).append((zlib.crc32(data), len(data), label))
    return recs


def disc_match(img, start, end, recs):
    hits, seen = [], {}
    for crc, length, label in recs.get(start, []):
        if start + length > end:
            continue
        if length not in seen:
            seen[length] = zlib.crc32(img[start:start + length])
        if seen[length] == crc:
            hits.append(label)
    return sorted(set(hits))


# ---------------------------------------------------------------- commands

def read_chips(pa, pb):
    a, b = Path(pa).read_bytes(), Path(pb).read_bytes()
    for p, d in ((pa, a), (pb, b)):
        if len(d) != CHIP_SIZE:
            sys.exit(f"{p}: {len(d):,} bytes, expected {CHIP_SIZE:,} (one S29GL256N = 32 MB)")
    return [a, b]


def cmd_merge(args):
    chips = read_chips(args.chip_a, args.chip_b)
    if args.layout:
        layout = tuple(json.loads(Path(args.layout).read_text())["layout"])
        best = score(chips, layout)
    else:
        ranked = sorted(((score(chips, l), l) for l in candidate_layouts()), key=lambda t: -t[0])
        best, layout = ranked[0]
        ties = [l for s, l in ranked if s == best]
        print(f"layout: {best} region magics in place (6 expected) -> {describe(layout)}")
        if best < 4:
            sys.exit("no layout puts the region magics in place -- are these both chips of a PCM 3.1?")
        if len(ties) > 1:
            print("warning: several layouts score the same:", *map(describe, ties), sep="\n  ")
    img = combine(chips, layout)
    assert separate(img, layout) == chips, "layout does not round-trip"
    Path(args.output).write_bytes(img)
    Path(args.output + ".layout.json").write_text(json.dumps(
        {"layout": list(layout), "description": describe(layout),
         "chip_a": str(args.chip_a), "chip_b": str(args.chip_b)}, indent=2))
    print(f"wrote {args.output} ({len(img):,} bytes) and {args.output}.layout.json")


def layout_for(image_path):
    p = Path(str(image_path) + ".layout.json")
    return tuple(json.loads(p.read_text())["layout"]) if p.exists() else None


def cmd_check(args):
    img = Path(args.image).read_bytes()
    if len(img) != FULL_SIZE:
        sys.exit(f"{args.image}: {len(img):,} bytes, expected {FULL_SIZE:,}")
    layout = layout_for(args.image)
    recs = load_disc(args.disc) if args.disc else {}
    fmap = flash_map(img)
    print(f"{args.image}: {'LOW (no-HDD) map' if fmap is MAP_LOW else 'standard map'}"
          + (f", layout {describe(layout)}" if layout else ""))
    bad = 0
    for name, start, end, magic, unit in fmap:
        status, detail, _ = check_region(img, name, start, end, magic)
        line = f"  {name:<14} 0x{start:07X}  {status:<10} {detail}"
        if recs:
            hits = disc_match(img, start, end, recs)
            line += f"\n{'':32}OEM match: {', '.join(hits)}" if hits else \
                f"\n{'':32}OEM match: none on this disc"
        print(line)
        if status == "BAD":
            bad += 1
            if layout and "flash 0x" in detail:
                at = int(detail.split("flash 0x")[1].split()[0], 16)
                chip, off = chip_location(at, layout)
                print(f"{'':32}that address is chip {chip} offset 0x{off:07X}")
    print("result:", "all self-checking regions good" if not bad else f"{bad} region(s) BAD")
    return 1 if bad else 0


def cmd_splice(args):
    img = bytearray(Path(args.image).read_bytes())
    fmap = flash_map(img)
    regs = {r[0]: r for r in fmap}
    name = args.region.upper()
    if name not in regs:
        sys.exit(f"unknown region {args.region}; one of {', '.join(regs)}")
    _, start, end, magic, unit = regs[name]
    if unit and not args.force_unit_data:
        sys.exit(f"{name} holds this unit's own VIN, activation and coding -- refusing to "
                 f"overwrite it (pass --force-unit-data only if you know why)")
    if name == "IPL" and not args.force_ipl:
        sys.exit("IPL is the bootloader; a bad IPL means no boot at all. Pass --force-ipl to replace it.")

    if args.donor:
        donor = Path(args.donor).read_bytes()
        if len(donor) != FULL_SIZE:
            sys.exit(f"{args.donor}: donor must be a merged {FULL_SIZE:,}-byte image")
        new = donor[start:end]
        src = f"donor {args.donor}"
    else:
        new = Path(args.with_image).read_bytes()
        src = args.with_image
        if len(new) > end - start:
            sys.exit(f"{src}: {len(new):,} bytes does not fit {name} ({end - start:,} bytes)")
    status, detail, _ = check_region(new + b"\xff" * (end - start - len(new)), name, 0, end - start, magic)
    if status == "BAD":
        sys.exit(f"replacement {src} fails its own check: {detail}")

    old = bytes(img[start:end])
    img[start:start + len(new)] = new
    if not args.no_pad:
        img[start + len(new):end] = b"\xff" * (end - start - len(new))  # as the erase leaves it
    status, detail, _ = check_region(bytes(img), name, start, end, magic)
    diffs = [i for i, (x, y) in enumerate(zip(old, img[start:end])) if x != y]
    print(f"{name}: replaced from {src}; {len(diffs):,} bytes changed; now {status}: {detail}")
    # Where the changed bytes were tells you which chip is failing. Only
    # meaningful when the replacement is the same build as what was there.
    layout = layout_for(args.image)
    if diffs and len(diffs) <= 64:
        for i in diffs:
            loc = ""
            if layout:
                chip, off = chip_location(start + i, layout)
                loc = f"  (chip {chip} offset 0x{off:07X})"
            print(f"  0x{start + i:07X}: {old[i]:02X} -> {img[start + i]:02X}{loc}")
    elif diffs and layout:
        per = {"A": 0, "B": 0}
        for i in diffs:
            per[chip_location(start + i, layout)[0]] += 1
        print(f"  changed bytes per chip: A {per['A']:,}, B {per['B']:,} "
              f"(a different build changes most bytes; a few flips on one chip points at that chip)")
    Path(args.output).write_bytes(img)
    lay = Path(str(args.image) + ".layout.json")
    if lay.exists():
        Path(args.output + ".layout.json").write_text(lay.read_text())
    print(f"wrote {args.output}")


def cmd_split(args):
    img = Path(args.image).read_bytes()
    if len(img) != FULL_SIZE:
        sys.exit(f"{args.image}: {len(img):,} bytes, expected {FULL_SIZE:,}")
    layout = tuple(json.loads(Path(args.layout).read_text())["layout"]) if args.layout \
        else layout_for(args.image)
    if not layout:
        sys.exit(f"no {args.image}.layout.json -- pass --layout from the merge step")
    a, b = separate(img, layout)
    assert combine([a, b], layout) == img
    Path(args.output[0]).write_bytes(a)
    Path(args.output[1]).write_bytes(b)
    print(f"layout {describe(layout)}\nwrote chip A -> {args.output[0]}, chip B -> {args.output[1]}")
    print("program each file to the SAME physical chip its original dump came from")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("merge", help="two chip dumps -> one 64 MB image")
    p.add_argument("chip_a"); p.add_argument("chip_b")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--layout", help="reuse a .layout.json instead of auto-detecting")
    p.set_defaults(fn=cmd_merge)

    p = sub.add_parser("check", help="verify every region of a merged image")
    p.add_argument("image")
    p.add_argument("--disc", help="extracted OEM update disc folder, to match regions by CRC")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("splice", help="replace one region with a known-good copy")
    p.add_argument("image"); p.add_argument("region", help="IFS1, IFS2, EMERGENCY, FPGA, ...")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", dest="with_image", help="OEM image file, e.g. PCM3_IFS2.ifs")
    src.add_argument("--donor", help="merged image of a donor unit (same build!)")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--no-pad", action="store_true", help="keep old bytes after the new image instead of 0xFF")
    p.add_argument("--force-unit-data", action="store_true")
    p.add_argument("--force-ipl", action="store_true")
    p.set_defaults(fn=cmd_splice)

    p = sub.add_parser("split", help="merged image -> two chip files")
    p.add_argument("image")
    p.add_argument("-o", "--output", nargs=2, required=True, metavar=("CHIP_A", "CHIP_B"))
    p.add_argument("--layout", help=".layout.json from merge (default: <image>.layout.json)")
    p.set_defaults(fn=cmd_split)

    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
