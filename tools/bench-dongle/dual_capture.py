#!/usr/bin/env python3
"""Capture CAN MMI and the diagnostic bus together, on one clock.

Built for watching PIWIS code the PCM. The prize is the SecurityAccess
exchange -- a VIN write has to unlock first, so `27 01` / `27 02` will cross the
wire with a live seed and the key that answers it, which is the thing five
separate approaches failed to recover from firmware.

**One process, one clock.** The previous dual-bus capture used two tools that
stamped in different units -- the CANable in milliseconds, the Nano in seconds
-- and correlating them without noticing produced a confident wrong conclusion.
Both adapters are read here by one program against one `time.time()`, so the
two logs are directly comparable by construction.

    python dual_capture.py --mmi COM5 --diag COM6 --out piwis

Writes `piwis_mmi.log`, `piwis_diag.log` and `piwis_merged.log`, and prints the
interesting traffic live: sessions, SecurityAccess, writes and routines, with
ISO-TP reassembled so the service is readable rather than a frame dump.

Passive. Nothing is transmitted onto either bus except the slcan open, and the
adapters ACK as any bus node does.
"""
import argparse
import sys
import threading
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  python -m pip install pyserial")

# request -> response pairs worth reassembling
PAIRS = {0x773: 0x7DD, 0x710: 0x77A, 0x714: 0x77E}
RESP = {v: k for k, v in PAIRS.items()}

SVC = {0x10: "DiagnosticSessionControl", 0x11: "ECUReset",
       0x14: "ClearDiagnosticInformation", 0x18: "ReadDTCByStatus",
       0x19: "ReadDTC", 0x1A: "ReadEcuIdentification",
       0x22: "ReadDataByIdentifier", 0x23: "ReadMemoryByAddress",
       0x27: "SecurityAccess", 0x2E: "WriteDataByIdentifier",
       0x2F: "InputOutputControl", 0x31: "RoutineControl",
       0x32: "StopRoutine", 0x33: "RequestRoutineResults",
       0x34: "RequestDownload", 0x36: "TransferData",
       0x37: "RequestTransferExit", 0x3B: "WriteDataByLocalId",
       0x3E: "TesterPresent", 0x85: "ControlDTCSetting"}
NRC = {0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
       0x22: "conditionsNotCorrect", 0x31: "requestOutOfRange",
       0x33: "securityAccessDenied", 0x35: "invalidKey",
       0x36: "exceedNumberOfAttempts", 0x37: "requiredTimeDelayNotExpired",
       0x78: "responsePending", 0x80: "noActiveSession"}

# Services worth shouting about. TesterPresent and repeated reads are noise.
LOUD = {0x27, 0x2E, 0x3B, 0x31, 0x34, 0x36, 0x37, 0x11, 0x10, 0x14, 0x2F}


class Bus(threading.Thread):
    """One slcan adapter, timestamped against the shared process clock."""

    def __init__(self, port, tag, rows, lock, baud=115200, bitrate="6"):
        super().__init__(daemon=True)
        self.tag, self.rows, self.lock, self.stop = tag, rows, lock, False
        self.s = serial.Serial(port, baud, timeout=0.02)
        time.sleep(1.5)
        self.s.reset_input_buffer()
        for c in ("C", "S" + bitrate, "O"):
            self.s.write((c + "\r").encode())
            time.sleep(0.15)
            self.s.read(64)
        self.s.reset_input_buffer()

    def close(self):
        try:
            self.s.write(b"C\r")
            time.sleep(0.1)
        finally:
            self.s.close()

    def run(self):
        buf = b""
        while not self.stop:
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
                    data = line[2 + n:2 + n + dlc * 2].upper()
                    with self.lock:
                        self.rows.append((time.time(), self.tag, cid, data))
            time.sleep(0.002)


class IsoTp:
    """Reassemble per CAN id, so a multi-frame answer prints as one service."""

    def __init__(self):
        self.part = {}

    def feed(self, cid, data):
        try:
            b = bytes.fromhex(data)
        except ValueError:
            return None
        if not b:
            return None
        kind = b[0] >> 4
        if kind == 0:
            return bytes(b[1:1 + (b[0] & 0x0F)])
        if kind == 1:
            self.part[cid] = [((b[0] & 0x0F) << 8) | b[1] - 6, bytearray(b[2:8])]
            return None
        if kind == 2 and cid in self.part:
            st = self.part[cid]
            st[1] += b[1:]
            if len(st[1]) >= st[0]:
                out = bytes(st[1])
                del self.part[cid]
                return out
        return None


def describe(msg, is_req):
    if not msg:
        return None
    s = msg[0]
    if s == 0x7F and len(msg) >= 3:
        return "NEG %s -> %s" % (SVC.get(msg[1], "%02X" % msg[1]),
                                 NRC.get(msg[2], "%02X" % msg[2]))
    base = s if is_req else s - 0x40
    if base not in LOUD:
        return None
    name = SVC.get(base, "svc%02X" % base)
    rest = msg[1:]
    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in rest)
    pr = sum(32 <= c < 127 for c in rest)
    tail = '  "%s"' % txt if rest and pr >= len(rest) * 0.6 else ""
    return "%s%s %s%s" % ("" if is_req else "ok ", name, rest.hex().upper(), tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mmi", required=True)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--out", default="piwis")
    ap.add_argument("--minutes", type=float, default=90.0)
    a = ap.parse_args()

    rows, lock = [], threading.Lock()
    mmi = Bus(a.mmi, "MMI", rows, lock)
    diag = Bus(a.diag, "DIAG", rows, lock)
    mmi.start()
    diag.start()
    t0 = time.time()

    print("capturing  MMI=%s  DIAG=%s  -> %s_*.log" % (a.mmi, a.diag, a.out))
    print("one clock for both buses. Ctrl-C when the PIWIS work is done.\n")
    print("watching for: SecurityAccess, writes, routines, session changes\n")

    tp, seen, seeds = IsoTp(), 0, []
    try:
        while time.time() - t0 < a.minutes * 60:
            time.sleep(0.25)
            with lock:
                batch, n = rows[seen:], len(rows)
            seen = n
            for t, tag, cid, data in batch:
                if cid not in PAIRS and cid not in RESP:
                    continue
                msg = tp.feed(cid, data)
                if not msg:
                    continue
                is_req = cid in PAIRS
                d = describe(msg, is_req)
                if not d:
                    continue
                print("  %8.2fs %-4s %03X  %s" % (t - t0, tag, cid, d))
                # the whole point: capture seed and key together
                if msg[0] in (0x27, 0x67) and len(msg) >= 2:
                    seeds.append((t - t0, cid, msg.hex().upper()))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        mmi.stop = diag.stop = True
        time.sleep(0.3)
        with lock:
            allrows = sorted(rows)
        for tag, name in (("MMI", "_mmi"), ("DIAG", "_diag")):
            with open(a.out + name + ".log", "w", encoding="utf-8") as fh:
                for t, g, cid, data in allrows:
                    if g == tag:
                        fh.write("%.4f %03X %s\n" % (t - t0, cid, data))
        with open(a.out + "_merged.log", "w", encoding="utf-8") as fh:
            for t, g, cid, data in allrows:
                fh.write("%.4f %-4s %03X %s\n" % (t - t0, g, cid, data))
        mmi.close()
        diag.close()

    print("\n%d frames total, written to %s_{mmi,diag,merged}.log"
          % (len(allrows), a.out))
    if seeds:
        print("\nSecurityAccess traffic captured -- this is the useful part:")
        for t, cid, hx in seeds:
            print("   %8.2fs %03X  %s" % (t, cid, hx))
    else:
        print("\nNo SecurityAccess seen. If PIWIS did write something, it did "
              "not unlock on a bus we were watching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
