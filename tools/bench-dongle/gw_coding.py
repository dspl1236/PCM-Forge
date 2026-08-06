#!/usr/bin/env python3
"""Find where the gateway keeps the vehicle configuration PIWIS displays.

PIWIS shows the car as a list of PR codes -- `E0W` Cayenne GTS, `D6V` 4.8 V8,
`L0L` left-hand drive and so on. That is Porsche's coding, and if it can be read
over UDS then the format can be decoded, which is the prerequisite for changing
anything without a dealer tool.

PR codes are three ASCII characters, so they cannot hide: sweep the DID space
and report any response containing one of the codes PIWIS is showing. A hit is
unambiguous, unlike the small-integer searches that have produced false
positives elsewhere in this project.

    python gw_coding.py --port COM6

Read-only. No write service is sent.
"""
import argparse
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

TX, RX = 0x710, 0x77A
PAD = 0xFF

# Straight off the PIWIS screen for this gateway. Any of these appearing in a
# response identifies the coding block immediately.
KNOWN = ["E0W", "8T1", "8BT", "L0L", "8G0", "D6V", "9Q1", "7Y1", "7L4", "9M0"]
PR = re.compile(r"\b[0-9A-Z][0-9A-Z][0-9A-Z]\b")


class Slcan:
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

    def send(self, cid, data):
        d = bytes(data) + bytes([PAD] * (8 - len(data)))
        self.s.write(("t%03X8%s\r" % (cid, d.hex().upper())).encode())
        self.s.flush()

    def request(self, payload, window=0.35):
        """One UDS request with ISO-TP reassembly. Returns bytes or None."""
        p = bytes(payload)
        self.send(TX, bytes([len(p)]) + p)
        out, expect, deadline = bytearray(), 0, time.time() + window
        buf = b""
        while time.time() < deadline:
            buf += self.s.read(256)
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip().decode(errors="replace")
                if len(line) < 5 or line[0] != "t":
                    continue
                try:
                    cid, dlc = int(line[1:4], 16), int(line[4], 16)
                except ValueError:
                    continue
                if cid != RX:
                    continue
                d = bytes.fromhex(line[5:5 + dlc * 2])
                kind = d[0] >> 4
                if kind == 0:
                    body = d[1:1 + (d[0] & 0x0F)]
                    if len(body) >= 3 and body[0] == 0x7F and body[2] == 0x78:
                        deadline = time.time() + 2.0   # responsePending
                        continue
                    return bytes(body)
                if kind == 1:
                    expect = ((d[0] & 0x0F) << 8) | d[1]
                    out = bytearray(d[2:8])
                    self.send(TX, b"\x30\x00\x00")
                    deadline = time.time() + 2.0
                elif kind == 2 and expect:
                    out += d[1:]
                    if len(out) >= expect:
                        return bytes(out[:expect])
            time.sleep(0.005)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--blocks", default="0000,0100,0200,0300,0400,0500,0600,0700,F100,F400,F800",
                    help="256-DID blocks to sweep, comma separated hex")
    a = ap.parse_args()

    bus = Slcan(a.port)
    print("sweeping gateway %03X/%03X for the PIWIS coding block" % (TX, RX))
    print("looking for: %s\n" % " ".join(KNOWN))
    found = readable = 0
    try:
        for blk in [int(b, 16) for b in a.blocks.split(",")]:
            hits = []
            for i in range(0x100):
                did = blk + i
                r = bus.request(bytes([0x22, did >> 8, did & 0xFF]))
                if not r or r[0] == 0x7F:
                    continue
                readable += 1
                body = r[3:]
                txt = "".join(chr(c) if 32 <= c < 127 else "." for c in body)
                if any(k in txt for k in KNOWN):
                    found += 1
                    print("  *** %04X  %s" % (did, txt))
                    print("           %s" % body.hex(" ")[:120])
                elif len(body) >= 12 and len(PR.findall(txt)) >= 4:
                    hits.append((did, txt, body))
            for did, txt, body in hits[:4]:
                print("  ?   %04X  %s" % (did, txt[:70]))
        print("\n%d readable DIDs, %d containing a known PR code" % (readable, found))
        if not found:
            print("The coding is not exposed as ASCII on any DID swept. PIWIS is "
                  "likely reading it through a routine or a proprietary service, "
                  "not ReadDataByIdentifier.")
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
