#!/usr/bin/env python3
"""Wait for the PCM to boot, then inject a diagnostic request immediately.

Every `10 89` in the Autel capture arrives 0.4-0.9 s after a boot announce on
6D3, and sending the same command to an already-settled PCM demonstrably does
nothing -- a session held open 30 s with 480 TesterPresent left the screen
dark. The difference may be the timing: a request that lands inside the boot
window while the unit is still deciding what to come up as, rather than after
it has settled.

Hitting a sub-second window by hand is not realistic, so this watches CAN MMI
for the boot and fires on the diagnostic bus the moment it sees it.

    python boot_catch.py --mmi COM5 --diag COM6 --send 1089
    python boot_catch.py --mmi COM5 --diag COM6 --send 1089 --delay 0.7

Start it, then power-cycle the PCM. It reports what the unit came up as, read
off its own state word rather than by watching the screen.
"""
import argparse
import sys
import threading
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

PCM_TX, PCM_RX = 0x773, 0x7DD
PAD = 0xFF
BOOT_ID = 0x6D3

# 539 byte 1 / byte 2. Three states, not two -- the third shows up after the
# Autel puts the unit into service.
STATES = {("02", "00"): "DOWN (standby)",
          ("0A", "80"): "UP (normal)",
          ("00", "80"): "THIRD (service?)"}


class Slcan:
    def __init__(self, port, baud=115200, bitrate="6", prime=False):
        self.s = serial.Serial(port, baud, timeout=0.02)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for cmd in ("C", "S" + bitrate, "O"):
            self.s.write((cmd + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        if prime:
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

    def kwp(self, payload):
        p = bytes(payload)
        self.send(PCM_TX, bytes([len(p)]) + p)


class Watcher(threading.Thread):
    def __init__(self, bus):
        super().__init__(daemon=True)
        self.bus, self.rows, self.stop = bus, [], False
        self.boot_at = None

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
                    except ValueError:
                        continue
                    now = time.time()
                    self.rows.append((now, cid, line[5:5 + dlc * 2].upper()))
                    if cid == BOOT_ID and self.boot_at is None:
                        self.boot_at = now
            time.sleep(0.002)


def state_of(rows):
    v = [d for _, c, d in rows if c == 0x539]
    if not v:
        return "?", None
    last = v[-1]
    return STATES.get((last[2:4], last[4:6]), "UNKNOWN"), last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mmi", required=True)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--send", default="1089",
                    help="comma-separated KWP payloads to fire on boot")
    ap.add_argument("--delay", type=float, default=0.5,
                    help="seconds after the boot announce before firing")
    ap.add_argument("--hold", type=float, default=25.0,
                    help="seconds of TesterPresent after firing")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="give up waiting for a boot")
    a = ap.parse_args()

    mmi = Slcan(a.mmi, prime=True)
    diag = Slcan(a.diag)
    w = Watcher(mmi)
    w.start()
    time.sleep(2.0)

    st, raw = state_of(w.rows)
    print("PCM now: %-18s 539=%s" % (st, raw))
    print("\n>>> POWER-CYCLE THE PCM NOW  <<<")
    print("    waiting up to %.0f s for %03X ...\n" % (a.timeout, BOOT_ID))

    t0 = time.time()
    while w.boot_at is None and time.time() - t0 < a.timeout:
        time.sleep(0.01)
    if w.boot_at is None:
        print("no boot seen -- did the unit actually cycle?")
        w.stop = True
        diag.close()
        mmi.close()
        return 1

    print("boot announce at t=0")
    time.sleep(a.delay)
    mark = len(w.rows)
    parts = [x.strip() for x in a.send.split(",") if x.strip()]
    for i, ph in enumerate(parts):
        if i:
            time.sleep(0.3)
        diag.kwp(bytes.fromhex(ph))
        print("   +%.2fs  sent %s" % (time.time() - w.boot_at, ph))

    time.sleep(0.4)
    for line in diag.s.read(512).decode(errors="replace").split("\r"):
        line = line.strip()
        if line.startswith("t%03X" % PCM_RX):
            print("   reply: %s" % line[5:])

    # hold the session; without TesterPresent it lapses in a couple of seconds
    end = time.time() + a.hold
    while time.time() < end:
        diag.kwp(b"\x3E")
        time.sleep(0.7)

    w.stop = True
    time.sleep(0.2)
    seg = w.rows[mark:]
    st2, raw2 = state_of(seg)
    print("\nafter: %-18s 539=%s" % (st2, raw2))
    for cid in (0x5FA, 0x5FB):
        v = [d for _, c, d in seg if c == cid]
        if v:
            print("   %03X %s%s" % (cid, v[-1],
                                    "  ALL ZERO" if set(v[-1]) <= {"0"} else ""))
    diag.close()
    mmi.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
