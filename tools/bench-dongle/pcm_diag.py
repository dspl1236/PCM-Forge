#!/usr/bin/env python3
"""Talk KWP2000 to the PCM over the diagnostic bus, via Cerberus.

Replays what the Autel was observed doing on 2026-08-04, one step at a time,
so we can see which step -- if any -- actually brings the screen up. The
capture could not settle that on its own: the PCM was already answering
diagnostics before the tool ever addressed it, and it rebooted several times
during sustained tester activity without any single frame lining up with the
screen coming on.

Everything here is read-only or session/routine control. No WriteDataBy*, no
RequestDownload, no ClearDiagnosticInformation -- nothing that changes stored
state, so a wrong guess costs a reboot at worst.

    python pcm_diag.py --port COM6              # walk the steps, prompting
    python pcm_diag.py --port COM6 --step ident # just read identity
    python pcm_diag.py --port COM6 --hold 60    # hold a session for 60 s

Cerberus speaks one ASCII line per request, "TX:RX:REQUEST", and does the
ISO-TP framing itself -- see CERBERUS_handoff.md.
"""
import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  py -3 -m pip install pyserial")

PCM_TX, PCM_RX = "773", "7DD"

SVC = {0x10: "StartDiagnosticSession", 0x14: "ClearDiagnosticInformation",
       0x18: "ReadDTCByStatus", 0x1A: "ReadEcuIdentification",
       0x22: "ReadDataByCommonIdentifier", 0x27: "SecurityAccess",
       0x31: "StartRoutineByLocalIdentifier", 0x32: "StopRoutineByLocalId",
       0x33: "RequestRoutineResultsByLocalId", 0x3E: "TesterPresent"}
NRC = {0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
       0x22: "conditionsNotCorrect", 0x23: "routineNotComplete",
       0x31: "requestOutOfRange", 0x33: "securityAccessDenied",
       0x35: "invalidKey", 0x78: "responsePending",
       0x80: "noActiveSession"}

# The identity block the Autel read, once it had unlocked. 9F answers without
# security; the rest came back only after a successful 27 01 / 27 02.
IDENT = [("90", "VIN field"), ("91", "part number"), ("95", "software version"),
         ("9F", "diagnostic status"), ("01", "Porsche part number"),
         ("94", "hardware"), ("83", "coding")]

# Routines the Autel started, in the order it started them. 0B reads back a
# two-byte state rather than acting, and 29 was rejected after 41 s of
# responsePending, so it is left out of the default walk.
ROUTINES = [("1701", "routine 17, param 01"),
            ("2E01", "routine 2E, param 01"),
            ("0B", "routine 0B (returns state)")]


class Cerberus:
    def __init__(self, port, baud=115200, timeout=2.0):
        self.s = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)                      # Teensy re-enumerates on open
        self.s.reset_input_buffer()

    def line(self, text):
        self.s.write((text + "\n").encode())
        self.s.flush()
        return self.s.readline().decode(errors="replace").strip()

    def ping(self):
        return "PONG" in self.line("PING")

    def req(self, payload):
        """Send a KWP request to the PCM, return (raw, decoded)."""
        r = self.line("%s:%s:%s" % (PCM_TX, PCM_RX, payload))
        hexpart = r.split("OK:", 1)[1].strip() if "OK:" in r else ""
        return r, decode(hexpart)


def decode(h):
    try:
        b = bytes.fromhex(h)
    except ValueError:
        return ""
    if not b:
        return ""
    if b[0] == 0x7F and len(b) >= 3:
        return "NEG %s -> %s" % (SVC.get(b[1], "%02X" % b[1]),
                                 NRC.get(b[2], "%02X" % b[2]))
    name = SVC.get(b[0] - 0x40, "svc%02X" % (b[0] - 0x40))
    txt = "".join(chr(x) if 32 <= x < 127 else "." for x in b[1:])
    printable = sum(32 <= x < 127 for x in b[1:]) >= max(1, len(b) - 1) * 0.6
    return "%s  %s%s" % (name, b[1:].hex().upper(),
                         '  "%s"' % txt if printable else "")


def show(c, payload, note=""):
    raw, dec = c.req(payload)
    print("    -> %-12s %-46s %s" % (payload, dec or raw, note))
    return dec


def keepalive(c, seconds):
    """Hold the session open. The PCM drops it in a couple of seconds without
    TesterPresent, which is why the Autel sent 212 of them."""
    end = time.time() + seconds
    n = 0
    while time.time() < end:
        c.req("3E")
        n += 1
        time.sleep(1.0)
    print("    held session %d s (%d TesterPresent)" % (seconds, n))


def pause(msg):
    try:
        input("\n  >>> %s -- press ENTER when done: " % msg)
    except EOFError:
        print("\n  (no console; continuing)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="Cerberus COM port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--hold", type=int, default=30,
                    help="seconds to hold the session in the session step")
    ap.add_argument("--step", default="all",
                    choices=["all", "probe", "session", "ident", "routines"])
    a = ap.parse_args()

    c = Cerberus(a.port, a.baud)
    if not c.ping():
        sys.exit("Cerberus did not answer PING on %s" % a.port)
    print("Cerberus up on %s\n" % a.port)

    if a.step in ("all", "probe"):
        print("[probe] is the PCM answering with no session open?")
        d = show(c, "3E", "expect NEG -> noActiveSession if alive in standby")
        show(c, "1A9F", "diagnostic status, answers unlocked")
        if not d:
            print("    no answer -- PCM is not on the bus at all")
        pause("note whether the screen is ON or OFF right now")

    if a.step in ("all", "session"):
        print("\n[session] 10 89, then hold it -- does the screen come up?")
        show(c, "1089", "manufacturer session")
        keepalive(c, a.hold)
        pause("did the screen change during those %d s?" % a.hold)

    if a.step in ("all", "ident"):
        print("\n[ident] identity block (needs the unlock the Autel got)")
        show(c, "2701", "request seed")
        for lid, what in IDENT:
            show(c, "1A" + lid, what)
        for did, what in (("F008", "config"), ("F009", "build date")):
            show(c, "22" + did, what)

    if a.step in ("all", "routines"):
        print("\n[routines] the ones the Autel started, one at a time")
        for payload, what in ROUTINES:
            show(c, "31" + payload, what)
            time.sleep(1.0)
            show(c, "33" + payload[:2], "poll result")
            pause("screen change after %s?" % what)

    print("\ndone -- session will lapse on its own once TesterPresent stops")
    return 0


if __name__ == "__main__":
    sys.exit(main())
