#!/usr/bin/env python3
"""Capture every readDataByLocalIdentifier the config declares, with lengths.

The response layout -- which dataflow node's value lands in which byte of an
answer -- is the last undecoded part of the diagnosis.cfg model. Response
LENGTHS are the way in: they are ground truth the file has to predict, and the
config declares exactly which identifiers exist, so the set is closed rather
than guessed.

Retries matter. The first request after a session opens frequently returns
7F xx 21 (busyRepeatRequest) or nothing at all, and on the first run here that
made every identifier look unsupported when all of them answered on a repeat.
So each id gets several attempts before being called absent, and a negative
response is recorded with its code rather than collapsed to a failure.

All reads. Nothing here starts a routine or writes.

Usage:  py -3 lid_survey.py --port COM5 [--out lid_survey.txt]
"""
import argparse
import sys
import time

import pcm_slcan as P

# Every read the config declares (dcl.kwp_services), plus 1A 91 / 1A 93 as
# controls: both are known to answer, so a run where they fail is a bench
# problem rather than an absent identifier.
REQUESTS = [
    "1A91", "1A93",
    "1A81", "1A83", "1A95",
    "2100", "2106", "210A", "210B", "210C", "210E", "2111", "2112", "2114",
    "2115", "2116", "211A", "211B", "2122", "2123", "2124", "2125", "2127",
    "2128", "2129", "212A", "212C", "21F4", "21FE",
]

NRC = {0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
       0x21: "busyRepeatRequest", 0x22: "conditionsNotCorrect",
       0x31: "requestOutOfRange", 0x33: "securityAccessDenied",
       0x78: "responsePending"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--bitrate", default="6")
    ap.add_argument("--tries", type=int, default=5)
    ap.add_argument("--gap", type=float, default=0.35,
                    help="pause before each attempt; the unit wedges if pushed")
    ap.add_argument("--requests",
                    help="comma-separated hex, e.g. 2106,210A; "
                         "defaults to every declared read")
    ap.add_argument("--out")
    a = ap.parse_args()

    reqs = ([x.strip() for x in a.requests.split(",") if x.strip()]
            if a.requests else REQUESTS)
    bus = P.Slcan(a.port, a.baud, a.bitrate)
    lines = []

    def emit(s):
        print(s)
        lines.append(s)

    try:
        P.step(bus, "1089", "open manufacturer session")
        emit("")
        emit("%-6s %-6s %-4s %s" % ("req", "status", "len", "payload"))
        busy_run = 0
        for hx in reqs:
            req = bytes.fromhex(hx)
            got, why = None, "no answer"
            for attempt in range(a.tries):
                # Keep the session alive and give the unit room. Hammering it
                # is what produced a wall of busyRepeatRequest: one identifier
                # returned generalReject and every request after it went busy
                # until the session was re-opened.
                P.request(bus, b"\x3E", window=0.4)
                time.sleep(a.gap)
                r = P.request(bus, req)
                if r and r[0] != 0x7F:
                    # VALIDATE THE ECHO. A positive KWP reply is
                    # <service+0x40> <id> ..., and when the unit answers slowly
                    # the harness otherwise pairs a reply with the NEXT
                    # request. That produced a whole table of "0-byte" reads
                    # with one identifier carrying the previous one's payload,
                    # which reads exactly like a dramatic state change and is
                    # not one.
                    ok_echo = (r[0] == req[0] + 0x40
                               and (len(req) < 2 or (len(r) > 1
                                                     and r[1] == req[1])))
                    if not ok_echo:
                        why = "MISMATCH: asked %s got %s" % (req.hex(), r[:2].hex())
                        time.sleep(a.gap)
                        continue
                    got = r
                    busy_run = 0
                    break
                if r and r[0] == 0x7F:
                    code = r[2] if len(r) > 2 else 0
                    why = "7F %02X %s" % (code, NRC.get(code, "?"))
                    if code != 0x21:          # only busy is worth repeating
                        break
                busy_run += 1
                if busy_run >= 3:             # wedged: re-open and carry on
                    P.request(bus, b"\x10\x89", window=1.0)
                    busy_run = 0
                    time.sleep(0.5)
            if got is None:
                emit("%-6s %-6s %-4s %s" % (hx, "-", "-", why))
                continue
            # positive response is 61 <id> <data>
            body = got[2:] if len(got) > 2 else b""
            emit("%-6s %-6s %-4d %s" % (hx, "ok", len(body), body.hex()))
            time.sleep(a.gap)
    finally:
        bus.close()

    if a.out:
        open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
