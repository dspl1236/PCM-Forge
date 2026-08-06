#!/usr/bin/env python3
"""Capture CAN MMI through a real vehicle wake, and isolate the moment.

The question this exists to answer: which frame carries `WUR_HU_ON_REQ`. The
PCM boots, asks the IOC why it was woken, and shuts down again if the answer is
not a recognised reason (see BOOT_ORDER_AND_STARTER.md). `WUR_ON_BUTTON` is the
only reason a bench can produce, so the wake frame has to be caught on a car.

It only appears during a genuine wake, which means the capture must be running
*before* the car is disturbed. A log started after the PCM is already awake has
missed it -- that is precisely how the bench experiments kept failing.

    python wake_capture.py --port COM5 --out wake.log

Sit with it running, then unlock / open the door / switch on. It writes the
whole trace, and separately reports the first appearance of every id and the
frames immediately around the bus waking up -- so the interesting 200 ms is not
buried in ten minutes of periodic traffic.

Tap CAN MMI at any node; they all carry the same bus:

    climate panel  sheet 05  A17    <- easiest access
    gateway        sheet 07  A18/A8
    cluster        sheet 04  A4
    PCM            sheet 20  A11/A9

CAN HIGH is `OG VT`, CAN LOW is `OG BN`. The climate/cluster taps are 0.13 mm2,
so use a pierce clip rather than anything heavy.
"""
import argparse
import sys
import time
from collections import defaultdict

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

PAD = 0xFF
PRIME_ID = 0x7FF

# The PCM's own ids, from CAN_MMI_BUS.md. Everything else on this bus is
# another module, which is the point -- on a car we finally get all nine.
PCM_IDS = {0x539, 0x541, 0x5FA, 0x5FB, 0x6AB, 0x6D3}


class Slcan:
    def __init__(self, port, baud=115200, bitrate="6", prime=True):
        self.s = serial.Serial(port, baud, timeout=0.02)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for cmd in ("C", "S" + bitrate, "O"):
            self.s.write((cmd + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        if prime:
            # This CANable will not receive until it has transmitted. On a live
            # car that is a real footprint, so it is one frame on an unused id
            # rather than the burst the bench scripts use.
            self.s.write(("t%03X8%s\r" % (PRIME_ID, "00" * 8)).encode())
            time.sleep(0.1)
        self.s.reset_input_buffer()

    def close(self):
        try:
            self.s.write(b"C\r")
            time.sleep(0.1)
        finally:
            self.s.close()

    def frames(self):
        """Yield (t, id, hexdata) forever."""
        buf = b""
        while True:
            buf += self.s.read(512)
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip().decode(errors="replace")
                if len(line) >= 5 and line[0] in "tT":
                    ext = line[0] == "T"
                    n = 8 if ext else 3
                    try:
                        cid = int(line[1:1 + n], 16)
                        dlc = int(line[1 + n], 16)
                    except ValueError:
                        continue
                    yield (time.time(), cid,
                           line[2 + n:2 + n + dlc * 2].upper())
            if not buf:
                time.sleep(0.002)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--out", default="wake.log")
    ap.add_argument("--quiet-secs", type=float, default=2.0,
                    help="gap that counts as the bus having been asleep")
    ap.add_argument("--window", type=float, default=3.0,
                    help="seconds of context to report around the wake")
    ap.add_argument("--minutes", type=float, default=30.0)
    a = ap.parse_args()

    bus = Slcan(a.port)
    fh = open(a.out, "w", encoding="utf-8")
    rows = []
    first_seen = {}
    wake_at = None
    last_frame = None
    t0 = time.time()

    print("capturing CAN MMI on %s -> %s" % (a.port, a.out))
    print("leave this running, THEN unlock / open the door / switch on.")
    print("Ctrl-C when done.\n")
    try:
        for t, cid, data in bus.frames():
            if time.time() - t0 > a.minutes * 60:
                break
            fh.write("%.3f %03X %s\n" % (t - t0, cid, data))

            # A quiet gap followed by traffic is the bus waking. Record the
            # first such transition only: later gaps are usually the adapter
            # being starved, not the car sleeping again.
            if (wake_at is None and last_frame is not None
                    and t - last_frame > a.quiet_secs):
                wake_at = t
                print("*** bus woke at %.2fs (after %.1fs quiet) ***"
                      % (t - t0, t - last_frame))
            last_frame = t

            if cid not in first_seen:
                first_seen[cid] = t
                tag = "PCM" if cid in PCM_IDS else "   "
                print("  %7.2fs  %s  %03X first seen  %s"
                      % (t - t0, tag, cid, data))
            rows.append((t, cid, data))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        fh.close()
        bus.close()

    print("\n%d frames, %d ids, written to %s" % (len(rows), len(first_seen),
                                                  a.out))
    if not rows:
        return 1

    # --- order of appearance: which module speaks first on a wake ---
    print("\nfirst appearance, in order:")
    for cid, t in sorted(first_seen.items(), key=lambda kv: kv[1]):
        tag = "PCM" if cid in PCM_IDS else "   "
        print("   %7.2fs  %s  %03X" % (t - t0, tag, cid))

    if wake_at is None:
        print("\nNo quiet->active transition seen. If the bus was already "
              "awake when this started, the wake frame was missed -- start "
              "the capture on a genuinely sleeping car.")
        return 0

    # --- the frames that matter ---
    lo, hi = wake_at - a.window, wake_at + a.window
    seg = [r for r in rows if lo <= r[0] <= hi]
    name = a.out.rsplit(".", 1)[0] + "_wake.log"
    with open(name, "w", encoding="utf-8") as wf:
        for t, cid, data in seg:
            wf.write("%+.3f %03X %s\n" % (t - wake_at, cid, data))
    print("\nwake window +/-%.1fs: %d frames -> %s" % (a.window, len(seg), name))

    print("\nfirst 25 frames after the bus woke:")
    for t, cid, data in [r for r in seg if r[0] >= wake_at][:25]:
        tag = "PCM" if cid in PCM_IDS else "   "
        print("   %+7.3fs  %s  %03X  %s" % (t - wake_at, tag, cid, data))

    # Whatever carries HU_ON_REQ has to arrive before the PCM answers, so the
    # ids ahead of the PCM's own first frame are the candidate set.
    pcm_first = min((t for t, c, _ in rows if c in PCM_IDS), default=None)
    if pcm_first:
        before = sorted({c for t, c, _ in rows if t < pcm_first})
        print("\nPCM first speaks at %.2fs. Ids seen before it: %s"
              % (pcm_first - t0, " ".join("%03X" % c for c in before)))
        print("The wake request is in that set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
