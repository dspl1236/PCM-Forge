#!/usr/bin/env python3
"""Talk KWP2000 to the PCM over an SLCAN adapter, doing ISO-TP on the host.

Why not the Cerberus command protocol: the board is sitting in Lawicel SLCAN
mode, which its firmware only leaves on a hardware reset (`is_slcan_cmd` in
src/main.cpp auto-enters on a bare O/C/L/V/F/N or an S<n>, and there is no
software escape). That is also how the 2026-08-04 Autel session got captured --
COM6 was acting as a plain slcan adapter. SLCAN can send and receive arbitrary
frames, so rather than demand a reset we just frame ISO-TP ourselves.

Everything sent here is read-only or session/routine control. No WriteDataBy*,
no RequestDownload, no ClearDiagnosticInformation -- nothing that changes stored
state, so a wrong guess costs a reboot at worst.

    python pcm_slcan.py --port COM6 --step probe
    python pcm_slcan.py --port COM6 --step session --hold 30
    python pcm_slcan.py --port COM6 --step all
"""
import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

PCM_TX, PCM_RX = 0x773, 0x7DD
PAD = 0xFF                       # the Autel pads with FF; match it exactly

# Other addresses reachable on the same wire. The gateway speaks UDS where the
# PCM speaks KWP, so its identifiers are the standard F1xx DIDs rather than the
# 1A sub-identifiers -- same transport, different dialect.
TARGETS = {
    "pcm":     (0x773, 0x7DD),
    "gateway": (0x710, 0x77A),
    "cluster": (0x714, 0x77E),
}

# UDS identifiers worth reading off a gateway.
UDS_DIDS = [("F190", "VIN"), ("F187", "spare part number"),
            ("F189", "software version"), ("F18A", "supplier"),
            ("F18C", "serial number"), ("F191", "hardware number"),
            ("F197", "system name"), ("F19E", "ODX file id"),
            ("F1DF", "programming status")]

SVC = {0x10: "StartDiagnosticSession", 0x14: "ClearDiagnosticInformation",
       0x18: "ReadDTCByStatus", 0x1A: "ReadEcuIdentification",
       0x22: "ReadDataByCommonId", 0x27: "SecurityAccess",
       0x31: "StartRoutineByLocalId", 0x32: "StopRoutineByLocalId",
       0x33: "RequestRoutineResults", 0x3E: "TesterPresent"}
NRC = {0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
       0x22: "conditionsNotCorrect", 0x23: "routineNotComplete",
       0x31: "requestOutOfRange", 0x33: "securityAccessDenied",
       0x35: "invalidKey", 0x78: "responsePending", 0x80: "noActiveSession"}

# None of these need SecurityAccess -- verified on a locked unit, where 1A 91
# still answered. The Autel happens to unlock before reading them, which made
# the capture look like they were gated.
IDENT = [("90", "VIN field"), ("91", "part number"), ("95", "software version"),
         ("9F", "diagnostic status"), ("01", "Porsche part number"),
         ("94", "hardware"), ("83", "coding")]

# The ReadEcuIdentification sub-identifier space is one byte, so it can simply
# be enumerated. KWP reserves 0x00-0x7F for manufacturer use and 0x80-0xFF for
# common identifiers; both are worth sweeping since this unit answers 0x01 and
# 0x83 alike. Anything that comes back is readable without a key.
IDENT_SWEEP = range(0x00, 0x100)

# ReadDataByCommonIdentifier. F0xx is where the two known-good ones live; F1xx
# is where VAG-derived units keep spare-part and supplier data, so both blocks
# are worth walking. The rest of the 16-bit space is large and mostly empty.
DID_BLOCKS = {"F0xx": [0xF000 + i for i in range(0x100)],
              "F1xx": [0xF100 + i for i in range(0x100)]}

# 0B reads back a two-byte state rather than acting; 29 was rejected after 41 s
# of responsePending in the capture, so it is left out of the default walk.
ROUTINES = [("1701", "routine 17, param 01"),
            ("2E01", "routine 2E, param 01"),
            ("0B", "routine 0B (returns state)")]


class Slcan:
    def __init__(self, port, baud=115200, bitrate="6"):
        self.s = serial.Serial(port, baud, timeout=0.05)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        # Close first: the channel may already be open from a previous run, and
        # S<n> is rejected while open.
        for cmd in ("C", "S" + bitrate, "O"):
            self.s.write((cmd + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
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

    def frames(self, seconds):
        """Yield (id, data) for every standard frame seen in the window."""
        end = time.time() + seconds
        buf = b""
        while time.time() < end:
            buf += self.s.read(256)
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip().decode(errors="replace")
                if len(line) >= 5 and line[0] == "t":
                    try:
                        cid = int(line[1:4], 16)
                        dlc = int(line[4], 16)
                        yield cid, bytes.fromhex(line[5:5 + dlc * 2])
                    except ValueError:
                        pass
            time.sleep(0.01)


def request(bus, payload, window=2.0):
    """One KWP request, ISO-TP framed and reassembled. Returns bytes or None."""
    p = bytes(payload)
    bus.send(PCM_TX, bytes([len(p)]) + p)          # single frame; all ours fit

    got, expect, out = None, 0, bytearray()
    deadline = time.time() + window
    while time.time() < deadline:
        for cid, d in bus.frames(0.25):
            if cid != PCM_RX or not d:
                continue
            kind = d[0] >> 4
            if kind == 0:
                svc = d[1:1 + (d[0] & 0x0F)]
                # responsePending: the real answer is still coming
                if len(svc) >= 3 and svc[0] == 0x7F and svc[2] == 0x78:
                    deadline = time.time() + 5.0
                    continue
                return bytes(svc)
            if kind == 1:                          # first frame -> flow control
                expect = ((d[0] & 0x0F) << 8) | d[1]
                out = bytearray(d[2:8])
                bus.send(PCM_TX, b"\x30\x00\x00")
                deadline = time.time() + 3.0
            elif kind == 2 and expect:
                out += d[1:]
                if len(out) >= expect:
                    return bytes(out[:expect])
    return got


def describe(b):
    if not b:
        return "(no answer)"
    if b[0] == 0x7F and len(b) >= 3:
        return "NEG %s -> %s" % (SVC.get(b[1], "%02X" % b[1]),
                                 NRC.get(b[2], "%02X" % b[2]))
    name = SVC.get(b[0] - 0x40, "svc%02X" % (b[0] - 0x40))
    rest = b[1:]
    txt = "".join(chr(x) if 32 <= x < 127 else "." for x in rest)
    printable = sum(32 <= x < 127 for x in rest)
    tail = '  "%s"' % txt if rest and printable >= len(rest) * 0.6 else ""
    return "%s  %s%s" % (name, rest.hex().upper(), tail)


def step(bus, payload_hex, note=""):
    r = request(bus, bytes.fromhex(payload_hex))
    print("    -> %-10s %-46s %s" % (payload_hex, describe(r), note))
    return r


def ascii_of(b):
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b).strip()


def report(bus):
    """One-line-per-field identity summary -- run this on every new unit.

    Deliberately does not open a session or request a seed: everything here
    answers on a locked PCM, so a bare report needs no dealer tool and leaves
    no diagnostic state behind.
    """
    fields = [("1A91", "part number", True), ("1A01", "Porsche part", True),
              ("1A95", "software version", True), ("22F009", "build date", True),
              ("1A90", "VIN field", True), ("1A83", "coding", True),
              ("1A94", "hardware", False), ("22F008", "config", False),
              ("1A9F", "diagnostic status", False)]
    print("PCM identity\n" + "-" * 46)
    for payload, label, is_text in fields:
        r = request(bus, bytes.fromhex(payload))
        if not r:
            print("  %-20s (no answer)" % label)
            continue
        # strip the echoed service byte and sub-identifier
        body = r[2:] if payload.startswith("1A") else r[3:]
        val = ascii_of(body) if is_text else body.hex().upper()
        print("  %-20s %s" % (label, val or body.hex().upper()))


def local_sweep(bus):
    """Enumerate ReadDataByLocalIdentifier, hunting a writable VIN handle.

    `21` (read) and `3B` (write) are a pair -- the PIWIS capture shows both used
    on local ids 08 and 09. `1A 9D` returns the VIN but lives in the
    ECU-identification space, which may be read-only. If the VIN also appears
    under a local id, that is the handle a write would use.

    Read-only. Nothing here writes; the point is to find the identifier before
    anyone sends a 3B at it.
    """
    print("[local] ReadDataByLocalIdentifier 21 00..FF")
    found = locked = 0
    vin_ids = []
    for lid in range(0x100):
        r = request(bus, bytes([0x21, lid]), window=0.5)
        if not r:
            continue
        if r[0] == 0x7F:
            if len(r) >= 3 and r[2] == 0x33:
                locked += 1
                print("   21 %02X  LOCKED (securityAccessDenied)" % lid)
            continue
        found += 1
        body = r[2:]
        s = ascii_of(body)
        mark = ""
        if "WP0" in s or "WP1" in s:
            vin_ids.append(lid)
            mark = "   <<< VIN"
        print("   21 %02X  %-34s %s%s" % (lid, body.hex().upper()[:34], s, mark))
    print("   -> %d readable, %d locked" % (found, locked))
    if vin_ids:
        print("\n   VIN appears at local id(s): %s"
              % " ".join("%02X" % i for i in vin_ids))
        print("   A write would be:  3B %02X <17 ascii bytes>" % vin_ids[0])
        print("   NOT sent here -- needs an unlock and a deliberate decision.")
    else:
        print("\n   VIN not exposed as a local identifier. It is readable at "
              "1A 9D only, so writing it needs whatever service PIWIS uses for "
              "the ECU-identification space, not 3B.")


def uds_report(bus):
    """Identity of a UDS module (the gateway), rather than the PCM's KWP block.

    Reads only; nothing here needs SecurityAccess on the modules tried so far.
    A negative response is reported rather than hidden, because `requestOutOfRange`
    (absent) and `securityAccessDenied` (present but locked) mean different
    things and the difference is the useful part.
    """
    print("UDS identity\n" + "-" * 52)
    for did, label in UDS_DIDS:
        r = request(bus, bytes.fromhex("22" + did))
        if not r:
            print("  %-20s (no answer)" % label)
            continue
        if r[0] == 0x7F:
            nrc = NRC.get(r[2], "%02X" % r[2]) if len(r) >= 3 else "?"
            print("  %-20s -- %s" % (label, nrc))
            continue
        body = r[3:]
        txt = ascii_of(body)
        print("  %-20s %s" % (label, txt if txt else body.hex().upper()))


def read_dtcs(bus):
    """Fault memory over CAN, no PIWIS needed.

    Only `18 00 FF 00` is accepted by this unit -- 18 02 FF 00, 18 00 FF FF,
    17 00 00 and 18 81 FF 00 all come back requestOutOfRange, so the usual
    readDTCByStatus variants are not interchangeable here.

    The reply is `58 <count> <hi lo status>*` -- there IS a count byte. I first
    read it as bare triplets because the survey harness strips two bytes for a
    `61 <id>` echo, which for service 0x18 removes the count as well and leaves
    a clean multiple of three. The count and the triplet count agree, so the
    answer was right by luck; parse both and check they match.

    Descriptions are not in the firmware or in diagnosis.cfg -- service 0x18 is
    not in its code-8 table at all, so fault memory is a separate mechanism
    from the dataflow graph. PIWIS is where the text lives.
    """
    r = request(bus, bytes.fromhex("1800FF00"), window=3.0)
    if not r:
        print("    no answer -- retry, the first request after a session often"
              " returns busyRepeatRequest or nothing")
        return
    if r[0] == 0x7F:
        print("    negative response %s" % r.hex())
        return
    count, body = r[1], r[2:]
    if len(body) % 3:
        print("    %d bytes, not a whole number of triplets: %s"
              % (len(body), body.hex()))
        return
    if count != len(body) // 3:
        print("    header count %d disagrees with %d triplets -- reporting both"
              % (count, len(body) // 3))
    print("    %d stored fault code(s):" % (len(body) // 3))
    for i in range(0, len(body), 3):
        hi, lo, st = body[i], body[i + 1], body[i + 2]
        print("      DTC %02X%02X   status %02X" % (hi, lo, st))


def sweep(bus):
    """Enumerate every readable identifier, so we stop guessing which exist.

    Both spaces are small enough to walk exhaustively, and a negative response
    is as informative as a positive one -- requestOutOfRange means the
    identifier is absent, where securityAccessDenied would mean it exists but
    is locked. Nothing here writes.
    """
    print("[sweep] ReadEcuIdentification 1A 00..FF")
    found = 0
    for lid in IDENT_SWEEP:
        r = request(bus, bytes([0x1A, lid]), window=0.5)
        if not r or r[0] == 0x7F:
            continue
        found += 1
        body = r[2:]
        print("   1A %02X  %-34s %s" % (lid, body.hex().upper()[:34],
                                        ascii_of(body)))
    print("   -> %d readable\n" % found)

    for name, block in DID_BLOCKS.items():
        print("[sweep] ReadDataByCommonIdentifier %s" % name)
        found = locked = 0
        for did in block:
            r = request(bus, bytes([0x22, did >> 8, did & 0xFF]), window=0.5)
            if not r:
                continue
            if r[0] == 0x7F:
                # 0x33 means the identifier EXISTS but is locked -- that is a
                # target for the key, unlike 0x31 which means absent.
                if len(r) >= 3 and r[2] == 0x33:
                    locked += 1
                    print("   22 %04X  LOCKED (securityAccessDenied)" % did)
                continue
            found += 1
            body = r[3:]
            print("   22 %04X  %-32s %s" % (did, body.hex().upper()[:32],
                                            ascii_of(body)))
        print("   -> %d readable, %d locked\n" % (found, locked))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--bitrate", default="6", help="slcan S code; 6 = 500 kbps")
    ap.add_argument("--hold", type=int, default=30)
    ap.add_argument("--step", default="probe",
                    choices=["probe", "session", "ident", "version", "sweep",
                             "local", "routines", "dtc", "all"])
    ap.add_argument("--send", help="comma-separated hex payloads to send one "
                                   "at a time, e.g. 2701,311701")
    ap.add_argument("--no-session", action="store_true",
                    help="skip the 10 89 that --send normally opens with")
    ap.add_argument("--target", default="pcm", choices=sorted(TARGETS),
                    help="which ECU to address (default pcm)")
    a = ap.parse_args()

    # Rebind the module-level pair rather than thread it through every call --
    # one target per invocation, and the ISO-TP helpers all reference these.
    global PCM_TX, PCM_RX
    PCM_TX, PCM_RX = TARGETS[a.target]
    if a.target != "pcm":
        print("addressing %s: %03X/%03X" % (a.target, PCM_TX, PCM_RX))

    # --send exists because the routines have to be fired individually: run
    # them back to back and a screen change cannot be attributed to any one of
    # them. The session is opened first because 31 is rejected without one, and
    # held afterwards so a slow reaction is not missed.
    if a.send:
        bus = Slcan(a.port, a.baud, a.bitrate)
        print("slcan open on %s at 500 kbps\n" % a.port)
        try:
            if not a.no_session:
                step(bus, "1089", "open manufacturer session")
            for p in [x.strip() for x in a.send.split(",") if x.strip()]:
                step(bus, p)
            if a.hold:
                n, end = 0, time.time() + a.hold
                while time.time() < end:
                    request(bus, b"\x3E", window=0.6)
                    n += 1
                print("    held %d s (%d TesterPresent)" % (a.hold, n))
        finally:
            bus.close()
        return 0

    bus = Slcan(a.port, a.baud, a.bitrate)
    print("slcan open on %s at 500 kbps\n" % a.port)
    try:
        if a.step in ("probe", "all"):
            print("[probe] does the PCM answer with no session open?")
            step(bus, "3E", "expect NEG -> noActiveSession if alive in standby")
            step(bus, "1A9F", "diagnostic status, answers unlocked")

        if a.step in ("session", "all"):
            print("\n[session] 10 89, then hold it")
            step(bus, "1089", "manufacturer session")
            n, end = 0, time.time() + a.hold
            while time.time() < end:
                request(bus, b"\x3E", window=0.6)
                n += 1
            print("    held %d s (%d TesterPresent)" % (a.hold, n))

        if a.step in ("ident", "all"):
            print("\n[ident] identity block -- none of this needs a key")
            step(bus, "1089", "open session (so 27 01 can answer)")
            step(bus, "2701", "request seed")
            for lid, what in IDENT:
                step(bus, "1A" + lid, what)
            step(bus, "22F008", "config")
            step(bus, "22F009", "build date")

        if a.step == "version":
            if a.target == "pcm":
                report(bus)
            else:
                uds_report(bus)

        if a.step == "sweep":
            sweep(bus)

        if a.step == "local":
            local_sweep(bus)

        if a.step in ("dtc", "all"):
            print("[dtc] fault memory")
            read_dtcs(bus)

        if a.step in ("routines", "all"):
            print("\n[routines] one at a time")
            for p, what in ROUTINES:
                step(bus, "31" + p, what)
                time.sleep(1.0)
                step(bus, "33" + p[:2], "poll result")

        print("\ndone -- session lapses once TesterPresent stops")
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
