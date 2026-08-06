#!/usr/bin/env python3
"""Check the decoded diagnosis.cfg model against a live PCM.

Everything in the DCL model so far -- the RPN operator semantics, the operand
binding, the node map -- is internally consistent and reproduces recognisable
idioms, but has never been put to a real unit. This asks the unit.

The predictions come from the code-8 KWP service table: each request below
reaches an expression whose constants are known, so the *shape* of the answer
is constrained even though its dynamic input is live vehicle state.

    21 0A   (v < 0) ? 1 : 0     a sign test -- the answer must be 0 or 1
    21 06   v % 100             a remainder -- the answer must be 0..99
    21 F4   v & 0x10            a bit test  -- the answer must be 0 or 16

All three are reads. Nothing here writes, starts a routine, or changes state:
the 0x31 (routineControl) and 0x3B (writeDataByLocalIdentifier) entries in the
same table are deliberately not touched.

READ THE RESULT HONESTLY. Reachability proves the expression is downstream of
the request, not that its value is what the response carries -- there may be
formatting or selection after it. A hit is evidence. A miss is inconclusive,
not a refutation, and is reported as such rather than as a failure.

Usage:  py -3 dcl_validate.py --port COM5
"""
import argparse
import sys

import pcm_slcan as P

# (request hex, human description, predicate over the payload's trailing bytes)
CHECKS = [
    ("210A", "(v < 0) ? 1 : 0   -- sign test",
     lambda v: all(b in (0, 1) for b in v), "every byte 0 or 1"),
    ("2106", "v % 100           -- remainder",
     lambda v: all(b <= 99 for b in v), "every byte <= 99"),
    ("21F4", "v & 0x10          -- bit test",
     lambda v: all(b in (0, 16) for b in v), "every byte 0 or 16"),
    ("210C", "average of two inputs -- no offline prediction",
     None, "(informational only)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--bitrate", default="6")
    a = ap.parse_args()

    bus = P.Slcan(a.port, a.baud, a.bitrate)
    print("slcan open on %s at 500 kbps" % a.port)
    print("predictions come from diagnosis.cfg; all requests are reads\n")
    hit = miss = noresp = 0
    try:
        P.step(bus, "1089", "open manufacturer session")
        print()
        for req, desc, pred, why in CHECKS:
            r = P.request(bus, bytes.fromhex(req))
            if not r:
                print("  %-6s %-42s no response" % (req, desc))
                noresp += 1
                continue
            if r[0] == 0x7F:
                print("  %-6s %-42s negative response %s"
                      % (req, desc, r.hex()))
                noresp += 1
                continue
            # Echo is <service+0x40> <id...>; the payload follows it.
            body = r[2:] if len(r) > 2 else b""
            print("  %-6s %-42s -> %s" % (req, desc, r.hex()))
            if pred is None:
                print("         %s" % why)
                continue
            if not body:
                print("         empty payload, nothing to check")
                noresp += 1
                continue
            ok = pred(body)
            hit += ok
            miss += (not ok)
            print("         payload %s   predicted %s   %s"
                  % (body.hex(), why, "MATCH" if ok else "no match"))
    finally:
        bus.close()

    print()
    print("matched %d, did not match %d, no usable answer %d" % (hit, miss, noresp))
    print("A match supports the binding. A miss is inconclusive: the response")
    print("may carry a different node's value from the same graph.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
