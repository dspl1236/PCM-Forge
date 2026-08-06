#!/usr/bin/env python3
"""Test candidate SecurityAccess key algorithms against the PCM.

A PIWIS capture caught one accepted pair: seed 6E0F, key 91F0, which are exact
one's complements. Four pairs scraped from an Autel log earlier do not fit that
rule, so it is either the algorithm or a coincidence, and one live request
settles it.

Tries ONE candidate per run by default. KWP defines 0x36 exceedNumberOfAttempts
and 0x37 requiredTimeDelayNotExpired -- a script that hammers guesses can lock
the unit out, so this deliberately does not loop.

    python try_unlock.py --port COM5 --rule complement
    python try_unlock.py --port COM5 --rule swap
"""
import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

TX, RX = 0x773, 0x7DD
PAD = 0xFF

# Candidates, each taking a 16-bit seed and returning a 16-bit key.
RULES = {
    "complement": lambda s: (~s) & 0xFFFF,          # 6E0F -> 91F0
    "swap":       lambda s: ((s << 8) | (s >> 8)) & 0xFFFF,   # 3D32 -> 323D
    "sub":        lambda s: (0xFFFF - s) & 0xFFFF,  # same as complement
    "negate":     lambda s: (-s) & 0xFFFF,
}

# Everything observed, for offline checking.
PAIRS = [(0x6E0F, 0x91F0, "PIWIS, accepted"),
         (0x3D32, 0x323D, "Autel"), (0xA059, 0x5399, "Autel"),
         (0x1C25, 0x128E, "Autel"), (0xB9FE, 0x1781, "Autel")]


class Bus:
    def __init__(self, port, baud=115200):
        self.s = serial.Serial(port, baud, timeout=0.05)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for c in ("C", "S6", "O"):
            self.s.write((c + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        self.s.reset_input_buffer()

    def close(self):
        try:
            self.s.write(b"C\r")
            time.sleep(0.1)
        finally:
            self.s.close()

    def req(self, payload, window=1.5):
        p = bytes(payload)
        d = bytes([len(p)]) + p
        d += bytes([PAD] * (8 - len(d)))
        self.s.write(("t%03X8%s\r" % (TX, d.hex().upper())).encode())
        self.s.flush()
        buf, end = b"", time.time() + window
        while time.time() < end:
            buf += self.s.read(256)
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip().decode(errors="replace")
                if len(line) >= 5 and line[0] == "t":
                    try:
                        cid, dlc = int(line[1:4], 16), int(line[4], 16)
                    except ValueError:
                        continue
                    if cid == RX:
                        b = bytes.fromhex(line[5:5 + dlc * 2])
                        if b and (b[0] >> 4) == 0:
                            return bytes(b[1:1 + (b[0] & 0x0F)])
            time.sleep(0.005)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--rule", default="complement", choices=sorted(RULES))
    ap.add_argument("--offline", action="store_true",
                    help="only score the rules against known pairs")
    a = ap.parse_args()

    print("known pairs vs each rule:")
    for name, fn in sorted(RULES.items()):
        ok = [s for s, k, _ in PAIRS if fn(s) == k]
        print("   %-11s reproduces %d/%d  %s"
              % (name, len(ok), len(PAIRS),
                 " ".join("%04X" % s for s in ok) or "-"))
    print()
    if a.offline:
        return 0

    bus = Bus(a.port)
    try:
        r = bus.req(b"\x10\x89")
        print("session 10 89 -> %s" % (r.hex().upper() if r else "no answer"))

        r = bus.req(b"\x27\x01")
        if not r or len(r) < 4 or r[0] != 0x67:
            print("27 01 -> %s (no seed)" % (r.hex().upper() if r else "nothing"))
            return 1
        seed = (r[2] << 8) | r[3]
        print("27 01 -> seed %04X" % seed)
        if seed == 0:
            print("Seed is 0000: already unlocked, so this proves nothing. "
                  "Power-cycle the PCM and run again.")
            return 0

        key = RULES[a.rule](seed)
        print("rule '%s' -> key %04X" % (a.rule, key))
        r = bus.req(bytes([0x27, 0x02, key >> 8, key & 0xFF]))
        if not r:
            print("27 02 -> no answer")
        elif r[0] == 0x67:
            print("\n*** ACCEPTED -- %s is the algorithm ***" % a.rule)
        elif r[0] == 0x7F:
            nrc = {0x35: "invalidKey", 0x36: "exceedNumberOfAttempts",
                   0x37: "requiredTimeDelayNotExpired",
                   0x24: "requestSequenceError"}.get(r[2], "%02X" % r[2])
            print("\nrejected: %s" % nrc)
            if r[2] in (0x36, 0x37):
                print("Attempt limiter tripped. Stop and power-cycle before "
                      "trying anything else.")
        else:
            print("27 02 -> %s" % r.hex().upper())
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
