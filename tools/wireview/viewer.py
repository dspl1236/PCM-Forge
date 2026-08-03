#!/usr/bin/env python3
"""Local browser viewer for Porsche WireView (SchaltplanViewer) data.

The bundled WireView.exe does not run from a copied folder, but the sheets are
plain SVG, so a browser renders them directly. This serves them with the
extracted pinout table alongside, and makes the cross-references clickable.

    python viewer.py                 serve on http://127.0.0.1:8731
    python viewer.py --port 9000
    python viewer.py --root "D:\\path\\to\\sv_projects"

Sheets carry ten language variants inside <switch> elements; browsers pick by
their own locale, which usually means German. Each sheet is localised on the
way out so the labels match what the extractor reports.

Binds to localhost only. This is licensed Porsche data -- do not expose it.
"""
import argparse
import html
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wireview as W

ROOT = W.ROOT
LANG = "en"

# "/30A.4G" and "/17_1.15G" -- sheet, then grid square
XREF_RE = re.compile(r"/([0-9]{1,2}[A-Z]?(?:_\d)?)\.(\d{1,2}[A-Z])")

CSS = """
:root { --bg:#0a0a0c; --panel:#141419; --line:#26262e;
        --fg:#e8e8ea; --dim:#8a8a96; --accent:#c8a44e; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:14px/1.5 "Segoe UI",system-ui,sans-serif; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
header { padding:10px 16px; background:var(--panel);
         border-bottom:1px solid var(--line); display:flex;
         align-items:center; gap:16px; flex-wrap:wrap; position:sticky;
         top:0; z-index:10; }
header h1 { font-size:15px; margin:0; font-weight:600; letter-spacing:.02em; }
header .crumb { color:var(--dim); }
main { padding:16px; }
.grid { display:flex; flex-wrap:wrap; gap:6px; }
.grid a { display:block; padding:7px 12px; background:var(--panel);
          border:1px solid var(--line); border-radius:4px; min-width:62px;
          text-align:center; }
.grid a:hover { border-color:var(--accent); text-decoration:none; }
.split { display:flex; gap:16px; align-items:flex-start; }
.sheet { flex:1 1 auto; min-width:0; background:#fff; border-radius:4px;
         overflow:auto; padding:8px; }
.sheet svg { width:100%; height:auto; }
aside { flex:0 0 340px; position:sticky; top:56px; max-height:calc(100vh - 72px);
        overflow:auto; background:var(--panel); border:1px solid var(--line);
        border-radius:4px; padding:12px; }
aside h2 { font-size:13px; margin:0 0 8px; color:var(--accent);
           text-transform:uppercase; letter-spacing:.06em; }
table { width:100%; border-collapse:collapse; font-size:12px; }
td { padding:3px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
td.pin { color:var(--accent); font-family:Consolas,monospace; white-space:nowrap; }
td.wire { color:var(--dim); font-family:Consolas,monospace; font-size:11px; }
input[type=search] { background:var(--bg); border:1px solid var(--line);
    color:var(--fg); padding:6px 10px; border-radius:4px; width:240px; }
.zoom button { background:var(--panel); color:var(--fg);
    border:1px solid var(--line); border-radius:4px; padding:5px 10px;
    cursor:pointer; font-size:13px; }
.zoom button:hover { border-color:var(--accent); }
.hit { padding:6px 0; border-bottom:1px solid var(--line); }
.hit .where { color:var(--accent); font-family:Consolas,monospace; }
.empty { color:var(--dim); font-style:italic; }
"""

ZOOM_JS = """
let z = 1;
const box = document.querySelector('.sheet');
function setZoom(v){ z = Math.min(8, Math.max(0.2, v));
  const s = box.querySelector('svg'); if (s) s.style.width = (z*100)+'%'; }
document.querySelectorAll('[data-zoom]').forEach(b =>
  b.onclick = () => setZoom(b.dataset.zoom === 'in' ? z*1.35
                     : b.dataset.zoom === 'out' ? z/1.35 : 1));
"""


def safe(*parts):
    """Join under ROOT, refusing anything that climbs out."""
    p = os.path.abspath(os.path.join(ROOT, *parts))
    if not p.startswith(os.path.abspath(ROOT)):
        raise ValueError("path escapes root")
    return p


def localize(svg, lang=LANG):
    """Collapse each <switch> to a single language branch."""
    def pick(m):
        block = m.group(0)
        first = None
        for lm in W.LANG_G_RE.finditer(block):
            if first is None:
                first = lm.group(2)
            if lm.group(1) == lang:
                return lm.group(2)
        return first or ""
    return W.SWITCH_RE.sub(pick, svg)


def linkify(svg, project, year):
    """Turn printed sheet cross-references into anchors."""
    def rep(m):
        sheet, grid = m.group(1), m.group(2)
        if not os.path.isdir(safe(project, year, sheet)):
            return m.group(0)
        href = "/p/%s/%s/%s" % (quote(project), quote(year), quote(sheet))
        return ('<a href="%s" target="_top" style="fill:#0645ad">%s</a>'
                % (href, m.group(0)))
    # only inside text nodes, so path data is never touched
    return re.sub(r"(<text\b[^>]*>)(.*?)(</text>)",
                  lambda t: t.group(1) + XREF_RE.sub(rep, t.group(2)) +
                  t.group(3), svg, flags=re.S)


def page(title, crumb, body):
    return """<!doctype html><meta charset="utf-8">
<title>%s</title><style>%s</style>
<header><h1>WireView</h1><span class="crumb">%s</span>
<form action="/search" style="margin-left:auto">
<input type="search" name="q" placeholder="search all sheets&hellip;"
 value="">%s</form></header><main>%s</main>""" % (
        html.escape(title), CSS, crumb, "", body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="text/html; charset=utf-8"):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        try:
            if not parts:
                return self.index()
            if parts[0] == "search":
                q = parse_qs(u.query).get("q", [""])[0]
                return self.search(q)
            if parts[0] == "svg" and len(parts) == 4:
                return self.svg(parts[1], parts[2], parts[3])
            if parts[0] == "p":
                if len(parts) == 2:
                    return self.years(parts[1])
                if len(parts) == 3:
                    return self.sheets(parts[1], parts[2])
                if len(parts) == 4:
                    return self.sheet(parts[1], parts[2], parts[3])
        except Exception as e:
            self.send(page("error", "", "<p class='empty'>%s</p>"
                           % html.escape(str(e))))
            return
        self.send_error(404)

    def index(self):
        items = "".join('<a href="/p/%s">%s</a>' % (quote(d), html.escape(d))
                        for d in sorted(os.listdir(ROOT))
                        if os.path.isdir(safe(d)))
        self.send(page("WireView", "projects",
                       '<div class="grid">%s</div>' % items))

    def years(self, project):
        items = "".join('<a href="/p/%s/%s">%s</a>'
                        % (quote(project), quote(d), html.escape(d))
                        for d in sorted(os.listdir(safe(project))))
        crumb = html.escape(project)
        self.send(page(project, crumb, '<div class="grid">%s</div>' % items))

    def sheets(self, project, year):
        items = "".join('<a href="/p/%s/%s/%s">%s</a>'
                        % (quote(project), quote(year), quote(d),
                           html.escape(d))
                        for d in sorted(os.listdir(safe(project, year))))
        crumb = '<a href="/p/%s">%s</a> / %s' % (
            quote(project), html.escape(project), html.escape(year))
        self.send(page(year, crumb, '<div class="grid">%s</div>' % items))

    def svg(self, project, year, sheet):
        path = safe(project, year, sheet, "sheet.svg")
        raw = open(path, encoding="utf-8", errors="replace").read()
        self.send(linkify(localize(raw), project, year),
                  "image/svg+xml; charset=utf-8")

    def sheet(self, project, year, sheet):
        try:
            rows = W.pins(project, year, sheet)
        except SystemExit:
            rows = []
        if rows:
            table = "<table>%s</table>" % "".join(
                '<tr><td class="pin">%s</td><td>%s</td>'
                '<td class="wire">%s</td></tr>'
                % (html.escape(p), html.escape(s), html.escape(w))
                for p, s, w in rows)
        else:
            table = "<p class='empty'>no connector pins found on this sheet</p>"

        crumb = ('<a href="/p/%s">%s</a> / <a href="/p/%s/%s">%s</a> / %s'
                 % (quote(project), html.escape(project), quote(project),
                    quote(year), html.escape(year), html.escape(sheet)))
        raw = open(safe(project, year, sheet, "sheet.svg"),
                   encoding="utf-8", errors="replace").read()
        # drop the XML prolog and DOCTYPE -- this is being inlined into HTML,
        # where a stray <?xml ...?> renders as text
        raw = re.sub(r"<\?xml.*?\?>|<!DOCTYPE.*?>", "", raw, flags=re.S)
        drawing = linkify(localize(raw), project, year)

        body = """
<div class="zoom" style="margin-bottom:10px">
  <button data-zoom="out">&minus;</button>
  <button data-zoom="reset">reset</button>
  <button data-zoom="in">+</button>
</div>
<div class="split">
  <div class="sheet">%s</div>
  <aside><h2>pinout &mdash; sheet %s</h2>%s</aside>
</div><script>%s</script>""" % (drawing, html.escape(sheet), table, ZOOM_JS)
        self.send(page("%s %s" % (year, sheet), crumb, body))

    def search(self, q):
        if not q:
            return self.send(page("search", "search",
                                  "<p class='empty'>enter a term</p>"))
        needle = q.lower()
        out = []
        for project in sorted(os.listdir(ROOT)):
            pdir = safe(project)
            if not os.path.isdir(pdir):
                continue
            for year in sorted(os.listdir(pdir)):
                ydir = safe(project, year)
                if not os.path.isdir(ydir):
                    continue
                for sheet in sorted(os.listdir(ydir)):
                    p = os.path.join(ydir, sheet, "sheet.svg")
                    if not os.path.isfile(p):
                        continue
                    hits = sorted({s for _, _, s in W.texts(p)
                                   if needle in s.lower()})
                    if hits:
                        out.append(
                            '<div class="hit"><a class="where" '
                            'href="/p/%s/%s/%s">%s / %s / %s</a><br>%s</div>'
                            % (quote(project), quote(year), quote(sheet),
                               html.escape(project), html.escape(year),
                               html.escape(sheet),
                               html.escape("; ".join(hits[:8]))))
        body = "".join(out) or "<p class='empty'>no matches</p>"
        self.send(page("search: " + q, "search &mdash; " + html.escape(q),
                       body))


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    ROOT = a.root
    W.ROOT = a.root
    if not os.path.isdir(ROOT):
        sys.exit("no such directory: %s" % ROOT)

    url = "http://127.0.0.1:%d/" % a.port
    print("serving %s\n        %s" % (ROOT, url))
    print("Ctrl-C to stop")
    if not a.no_browser:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
