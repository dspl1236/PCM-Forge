#!/usr/bin/env python3
"""Inject a diagnostic request and watch CAN MMI for the PCM's reaction.

Asking the operator whether the screen changed puts a human in the measurement
loop, and that has already produced one uninterpretable result -- the knob and
the command look identical after the fact. The MMI bus does not have that
problem: the PCM publishes its own state on 539/5FA/5FB and announces boots on
6D3, so a capture taken across the injection says what happened and when,
whoever touched what.

Two adapters: the CANable on CAN MMI (listen) and the Cerberus in SLCAN mode on
the diagnostic bus (inject). Both are slcan, so one driver covers them.

    python wake_test.py --mmi COM5 --diag COM6 --send 1081
    python wake_test.py --mmi COM5 --diag COM6 --send 1089 --pre 6 --post 20

Nothing is written to the PCM: only session control and reads. The MMI adapter
does transmit a short priming burst on an unused id, because this CANable will
not receive until it has transmitted -- see BENCH_CAN.md.
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
PRIME_ID = 0x7FF          # unused, lowest priority: pokes the adapter's TX path

# The ids that actually carry PCM state, established in CAN_MMI_BUS.md. 6B2 is
# a free-running gateway counter and 6AB drifts, so both are noise here.
WATCH = {0x539: "state word", 0x5FA: "up-indicator A",
         0x5FB: "up-indicator B", 0x6D3: "boot announce"}


class Slcan:
    def __init__(self, port, baud=115200, bitrate="6", prime=False):
        self.s = serial.Serial(port, baud, timeout=0.05)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for cmd in ("C", "S" + bitrate, "O"):
            self.s.write((cmd + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        if prime:
            for _ in range(3):
                self.send(PRIME_ID, b"\x00")
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
    """Timestamp every frame on the MMI bus until told to stop."""

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


def report(rows, t0, label):
    """Print every change on a watched id, timed relative to the injection."""
    last, seen_any = {}, False
    for t, cid, data in rows:
        if cid not in WATCH:
            continue
        if cid == 0x6D3:
            if last.get(cid) is None or t - last[cid] > 3:
                print("   %+7.2fs  6D3  boot announce" % (t - t0))
                seen_any = True
            last[cid] = t
            continue
        prev = last.get(cid)
        if prev is not None and prev != data:
            marks = []
            for i in range(min(len(prev), len(data)) // 2):
                a, b = prev[i * 2:i * 2 + 2], data[i * 2:i * 2 + 2]
                if a != b:
                    marks.append("byte %d %s->%s" % (i, a, b))
            print("   %+7.2fs  %03X  %s   [%s]"
                  % (t - t0, cid, ", ".join(marks), WATCH[cid]))
            seen_any = True
        last[cid] = data
    if not seen_any:
        print("   (%s: no change on any watched id)" % label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mmi", required=True, help="CANable on CAN MMI")
    ap.add_argument("--diag", required=True, help="adapter on the diag bus")
    ap.add_argument("--send", help="KWP payload hex, e.g. 1081; omit to just "
                                   "sample the bus and report PCM state")
    ap.add_argument("--pre", type=float, default=6.0, help="baseline seconds")
    ap.add_argument("--post", type=float, default=20.0, help="watch seconds")
    a = ap.parse_args()

    mmi = Slcan(a.mmi, prime=True)
    w = Watcher(mmi)
    w.start()
    print("watching CAN MMI on %s for %.0f s of baseline ..." % (a.mmi, a.pre))
    time.sleep(a.pre)

    split = len(w.rows)
    t0 = time.time()
    diag = None
    if a.send:
        diag = Slcan(a.diag)
        # Comma-separated so a session can be opened in the same breath as the
        # request under test -- 31 is rejected outside one, and a separate
        # invocation would let the session lapse in between. t=0 is the last
        # payload, which is the one whose effect we are timing.
        parts = [x.strip() for x in a.send.split(",") if x.strip()]
        for i, ph in enumerate(parts):
            if i:
                time.sleep(0.4)
            p = bytes.fromhex(ph)
            if i == len(parts) - 1:
                t0 = time.time()
            diag.send(PCM_TX, bytes([len(p)]) + p)
        print("injected %s on %03X (t=0 is '%s'); watching %.0f s ...\n"
              % (a.send, PCM_TX, parts[-1], a.post))

        # the PCM's own answer, if any
        time.sleep(0.5)
        ans = diag.s.read(512).decode(errors="replace")
        for line in ans.split("\r"):
            line = line.strip()
            if line.startswith("t%03X" % PCM_RX):
                print("   reply on %03X: %s\n" % (PCM_RX, line[5:]))
    else:
        print("observation only, no injection; watching %.0f s ...\n" % a.post)

    time.sleep(a.post)
    w.stop = True
    time.sleep(0.2)
    rows = w.rows

    print("baseline (%.0f s before injection):" % a.pre)
    report(rows[:split], t0, "baseline")
    print("\nafter injection:")
    report(rows[split:], t0, "after")

    # Absolute state, not just deltas. Without this the operator has to say
    # whether the screen is on, and a remembered knob press is indistinguishable
    # from a command afterwards. These payloads are the PCM's own account.
    print("\nPCM state as published on CAN MMI:")
    for cid in sorted(WATCH):
        vals = [d for _, c, d in rows if c == cid]
        if not vals:
            print("   %03X  not transmitted   [%s]" % (cid, WATCH[cid]))
            continue
        zero = set(vals[-1]) <= {"0"}
        note = "  ALL ZERO" if zero else ""
        print("   %03X  %-18s n=%-5d [%s]%s"
              % (cid, vals[-1], len(vals), WATCH[cid], note))

    ids = sorted({c for _, c, _ in rows})
    print("\n%d frames, %d ids: %s"
          % (len(rows), len(ids), " ".join("%03X" % i for i in ids)))
    if diag:
        diag.close()
    mmi.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
