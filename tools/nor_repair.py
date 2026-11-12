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
          against an update disc (an .ISO or an extracted folder).
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

Reading and checking a dump -- the flash map, the chip layouts, the region
checks, disc matching -- is PCM-Explorer's (pcmexplorer/nor.py), which also
shows all of it in its desktop UI. This tool adds only the writing half that
a read-only browser must not have. It needs a PCM-Explorer clone: either
importable, named by the PCM_EXPLORER environment variable, or checked out
next to this PCM-Forge checkout.

HBPERSISTENCE holds this unit's own VIN, activation and coding. Never copy it
from another unit -- splice refuses unless --force-unit-data is given.
"""
import argparse
import json
import os
import sys
from pathlib import Path

EXPLORER_URL = "https://github.com/dspl1236/PCM-Explorer"


def _import_explorer():
    """pcmexplorer.nor (+ UpdateDisc), from wherever a PCM-Explorer clone is."""
    try:
        import pcmexplorer.nor  # noqa: F401
    except ImportError:
        forge = Path(__file__).resolve().parent.parent
        for cand in (os.environ.get("PCM_EXPLORER"),
                     forge.parent / "PCM-Explorer", forge.parent / "pcm-explorer"):
            if cand and (Path(cand) / "pcmexplorer" / "__init__.py").exists():
                sys.path.insert(0, str(cand))
                break
        else:
            sys.exit("nor_repair.py reads dumps with PCM-Explorer, which was not found.\n"
                     "  git clone %s\n"
                     "next to this PCM-Forge checkout, or set PCM_EXPLORER to the clone."
                     % EXPLORER_URL)
    try:
        from pcmexplorer import nor
        from pcmexplorer.updatedisc import UpdateDisc
    except ImportError:
        sys.exit("this PCM-Explorer has no NOR support (pcmexplorer/nor.py) -- "
                 "git pull it to a version from 2026-11 or later.")
    return nor, UpdateDisc


nor, UpdateDisc = _import_explorer()


# ---------------------------------------------------------------- layout file

def layout_for(image_path):
    p = Path(str(image_path) + ".layout.json")
    return tuple(json.loads(p.read_text())["layout"]) if p.exists() else None


def read_layout(path):
    return tuple(json.loads(Path(path).read_text())["layout"])


def write_layout(image_path, layout, chips=None):
    rec = {"layout": list(layout), "description": nor.describe_layout(layout)}
    if chips:
        rec["chip_a"], rec["chip_b"] = map(str, chips)
    Path(str(image_path) + ".layout.json").write_text(json.dumps(rec, indent=2))


def open_image(path, layout=None):
    try:
        return nor.NorImage(path, layout=layout or layout_for(path))
    except (OSError, ValueError) as e:
        sys.exit(str(e))


# ---------------------------------------------------------------- commands

def cmd_merge(args):
    if args.layout:
        layout = read_layout(args.layout)
        chips = []
        for p in (args.chip_a, args.chip_b):
            d = Path(p).read_bytes()
            if hasattr(nor, "normalise_chip"):
                # trims a programmer's wrap-around over-read (32 MB + 256 bytes
                # repeating the chip's start), refuses anything else
                try:
                    d, note = nor.normalise_chip(d, Path(p).name)
                except ValueError as e:
                    sys.exit(str(e))
                if note:
                    print("note: %s" % note)
            elif len(d) != nor.CHIP_SIZE:    # a PCM-Explorer clone from before the trim
                sys.exit("%s: %d bytes, expected %d (one S29GL256N = 32 MB); git pull "
                         "PCM-Explorer to accept a programmer's 256-byte over-read"
                         % (p, len(d), nor.CHIP_SIZE))
            chips.append(d)
        data = nor.combine(chips, layout)
        print("layout (given): %s" % nor.describe_layout(layout))
    else:
        try:
            img = nor.NorImage.from_chips(args.chip_a, args.chip_b)
        except (OSError, ValueError) as e:
            sys.exit(str(e))
        layout, data = img.layout, img.data
        for note in getattr(img, "notes", []):
            print("note: %s" % note)
        print("layout: %d region headers in place (%d expected) -> %s"
              % (img.layout_score, nor.PROBES_EXPECTED, nor.describe_layout(layout)))
        if len(img.layout_ties) > 1:
            print("warning: several layouts fit equally well:",
                  *map(nor.describe_layout, img.layout_ties), sep="\n  ")
    Path(args.output).write_bytes(data)
    write_layout(args.output, layout, (args.chip_a, args.chip_b))
    print("wrote %s (%d bytes) and %s.layout.json" % (args.output, len(data), args.output))


def cmd_check(args):
    img = open_image(args.image)
    matches = None
    if args.disc:
        print("matching against %s ..." % args.disc)
        try:
            disc = UpdateDisc(args.disc)
            try:
                matches = img.match_disc(disc)
            finally:
                disc.close()
        except Exception as e:
            sys.exit("could not read the disc: %s" % e)
    print("%s: %s" % (args.image, img.describe()))
    for r in img.regions:
        img.check(r)
        print("  %-14s 0x%07X  %-10s %s" % (r.name, r.start, r.status, r.detail))
        if matches is not None:
            m = matches.get(r.name)
            print("%32sdisc: %s" % ("", nor.compact_matches(m) if m else "no match"))
    bad = [r.name for r in img.regions if r.status == "BAD"]
    print("result:", "BAD: " + ", ".join(bad) if bad else "all self-checking regions good")
    return 1 if bad else 0


def cmd_splice(args):
    img = open_image(args.image)
    r = img.region(args.region)
    if r is None:
        sys.exit("unknown region %s; one of %s"
                 % (args.region, ", ".join(x.name for x in img.regions)))
    if r.unit and not args.force_unit_data:
        sys.exit("%s holds this unit's own VIN, activation and coding -- refusing to "
                 "overwrite it (pass --force-unit-data only if you know why)" % r.name)
    if r.name == "IPL" and not args.force_ipl:
        sys.exit("IPL is the bootloader; a bad IPL means no boot at all. "
                 "Pass --force-ipl to replace it.")

    if args.donor:
        donor = Path(args.donor).read_bytes()
        if len(donor) != nor.FULL_SIZE:
            sys.exit("%s: donor must be a merged %d-byte image" % (args.donor, nor.FULL_SIZE))
        new, src = donor[r.start:r.end], "donor %s" % args.donor
    else:
        new, src = Path(args.with_image).read_bytes(), args.with_image
        if len(new) > r.size:
            sys.exit("%s: %d bytes does not fit %s (%d bytes)" % (src, len(new), r.name, r.size))

    old = img.region_bytes(r)
    data = bytearray(img.data)
    data[r.start:r.start + len(new)] = new
    if not args.no_pad:                       # as the erase before a write leaves it
        data[r.start + len(new):r.end] = b"\xff" * (r.size - len(new))
    out = nor.NorImage(args.output, data=bytes(data), layout=img.layout)
    r2 = out.check(out.region(r.name))
    # only this region changed, so a failure here is the replacement's own
    if r2.status == "BAD":
        sys.exit("replacement %s fails its own check: %s" % (src, r2.detail))

    diffs = [i for i, (x, y) in enumerate(zip(old, data[r.start:r.end])) if x != y]
    print("%s: replaced from %s; %d bytes changed; now %s: %s"
          % (r.name, src, len(diffs), r2.status, r2.detail))
    # Where the changed bytes were tells you which chip is failing. Only
    # meaningful when the replacement is the same build as what was there.
    if diffs and len(diffs) <= 64:
        for i in diffs:
            loc = ""
            if img.layout:
                c, off = nor.chip_location(r.start + i, img.layout)
                loc = "  (chip %s offset 0x%07X)" % ("AB"[c], off)
            print("  0x%07X: %02X -> %02X%s" % (r.start + i, old[i], data[r.start + i], loc))
    elif diffs and img.layout:
        per = [0, 0]
        for i in diffs:
            per[nor.chip_location(r.start + i, img.layout)[0]] += 1
        print("  changed bytes per chip: A %d, B %d (a different build changes most "
              "bytes; a few flips on one chip points at that chip)" % tuple(per))
    Path(args.output).write_bytes(bytes(data))
    if img.layout:
        write_layout(args.output, img.layout)
    print("wrote %s" % args.output)


def cmd_split(args):
    img = Path(args.image).read_bytes()
    if len(img) != nor.FULL_SIZE:
        sys.exit("%s: %d bytes, expected %d" % (args.image, len(img), nor.FULL_SIZE))
    layout = read_layout(args.layout) if args.layout else layout_for(args.image)
    if not layout:
        sys.exit("no %s.layout.json -- pass --layout from the merge step" % args.image)
    a, b = nor.separate(img, layout)
    assert nor.combine([a, b], layout) == img
    Path(args.output[0]).write_bytes(a)
    Path(args.output[1]).write_bytes(b)
    print("layout %s\nwrote chip A -> %s, chip B -> %s"
          % (nor.describe_layout(layout), args.output[0], args.output[1]))
    print("program each file to the SAME physical chip its original dump came from")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("merge", help="two chip dumps -> one 64 MB image")
    p.add_argument("chip_a")
    p.add_argument("chip_b")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--layout", help="reuse a .layout.json instead of auto-detecting")
    p.set_defaults(fn=cmd_merge)

    p = sub.add_parser("check", help="verify every region of a merged image")
    p.add_argument("image")
    p.add_argument("--disc", help="update disc (.ISO or extracted folder) to match regions")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("splice", help="replace one region with a known-good copy")
    p.add_argument("image")
    p.add_argument("region", help="IFS1, IFS2, EMERGENCY, FPGA, ...")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", dest="with_image", help="OEM image file, e.g. PCM3_IFS2.ifs")
    src.add_argument("--donor", help="merged image of a donor unit (same build!)")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--no-pad", action="store_true",
                   help="keep old bytes after the new image instead of 0xFF")
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
