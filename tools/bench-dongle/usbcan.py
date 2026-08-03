#!/usr/bin/env python3
"""Drive a USB-CAN adapter via python-can, whichever firmware it ships with.

The cheap "CAN 2.0A/2.0B/FD analyzer" modules are usually CANable-class, but
they ship with one of two firmwares and the host side differs:

  slcan    enumerates as a virtual COM port. Needs nothing extra.
  gs_usb   enumerates as raw USB (candleLight). Needs a WinUSB driver bound
           with Zadig before Windows will let us talk to it.

    python usbcan.py detect              what is plugged in, and how to reach it
    python usbcan.py sniff 500000        listen (default 500k, for OBD)
    python usbcan.py sniff 100000 60     100k for 60s (infotainment side)
    python usbcan.py send 500000 710 0102030405060708

Sniffing is passive but NOT listen-only: python-can opens in normal mode, so we
ACK. That is what we want against a gateway -- it gives the other node a
partner. Do not point this at a car you care about until the bitrate is known.
"""
import sys
import time
from collections import Counter

try:
    import can
except ImportError:
    sys.exit("needs python-can:  pip install python-can")

# The v1 bench capture -- see pcm31-bench-can-link. If these show up, the pair
# under test is the PCM's infotainment CAN.
FINGERPRINT = {0x6AB, 0x539, 0x541, 0x6D3, 0x5FB}


def detect():
    print("=== serial ports (slcan firmware shows up here) ===")
    try:
        from serial.tools import list_ports
        ports = list(list_ports.comports())
        if ports:
            for p in ports:
                print("   %-8s %s" % (p.device, p.description))
                if p.vid is not None:
                    print("            VID:PID %04x:%04x" % (p.vid, p.pid))
        else:
            print("   none")
    except ImportError:
        print("   pyserial missing")

    print("\n=== raw USB (gs_usb / candleLight firmware) ===")
    try:
        import usb.core
        # 0x1d50:0x606f is the canonical candleLight/CANable id; clones vary,
        # so list anything that looks like a CDC/vendor device too.
        found = False
        for dev in usb.core.find(find_all=True):
            try:
                name = usb.util.get_string(dev, dev.iProduct) or ""
            except Exception:
                name = ""
            if (dev.idVendor, dev.idProduct) == (0x1d50, 0x606f) or \
               "can" in name.lower():
                print("   %04x:%04x  %s" % (dev.idVendor, dev.idProduct, name))
                found = True
        if not found:
            print("   nothing obvious. If the adapter is plugged in and absent")
            print("   from both lists, Windows has no driver bound -- run Zadig")
            print("   and assign WinUSB to it, then it appears here as gs_usb.")
    except ImportError:
        print("   pyusb missing")

    print("\nOnce you know which: slcan -> 'sniff' uses the COM port;")
    print("gs_usb -> it is found automatically.")


def _has_gs_usb():
    """Only attempt gs_usb if a candleLight device is actually present --
    a failed attempt leaves a half-built bus that warns on garbage collect."""
    try:
        import usb.core
        return usb.core.find(idVendor=0x1d50, idProduct=0x606f) is not None
    except Exception:
        return False


def open_bus(bitrate):
    """slcan over a COM port, or gs_usb if a candleLight device is present."""
    errors = []
    if _has_gs_usb():
        try:
            bus = can.Bus(interface="gs_usb", channel=0, index=0,
                          bitrate=bitrate)
            print("opened via gs_usb at %d" % bitrate)
            return bus
        except Exception as e:
            errors.append("gs_usb: %s" % e)

    try:
        from serial.tools import list_ports
        for p in list_ports.comports():
            if p.device.upper() == "COM1":       # the built-in, never it
                continue
            try:
                bus = can.Bus(interface="slcan", channel=p.device,
                              bitrate=bitrate)
                print("opened via slcan on %s at %d" % (p.device, bitrate))
                return bus
            except Exception as e:
                errors.append("slcan %s: %s" % (p.device, e))
    except ImportError:
        pass

    print("could not open the adapter:")
    for e in errors:
        print("   " + e)
    print("\nRun 'detect' to see what Windows thinks is attached.")
    return None


def sniff(bitrate, seconds):
    bus = open_bus(bitrate)
    if not bus:
        return 1
    ids, lens, first = Counter(), {}, {}
    t0 = t_first = None
    print("listening %ds ...\n" % seconds)
    try:
        end = time.time() + seconds
        while time.time() < end:
            msg = bus.recv(timeout=0.5)
            if msg is None:
                continue
            if t0 is None:
                t0 = time.time()
                t_first = t0
                print("*** first frame after %.1fs" % (t0 - (end - seconds)))
            ids[msg.arbitration_id] += 1
            lens[msg.arbitration_id] = msg.dlc
            first.setdefault(msg.arbitration_id,
                             " ".join("%02X" % b for b in msg.data))
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()

    total = sum(ids.values())
    print("\n%d frames, %d distinct ids" % (total, len(ids)))
    for i, n in ids.most_common(40):
        mark = "   <-- v1 fingerprint" if i in FINGERPRINT else ""
        print("   %03X  dlc=%-2s n=%-6d %s%s" % (i, lens.get(i, "?"), n,
                                                 first.get(i, ""), mark))
    hits = FINGERPRINT & set(ids)
    if len(hits) >= 3:
        print("\n*** INFOTAINMENT CAN -- %d of 5 v1 IDs. This is the PCM's bus."
              % len(hits))
    elif total:
        print("\nLive bus, not the v1 fingerprint -- gateway or another domain.")
        print("Still good news: a live node here means transmit should ACK.")
    else:
        print("\nSilence. Wrong bitrate, wrong pair, or nothing powered.")
    return 0


def send(bitrate, can_id, data_hex):
    bus = open_bus(bitrate)
    if not bus:
        return 1
    data = bytes.fromhex(data_hex)
    msg = can.Message(arbitration_id=int(can_id, 16), data=data,
                      is_extended_id=False)
    try:
        bus.send(msg, timeout=1.0)
        print("T ok  %s  -- someone ACKed. Injection is possible." % can_id)
    except can.CanError as e:
        print("T ERR %s  -- %s" % (can_id, e))
        print("No ACK. Either nothing else is on the bus, or it cannot hear us.")
    finally:
        bus.shutdown()
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "detect":
        detect()
        return 0
    if cmd == "sniff":
        rate = int(argv[1]) if len(argv) > 1 else 500000
        secs = int(argv[2]) if len(argv) > 2 else 20
        return sniff(rate, secs)
    if cmd == "send":
        return send(int(argv[1]), argv[2], argv[3])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
