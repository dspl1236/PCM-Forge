#!/usr/bin/env python3
"""Drive the PCM-Forge bench dongle from a PC.

    python bench_can.py COM4 scan          find the bitrate
    python bench_can.py COM4 sniff 30      listen 30s, report the ID map
    python bench_can.py COM4 send 710 0102030405060708
    python bench_can.py COM4 hold 0 100 710 0102030405060708   repeat every 100ms
    python bench_can.py COM4 shell         type dongle commands directly

Needs pyserial (``pip install pyserial``) and nothing else.

The bitrate is the first thing to establish and the easiest to get wrong: a
misconfigured MCP2515 crystal makes every rate wrong by a factor of two, and
presents as silence rather than as an error. ``scan`` walks the rates in
listen-only mode -- which cannot disturb a live bus -- and reports how many
frames each one yielded. If every rate reports zero, try the other crystal
(``x 8`` or ``x 16``, then ``o``) before suspecting the wiring.
"""
import sys
import time
from collections import Counter

try:
    import serial
except ImportError:
    sys.exit("needs pyserial:  pip install pyserial")

BAUD = 115200


def open_port(port):
    s = serial.Serial(port, BAUD, timeout=0.2)
    time.sleep(2.0)          # the Nano resets when the port opens
    s.reset_input_buffer()
    return s


def pump(s, seconds, on_line=None, quiet=False):
    """Read for a while, returning every line."""
    out, end = [], time.time() + seconds
    while time.time() < end:
        raw = s.readline()
        if not raw:
            continue
        line = raw.decode("ascii", "replace").strip()
        if not line:
            continue
        out.append(line)
        if on_line:
            on_line(line)
        elif not quiet:
            print(line)
    return out


def cmd(s, text, wait=0.4, quiet=True):
    s.write((text + "\n").encode("ascii"))
    s.flush()
    return pump(s, wait, quiet=quiet)


def do_scan(s):
    print("scanning bitrates (listen-only -- safe on a live bus)\n")
    s.write(b"s 1500\n")
    s.flush()
    results = []
    for line in pump(s, 22, quiet=True):
        print(line)
        if line.startswith("S "):
            parts = line.split()
            rate = parts[1]
            n = int(parts[2].split("=")[1])
            results.append((n, rate))
    print()
    good = [r for r in results if r[0] > 0]
    if not good:
        print("No frames at any bitrate. Either the bus is silent, or the")
        print("MCP2515 crystal setting is wrong -- try:  x 16   then  o")
        print("(and check 120 ohm termination across CAN-H / CAN-L)")
        return
    good.sort(reverse=True)
    print("Frames seen at: %s" % ", ".join("%s (%d)" % (r, n) for n, r in good))
    print("Set it with 'b <index>' then 'o'. Indices: "
          "0=100k 1=125k 2=250k 3=500k 4=1M 5=50k 6=83k 7=33k")


def do_sniff(s, seconds, logfile=None):
    ids, total = Counter(), [0]
    lens = {}

    def on_line(line):
        if line.startswith("R "):
            p = line.split()
            if len(p) >= 4:
                ids[p[2]] += 1
                lens[p[2]] = p[3]
                total[0] += 1
        if logfile:
            logfile.write(line + "\n")

    print("listening %ds ..." % seconds)
    cmd(s, "z")
    cmd(s, "e 1")
    pump(s, seconds, on_line=on_line)
    print("\n%d frames, %d distinct IDs\n" % (total[0], len(ids)))
    if ids:
        print("  %-8s %-4s %s" % ("id", "dlc", "count"))
        for i, n in ids.most_common(40):
            print("  %-8s %-4s %d" % (i, lens.get(i, "?"), n))
    else:
        print("Nothing heard. Run 'scan' first -- and remember a lone node with")
        print("no one to ACK cannot transmit, so a silent bus may mean the PCM")
        print("is trying and failing. Leaving listen-only ('l 0', 'o') gives it")
        print("a partner.")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    port, action = argv[0], argv[1]
    s = open_port(port)
    try:
        pump(s, 0.5, quiet=True)          # banner
        if action == "scan":
            do_scan(s)
        elif action == "sniff":
            secs = int(argv[2]) if len(argv) > 2 else 20
            path = argv[3] if len(argv) > 3 else None
            fh = open(path, "w", encoding="ascii") if path else None
            try:
                do_sniff(s, secs, fh)
            finally:
                if fh:
                    fh.close()
                    print("\nlog written to %s" % path)
        elif action == "send":
            for line in cmd(s, "l 0", quiet=True):
                pass
            cmd(s, "o", 1.0, quiet=True)
            for line in cmd(s, "t %s %s" % (argv[2], argv[3]), 0.6, quiet=False):
                print(line)
        elif action == "hold":
            cmd(s, "l 0", quiet=True)
            cmd(s, "o", 1.0, quiet=True)
            slot, ms, cid, data = argv[2], argv[3], argv[4], argv[5]
            for line in cmd(s, "r %s %s %s %s" % (slot, ms, cid, data), 0.6):
                print(line)
            print("repeating; Ctrl-C to stop (the dongle keeps going -- send 'q')")
            try:
                pump(s, 10 ** 6)
            except KeyboardInterrupt:
                cmd(s, "q", quiet=False)
        elif action == "shell":
            print("dongle shell -- '?' for help, Ctrl-C to exit")
            cmd(s, "?", 0.8, quiet=False)
            try:
                while True:
                    line = input("> ").strip()
                    if line:
                        for out in cmd(s, line, 1.2, quiet=True):
                            print(out)
            except (KeyboardInterrupt, EOFError):
                print()
        else:
            print(__doc__)
            return 1
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
