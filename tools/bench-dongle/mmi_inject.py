#!/usr/bin/env python3
"""Transmit onto CAN MMI and watch whether the PCM wakes.

The PCM 3.1 function sheet lists three power-relevant signals reaching this
unit over CAN MMI: TERM. 15, S CONTACT and -- the one we never chased --
RADIO KEY. Terminal R is what powers a head unit in the accessory position,
which is exactly the state a bench PCM never reaches.

`3F1` byte 1 reads 0x02 with terminal 15 applied and 0x00 without. 0x02 is
bit 1, not a count, so the byte is very likely a terminal bitmask with the
other terminals on neighbouring bits. This steps through them and reads the
answer off the PCM's own state word rather than asking anyone to watch a screen.

    python mmi_inject.py --port COM5                     observe only
    python mmi_inject.py --port COM5 --sweep 3F1:1       step byte 1 of 3F1
    python mmi_inject.py --port COM5 --send 3F1:0002...  hold one frame

CONTENTION WARNING. If the real gateway is powered it is already transmitting
3F1. Two nodes sending the same id with different data collide after
arbitration and both raise error frames; sustained, that can drive a node to
bus-off. Observe mode reports whether the gateway is present. For a clean
sweep, power the gateway down and let this be the only transmitter -- the PCM
sleeps ~1.2 s when alone, but continuous injection keeps it awake.
"""
import argparse
import sys
import threading
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

PAD = 0xFF
# The PCM's own state, established by knobbing the screen and reading the bus.
ON_SIG = ("0A", "80")      # 539 byte 1, byte 2 when up
OFF_SIG = ("02", "00")     # ... and when down
WATCH = {0x539: "state word", 0x5FA: "up-ind A", 0x5FB: "up-ind B",
         0x6D3: "boot announce"}
# Gateway ids carrying terminal / system state, worth showing in observe mode.
TERMINAL_IDS = {0x3F1: "terminal flags?", 0x663: "moves with ignition",
                0x6C0: "system state"}


class Slcan:
    def __init__(self, port, baud=115200, bitrate="6"):
        self.s = serial.Serial(port, baud, timeout=0.05)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for cmd in ("C", "S" + bitrate, "O"):
            self.s.write((cmd + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        # this CANable will not receive until it has transmitted
        for _ in range(3):
            self.send(0x7FF, b"\x00")
            time.sleep(0.05)
        self.s.reset_input_buffer()

    def close(self):
        try:
            self.s.write(b"C\r")
            time.sleep(0.1)
        finally:
            self.s.close()

    def send(self, can_id, data):
        d = bytes(data) + bytes([PAD] * (8 - len(data)))
        self.s.write(("t%03X8%s\r" % (can_id, d.hex().upper())).encode())
        self.s.flush()


class Watcher(threading.Thread):
    def __init__(self, bus):
        super().__init__(daemon=True)
        self.bus, self.rows, self.stop = bus, [], False

    def run(self):
        buf = b""
        while not self.stop:
            buf += self.bus.s.read(512)
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip().decode(errors="replace")
                if len(line) >= 5 and line[0] == "t":
                    try:
                        cid = int(line[1:4], 16)
                        dlc = int(line[4], 16)
                        self.rows.append((time.time(), cid,
                                          line[5:5 + dlc * 2].upper()))
                    except ValueError:
                        pass
            time.sleep(0.005)


def pcm_state(rows):
    """Up, down, or unknown -- read off the PCM's own 539."""
    v = [d for _, c, d in rows if c == 0x539]
    if not v:
        return "?", None
    last = v[-1]
    sig = (last[2:4], last[4:6])
    return ("UP" if sig == ON_SIG else
            "DOWN" if sig == OFF_SIG else "??"), last


def latest(rows, cid):
    v = [d for _, c, d in rows if c == cid]
    return v[-1] if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="CANable on CAN MMI")
    ap.add_argument("--sweep", metavar="ID:BYTE",
                    help="step one byte of an id, e.g. 3F1:1")
    ap.add_argument("--values", default="01,02,03,04,05,07,0F",
                    help="byte values to try in the sweep")
    ap.add_argument("--send", metavar="ID:HEX", help="hold one frame")
    ap.add_argument("--dwell", type=float, default=6.0,
                    help="seconds to hold each value")
    ap.add_argument("--period", type=float, default=0.05,
                    help="transmit interval while holding")
    a = ap.parse_args()

    bus = Slcan(a.port)
    w = Watcher(bus)
    w.start()
    time.sleep(3.0)

    ids = sorted({c for _, c, _ in w.rows})
    gw_present = 0x3F1 in ids
    st, raw = pcm_state(w.rows)
    print("bus: %d ids seen; gateway %s"
          % (len(ids), "PRESENT (contention risk)" if gw_present else "absent"))
    print("PCM: %s   539=%s" % (st, raw))
    for cid, what in TERMINAL_IDS.items():
        print("   %03X  %-18s %s" % (cid, latest(w.rows, cid), what))

    if not (a.sweep or a.send):
        print("\nobserve only; pass --sweep or --send to transmit")
        w.stop = True
        bus.close()
        return 0

    if gw_present:
        print("\nNOTE: transmitting the same id as a live gateway will raise "
              "CAN errors on both nodes.")

    base = latest(w.rows, 0x3F1) or "0000000000000000"

    def hold(cid, payload, secs, label):
        start = len(w.rows)
        t0 = time.time()
        while time.time() - t0 < secs:
            bus.send(cid, payload)
            time.sleep(a.period)
        seg = w.rows[start:]
        st2, raw2 = pcm_state(seg)
        boots = sum(1 for _, c, _ in seg if c == 0x6D3)
        print("   %-22s -> PCM %-5s 539=%s%s"
              % (label, st2, raw2, "  BOOT ANNOUNCE" if boots else ""))
        return st2

    if a.send:
        sid, hexs = a.send.split(":")
        print()
        hold(int(sid, 16), bytes.fromhex(hexs), a.dwell, a.send)

    if a.sweep:
        sid, bidx = a.sweep.split(":")
        cid, bidx = int(sid, 16), int(bidx)
        print("\nsweeping %03X byte %d, %.0f s each (baseline %s)\n"
              % (cid, bidx, a.dwell, base))
        for v in [x.strip() for x in a.values.split(",")]:
            d = bytearray.fromhex(base)
            d[bidx] = int(v, 16)
            if hold(cid, bytes(d), a.dwell, "byte%d=%s" % (bidx, v)) == "UP":
                print("\n   *** PCM came up on byte%d=%s ***" % (bidx, v))
                break

    w.stop = True
    time.sleep(0.2)
    bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
