#!/usr/bin/env python3
"""Parse the PCM's DCL diagnostic description (diagnosis.cfg).

PCM3Reload does not implement KWP services in code -- its class list is a set of
interpreter nodes (CRBDiagService, CRBDiagCalculate, CRBDiagTable, CRBDiagConst,
CRBDiagSelect, each with an onDispatch) walking a description. diagnosis.cfg is
that description, and its header names an ODXCheck entry, so the services --
including SecurityAccess -- are data rather than compiled logic.

Format is a stream of length-prefixed ASCII: u16 little-endian length, then that
many bytes, with binary tag bytes in between. ("DCLVersion = 2" is 14 = 0x0E00.)

    python dclparse.py                 every string, in file order
    python dclparse.py --grep sec      only strings matching
"""
import argparse
import io
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
DEFAULT = r"D:\PCM\ifs2_rootfs\mnt\ifs_app\HBproject\diagnosis.cfg"


def strings(d):
    """(offset, text) for each length-prefixed ASCII run."""
    out, i, n = [], 0, len(d)
    while i + 2 <= n:
        ln = struct.unpack_from("<H", d, i)[0]
        if 3 <= ln <= 512 and i + 2 + ln <= n:
            s = d[i + 2:i + 2 + ln]
            if all(32 <= c < 127 or c in (9,) for c in s):
                out.append((i, s.decode("ascii")))
                i += 2 + ln
                continue
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT)
    ap.add_argument("--grep")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--context", type=int, default=0,
                    help="also show N strings either side of a --grep hit")
    a = ap.parse_args()

    d = open(a.file, "rb").read()
    ss = strings(d)
    print("%s: %d bytes, %d strings\n" % (os.path.basename(a.file), len(d),
                                          len(ss)))
    if a.grep:
        rx = re.compile(a.grep, re.I)
        hits = [i for i, (_, s) in enumerate(ss) if rx.search(s)]
        print("%d matches for %r\n" % (len(hits), a.grep))
        shown = set()
        for h in hits:
            lo = max(0, h - a.context)
            hi = min(len(ss), h + a.context + 1)
            for j in range(lo, hi):
                if j in shown:
                    continue
                shown.add(j)
                off, s = ss[j]
                print("   %06X %s%s" % (off, "* " if j == h else "  ", s))
            if a.context:
                print()
        return 0

    for k, (off, s) in enumerate(ss):
        if a.limit and k >= a.limit:
            print("   ... %d more" % (len(ss) - a.limit))
            break
        print("   %06X  %s" % (off, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
