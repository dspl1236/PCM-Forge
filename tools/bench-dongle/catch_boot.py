#!/usr/bin/env python3
"""Listen continuously and timestamp the first frame -- catch the boot window.

WillCoder reports the PCM auto-shuts down after ~15 minutes without car-side
CAN signals. If that is what has been happening on our bench, the unit is only
talking for a window after power-up, and every capture we ran was simply too
late.

Start this FIRST, with the PCM powered off. Then apply 12V. It prints the
elapsed time to the first frame and keeps a running log, so we learn both
whether it talks and for how long before it goes quiet.

    python catch_boot.py COM4
    python catch_boot.py COM4 --rate 3        (500k instead of 100k)

Ctrl-C prints the summary: first frame, last frame, and the silent gap that
would indicate the unit shutting itself down.
"""
import sys
import time
from collections import Counter

try:
    import serial
except ImportError:
    sys.exit("needs pyserial:  pip install pyserial")

RATE_NAMES = {0: "100k", 1: "125k", 2: "250k", 3: "500k",
              4: "1M", 5: "50k", 6: "83k", 7: "33k"}


def cmd(s, text, wait=0.5):
    s.write((text + "\n").encode())
    s.flush()
    out, end = [], time.time() + wait
    while time.time() < end:
        raw = s.readline()
        if raw:
            line = raw.decode("ascii", "replace").strip()
            if line:
                out.append(line)
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    port = argv[0]
    rate = 0
    if "--rate" in argv:
        rate = int(argv[argv.index("--rate") + 1])

    s = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(2.2)                      # the Nano resets on port open
    s.reset_input_buffer()

    cmd(s, "x 8")
    cmd(s, "b %d" % rate)
    cmd(s, "l 0")                        # normal mode: we ACK, so a lone PCM
    cmd(s, "o", 1.5)                     # can actually complete a transmit
    cmd(s, "z")
    cmd(s, "e 1")

    print("listening at %s, ACKing." % RATE_NAMES.get(rate, "?"))
    print("POWER THE PCM ON NOW.  Ctrl-C for the summary.\n")

    t0 = time.time()
    first = last = None
    ids = Counter()
    gap_warned = False

    try:
        while True:
            raw = s.readline()
            now = time.time()
            if raw:
                line = raw.decode("ascii", "replace").strip()
                if line.startswith("R "):
                    p = line.split()
                    if len(p) >= 4:
                        ids[p[2].upper()] += 1
                        if first is None:
                            first = now
                            print("*** FIRST FRAME at t+%.1fs: %s" %
                                  (now - t0, " ".join(p[2:])))
                        last = now
                        gap_warned = False
            # flag a lull once traffic has started -- that is the shutdown
            if last and not gap_warned and time.time() - last > 10:
                print("--- silent for 10s at t+%.0fs (was talking). "
                      "Auto-shutdown?" % (time.time() - t0))
                gap_warned = True
            if first is None and int(time.time() - t0) % 30 == 0:
                sys.stdout.write("\r   waiting... t+%.0fs " % (time.time() - t0))
                sys.stdout.flush()
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        s.close()

    print("\n\n=== summary ===")
    if first is None:
        print("  no frames at all in %.0fs." % (time.time() - t0))
        print("  Either the unit never talks on this pair, or the pair is dead.")
    else:
        print("  first frame   t+%.1fs" % (first - t0))
        print("  last frame    t+%.1fs" % (last - t0))
        print("  talked for    %.1fs" % (last - first))
        print("  %d frames, %d distinct ids" % (sum(ids.values()), len(ids)))
        for i, n in ids.most_common(20):
            print("     %-6s %d" % (i, n))
        if time.time() - last > 60:
            print("\n  It went quiet and stayed quiet -- consistent with the")
            print("  ~15min no-car auto-shutdown WillCoder describes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
