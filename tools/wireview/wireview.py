#!/usr/bin/env python3
"""Extract connector pinouts from Porsche WireView (SchaltplanViewer) data.

WireView ships each wiring sheet as an SVG with every label as a real text
node, so pinouts can be recovered exactly rather than transcribed by hand from
screenshots. Labels are rotated -90 degrees, which means one connector pin is a
*column*: all of its text shares an x coordinate and stacks along y.

    python wireview.py projects
    python wireview.py sheets Cayenne_E2 MJ0D_kab
    python wireview.py pins   Cayenne_E2 MJ0D_kab 20
    python wireview.py pins   Cayenne_E2 MJ0D_kab 20 --md
    python wireview.py grep   "CAN LOW" Cayenne_E2 MJ0D_kab

Sheet numbers match the cross-references printed on the diagrams themselves --
"/30A.4G" means sheet 30A, grid square 4G -- so a reference on one sheet can be
followed straight to the folder holding the next.

Model year folders are MJ0B..MJ0J for 2011..2018. Point ROOT at the install.
"""
import os
import re
import sys
from collections import defaultdict

ROOT = os.environ.get(
    "WIREVIEW_ROOT",
    r"D:\PCM\SchaltplanViewer\SchaltplanViewer\data\sv_projects")

LANG = "en"

# A9, B12, L5S, M1 ... connector pin designations
PIN_RE = re.compile(r"^[A-Z]{1,2}\d{1,3}S?$")
# OG BN 0.35, RD YE 2.5, BLK BLK 0.35
WIRE_RE = re.compile(r"^[A-Z]{2,3} [A-Z]{2,3} \d+\.\d+$")
# bare wire / segment numbers
NUM_RE = re.compile(r"^(SL)?\d{4,6}$")
# destination refs printed at the far end of a wire: splice points like
# "Y451 / SP_SC51_P", component refs like "W281.1 / A1", sheet grid refs
# like "/17_1.15G". Never the signal name.
DEST_RE = re.compile(r"^(Y\d|[A-Z]\d{3}\s*\.|/\d)|/\s*(SP_|[A-Z]\d)")

TEXT_RE = re.compile(
    r'<text\b[^>]*?\bx="(-?[\d.]+)"[^>]*?\by="(-?[\d.]+)"[^>]*?>(.*?)</text>',
    re.S)
SWITCH_RE = re.compile(r"<switch\b.*?</switch>", re.S)
LANG_G_RE = re.compile(r'<g systemLanguage="(\w+)"\s*>(.*?)</g>', re.S)


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return s.strip()


TRANSLATE_RE = re.compile(r"translate\(\s*(-?[\d.]+)[,\s]+(-?[\d.]+)")
MATRIX_RE = re.compile(r"matrix\(" + r"[,\s]+".join([r"(-?[\d.]+)"] * 6))
TAG_RE = re.compile(r"<(/?)(g|text|switch)\b([^>]*?)(/?)>", re.S)


def _offset(attrs):
    """Translation contributed by one element's transform attribute."""
    t = re.search(r'transform="([^"]*)"', attrs)
    if not t:
        return 0.0, 0.0
    v = t.group(1)
    m = TRANSLATE_RE.search(v)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = MATRIX_RE.search(v)
    if m:                                   # e, f carry the translation
        return float(m.group(5)), float(m.group(6))
    return 0.0, 0.0


def texts(path):
    """Every text node as (x, y, content) in GLOBAL coordinates.

    Connectors are wrapped in <g transform="translate(...)">, so raw x values
    are local and collide across connectors -- two different plugs both have a
    pin near x=4.9. Walking the tag stream and accumulating the translation
    keeps columns distinct.

    Inside a <switch> only the chosen language is kept, otherwise every label
    appears ten times over.
    """
    svg = open(path, encoding="utf-8", errors="replace").read()
    out = []
    stack = [(0.0, 0.0)]
    skip_to = 0

    for m in TAG_RE.finditer(svg):
        if m.start() < skip_to:
            continue
        closing, tag, attrs, selfclose = m.groups()

        if tag == "switch" and not closing:
            # Take the whole block at once and choose one language branch.
            # Scanning branch-by-branch cannot know whether the preferred
            # language appears later, so it ends up emitting several.
            end = svg.find("</switch>", m.start())
            block = svg[m.start():end]
            skip_to = end
            pick = None
            first = None
            for lm in LANG_G_RE.finditer(block):
                if first is None:
                    first = lm.group(2)
                if lm.group(1) == LANG:
                    pick = lm.group(2)
                    break
            chunk = pick if pick is not None else first
            if not chunk:
                continue
            tm = TEXT_RE.search(chunk)
            if tm:
                px, py = stack[-1]
                body = _clean(tm.group(3))
                if body:
                    out.append((px + float(tm.group(1)),
                                py + float(tm.group(2)), body))
            continue

        if tag == "g":
            if closing:
                if len(stack) > 1:
                    stack.pop()
            elif not selfclose:
                dx, dy = _offset(attrs)
                px, py = stack[-1]
                stack.append((px + dx, py + dy))
            continue

        if tag == "text" and not closing:
            chunk = svg[m.start():svg.find("</text>", m.start()) + 7]
            tm = TEXT_RE.search(chunk)
            if not tm:
                continue
            px, py = stack[-1]
            body = _clean(tm.group(3))
            if body:
                out.append((px + float(tm.group(1)),
                            py + float(tm.group(2)), body))
    return out


def _mode_offset(pins_, others, span=6.0, bin_=0.25, above=True):
    """Find the constant x-offset between a pin label and its own annotation.

    Sheets do not agree on this. On the PCM sheet a signal name sits directly
    above its pin (offset ~0); on the gateway sheet it is 2.98 to the right.
    Guessing wrong silently shifts every signal onto its neighbour's pin, so
    rather than assume, take every plausible (pin, annotation) pairing, build a
    histogram of their x deltas, and use the mode -- the real offset is the one
    that recurs across the whole connector.
    """
    hist = defaultdict(int)
    for px, py, _ in pins_:
        for ox, oy, _ in others:
            # signal names print above their pin, wire specs below it
            if (oy >= py) if above else (oy <= py):
                continue
            d = ox - px
            if abs(d) <= span:
                hist[round(d / bin_)] += 1
    if not hist:
        return 0.0
    return max(hist.items(), key=lambda kv: kv[1])[0] * bin_


def _nearest(px, py, cands, offset, xtol=1.2):
    """The candidate sitting at the expected offset, closest in y."""
    best = None
    for cx, cy, cs in cands:
        if cy >= py or abs(cx - px - offset) > xtol:
            continue
        d = py - cy
        if best is None or d < best[0]:
            best = (d, cs)
    return best[1] if best else ""


def pins(project, year, sheet):
    path = os.path.join(ROOT, project, year, sheet, "sheet.svg")
    if not os.path.isfile(path):
        sys.exit("no such sheet: %s" % path)
    items = texts(path)
    pin_ts = [(x, y, s) for x, y, s in items
              if PIN_RE.match(s) and not s.startswith("Y")]
    wire_ts = [(x, y, s) for x, y, s in items if WIRE_RE.match(s)]
    sig_ts = [(x, y, s) for x, y, s in items
              if not PIN_RE.match(s) and not WIRE_RE.match(s)
              and not NUM_RE.match(s) and not s.isdigit()
              and not DEST_RE.match(s) and not s.startswith("SP_")
              and len(s) > 1]

    sig_off = _mode_offset(pin_ts, sig_ts)
    wire_off = _mode_offset(pin_ts, wire_ts, above=False) if wire_ts else 0.0

    rows = []
    for px, py, pin in pin_ts:
        signal = _nearest(px, py, sig_ts, sig_off)
        if not signal:
            continue                        # a pin with no label is not ours
        wire, best = "", None
        for wx, wy, ws in wire_ts:
            if wy <= py or abs(wx - px - wire_off) > 1.2:
                continue
            d = wy - py
            if best is None or d < best[0]:
                best = (d, ws)
        if best:
            wire = best[1]
        rows.append((pin, signal, wire))

    seen, uniq = set(), []
    for r in rows:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    uniq.sort(key=lambda r: (re.sub(r"\d.*", "", r[0]),
                             int(re.sub(r"\D", "", r[0]) or 0)))
    return uniq


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]

    if cmd == "projects":
        for d in sorted(os.listdir(ROOT)):
            print("  " + d)
        return 0

    if cmd == "sheets":
        base = os.path.join(ROOT, argv[1], argv[2])
        names = sorted(os.listdir(base))
        for i in range(0, len(names), 10):
            print("  " + "  ".join("%-5s" % n for n in names[i:i + 10]))
        print("\n%d sheets" % len(names))
        return 0

    if cmd == "pins":
        rows = pins(argv[1], argv[2], argv[3])
        md = "--md" in argv
        if md:
            print("| pin | signal | wire |")
            print("|-----|--------|------|")
            for r in rows:
                print("| %s | %s | %s |" % r)
        else:
            print("  %-6s %-40s %s" % ("pin", "signal", "wire"))
            for r in rows:
                print("  %-6s %-40s %s" % r)
        print("\n%d pins" % len(rows))
        return 0

    if cmd == "grep":
        needle, project, year = argv[1].lower(), argv[2], argv[3]
        base = os.path.join(ROOT, project, year)
        for sheet in sorted(os.listdir(base)):
            p = os.path.join(base, sheet, "sheet.svg")
            if not os.path.isfile(p):
                continue
            hits = [s for _, _, s in texts(p) if needle in s.lower()]
            if hits:
                uniq = sorted(set(hits))
                print("  %-5s  %s" % (sheet, "; ".join(uniq[:6])))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
