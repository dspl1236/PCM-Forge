#!/usr/bin/env python3
"""Diff two CAN captures to find which bytes carry a signal.

    python candiff.py baseline.log changed.log
    python candiff.py baseline.log changed.log --id 539

There is no published message catalogue for this bus and none in the firmware
-- searching the binaries for the ids finds only coincidence, because a 2-byte
value occurs by chance every 64KB and several of the ids are consecutive, so
font tables and Unicode data match. Decoding is therefore experimental: change
exactly one thing, capture again, and see what moved.

Reports three kinds of difference, because they mean different things:

  APPEARED / VANISHED   an id present in one capture only -- a module started,
                        stopped, or changed mode
  CHANGED               a byte whose value set differs -- the signal itself
  WIDENED               a byte static in one capture and varying in the other,
                        which usually means the thing it measures became live

Ignores bytes that vary in BOTH captures: a free-running counter moves whatever
you do and is never the signal you are hunting.
"""
import argparse
import sys
from collections import defaultdict


def load(path):
    """id -> list of payload hex strings, in order."""
    out = defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.split()
            if len(p) >= 4:
                out[p[1].upper()].append(p[3])
    return out


def byte_sets(frames):
    """position -> set of values seen there."""
    n = max((len(f) for f in frames), default=0) // 2
    return [{f[i * 2:i * 2 + 2] for f in frames if len(f) >= i * 2 + 2}
            for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--id", help="restrict to one CAN id")
    ap.add_argument("--quiet-counters", action="store_true", default=True,
                    help="skip bytes that vary in both captures (default)")
    a = ap.parse_args()

    b, c = load(a.before), load(a.after)
    ids = sorted(set(b) | set(c))
    if a.id:
        ids = [i for i in ids if i == a.id.upper()]

    print("before: %s  (%d ids, %d frames)"
          % (a.before, len(b), sum(len(v) for v in b.values())))
    print("after : %s  (%d ids, %d frames)\n"
          % (a.after, len(c), sum(len(v) for v in c.values())))

    gone = [i for i in ids if i in b and i not in c]
    new = [i for i in ids if i in c and i not in b]
    if new:
        print("APPEARED : " + " ".join(new))
    if gone:
        print("VANISHED : " + " ".join(gone))
    if new or gone:
        print()

    hits = 0
    for cid in ids:
        if cid not in b or cid not in c:
            continue
        sb, sc = byte_sets(b[cid]), byte_sets(c[cid])
        lines = []
        for i in range(min(len(sb), len(sc))):
            if sb[i] == sc[i]:
                continue
            varies_both = len(sb[i]) > 1 and len(sc[i]) > 1
            if varies_both and a.quiet_counters:
                continue
            kind = "WIDENED" if len(sb[i]) == 1 and len(sc[i]) > 1 else \
                   "NARROWED" if len(sb[i]) > 1 and len(sc[i]) == 1 else \
                   "CHANGED"
            fmt = lambda s: ",".join(sorted(s)[:4]) + \
                ("+%d" % (len(s) - 4) if len(s) > 4 else "")
            lines.append("    byte %d  %-8s %-22s -> %s"
                         % (i, kind, fmt(sb[i]), fmt(sc[i])))
        if lines:
            hits += 1
            print("%s   (%d -> %d frames)" % (cid, len(b[cid]), len(c[cid])))
            print("\n".join(lines))
    if not hits and not new and not gone:
        print("No differences outside continuously-varying bytes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
