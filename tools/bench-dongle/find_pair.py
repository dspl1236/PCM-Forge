#!/usr/bin/env python3
"""Find which wire pair is the infotainment CAN, by fingerprint.

Move the dongle to a candidate pair, run this, move to the next. It sweeps
every bitrate listen-only (which cannot disturb a live bus) and tells you what
it heard -- and specifically whether the v1 fingerprint showed up.

    python find_pair.py COM4                 sweep once, report
    python find_pair.py COM4 --watch         sweep repeatedly until Ctrl-C

The fingerprint is the capture from the first working bench session: five IDs
at 100 kbps from the PCM itself. If these appear, the pair under test is the
infotainment CAN and the PCM is transmitting on it. Anything else alive is
still useful -- a gateway on the diagnostic pair proves the dongle and wiring
are good, which is the harder thing to establish.
"""
import sys
import time
from collections import Counter

try:
    import serial
except ImportError:
    sys.exit("needs pyserial:  pip install pyserial")

# The v1 capture -- see research/, and the pcm31-bench-can-link note.
FINGERPRINT = {
    "6AB": "~200ms  00 00 00 00 00 00 0F A1",
    "539": "~250ms  35 02 80 00 08 03 00 00",
    "541": "~250ms  all zeros",
    "6D3": "~200ms  01 00 00 00 00 00 00",
    "5FB": "~1000ms 1F FF FF FF FF 1F F8 7E",
}

RATES = [(0, "100k"), (1, "125k"), (2, "250k"), (3, "500k"),
         (4, "1M"), (5, "50k"), (6, "83k"), (7, "33k")]

DWELL = 2.5          # seconds per bitrate; 0x5FB is ~1Hz so give it room


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


def harvest(s, secs):
    ids, lens, first = Counter(), {}, {}
    end = time.time() + secs
    while time.time() < end:
        raw = s.readline()
        if not raw:
            continue
        line = raw.decode("ascii", "replace").strip()
        if line.startswith("R "):
            p = line.split()
            if len(p) >= 4:
                ids[p[2].upper()] += 1
                lens[p[2].upper()] = p[3]
                first.setdefault(p[2].upper(), " ".join(p[4:]))
    return ids, lens, first


def sweep(s):
    print("sweeping (listen-only -- safe on a live bus)")
    best = None
    for idx, name in RATES:
        cmd(s, "l 1")
        cmd(s, "b %d" % idx)
        cmd(s, "o", 1.2)
        cmd(s, "z")
        cmd(s, "e 1")
        ids, lens, first = harvest(s, DWELL)
        total = sum(ids.values())
        match = FINGERPRINT.keys() & ids.keys()
        flag = "  <-- %d/5 fingerprint" % len(match) if match else ""
        print("  %-5s  %5d frames  %2d ids%s" % (name, total, len(ids), flag))
        if total and (best is None or total > best[0]):
            best = (total, name, ids, lens, first, match)

    if not best:
        print("\nnothing on this pair at any bitrate.")
        print("Either it is not a CAN pair, nothing on it is powered, or the")
        print("wiring is open. A pair with a live node shows traffic here.")
        return False

    total, name, ids, lens, first, match = best
    print("\n=== traffic at %s: %d frames, %d ids ===" % (name, total, len(ids)))
    for i, n in ids.most_common(40):
        known = "  [v1: %s]" % FINGERPRINT[i] if i in FINGERPRINT else ""
        print("   %-6s dlc=%-2s n=%-5d  %s%s" % (i, lens.get(i, "?"), n,
                                                 first.get(i, ""), known))

    if len(match) >= 3:
        print("\n*** INFOTAINMENT CAN -- %d of the 5 v1 IDs present." % len(match))
        print("    This is the pair the PCM talks on.")
    elif match:
        print("\npartial fingerprint (%s). Probably right, let it run longer:"
              % ", ".join(sorted(match)))
        print("   the 1Hz 0x5FB needs a few seconds to show.")
    else:
        print("\nLive pair, but not the v1 fingerprint -- likely the diagnostic")
        print("or a powertrain bus. Still valuable: a live node here means the")
        print("dongle and wiring are good, so transmit should now ACK.")
    return True


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    port = argv[0]
    watch = "--watch" in argv

    s = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(2.2)                    # the Nano resets when the port opens
    s.reset_input_buffer()
    try:
        cmd(s, "x 8")                  # settings do not survive the reset
        while True:
            alive = sweep(s)
            if alive:
                print("\nchecking transmit (needs a partner to ACK)...")
                cmd(s, "l 0")
                cmd(s, "o", 1.2)
                for l in cmd(s, "t 710 0102030405060708", 0.8):
                    if l.startswith("T "):
                        print("   %s   %s" % (
                            l, "<-- someone ACKed. Injection is now possible."
                            if l.startswith("T ok") else
                            "still no ACK -- nothing is receiving us."))
            if not watch:
                break
            print("\n--- again, Ctrl-C to stop ---\n")
    except KeyboardInterrupt:
        print()
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
