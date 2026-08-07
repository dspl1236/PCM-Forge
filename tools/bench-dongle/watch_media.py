#!/usr/bin/env python3
"""Poll a set of read identifiers and report anything that CHANGES.

For watching a unit across a state transition -- e.g. pressing MEDIA on the
front panel, which is the only safe request that carries package 11 USB and so
the only thing that should start /sbin/io-usb.

Only identifiers that were STABLE across earlier runs are polled. 21 06 and
21 FE move on every read (counter/clock behaviour seen on three separate runs),
so including them would bury a real transition in noise.

Read-only, and paced: the unit answers 7F xx 21 busyRepeatRequest or nothing to
the first request after a session opens, and hammering it wedges it into
answering nothing at all.

Usage:  py -3 watch_media.py --port COM5 [--seconds 240]
"""
import argparse
import sys
import time

import pcm_slcan as P

WATCH = ["1A9F", "2112", "210A", "210C", "2116", "2100", "211B", "2114"]


def read_one(bus, hx, tries=3, gap=0.3):
    for _ in range(tries):
        P.request(bus, b"\x3E", window=0.4)
        time.sleep(gap)
        r = P.request(bus, bytes.fromhex(hx))
        if r and r[0] != 0x7F:
            return r[2:].hex()
        if r and r[0] == 0x7F and len(r) > 2 and r[2] != 0x21:
            return "NEG%02X" % r[2]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--bitrate", default="6")
    ap.add_argument("--seconds", type=int, default=240)
    a = ap.parse_args()

    bus = P.Slcan(a.port, a.baud, a.bitrate)
    base, changes = {}, 0
    t0 = time.time()
    try:
        P.request(bus, b"\x10\x89", window=1.5)
        print("watching %d identifiers for %ds -- press MEDIA now\n"
              % (len(WATCH), a.seconds))
        rnd = 0
        while time.time() - t0 < a.seconds:
            rnd += 1
            for hx in WATCH:
                v = read_one(bus, hx)
                if v is None:
                    continue
                if hx not in base:
                    base[hx] = v
                    print("  [base] %-6s %s" % (hx, v))
                elif v != base[hx]:
                    changes += 1
                    print("  *** t=%3ds  %-6s CHANGED  %s -> %s"
                          % (int(time.time() - t0), hx, base[hx], v))
                    base[hx] = v
            # keep the session alive between rounds
            P.request(bus, b"\x3E", window=0.4)
        print("\n%d round(s), %d change(s) in %ds" % (rnd, changes, a.seconds))
        if not changes:
            print("nothing moved -- the media request did not alter any of "
                  "these identifiers")
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
