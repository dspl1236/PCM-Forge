#!/usr/bin/env python3
"""Serve the static WireView app for local use.

The app is pure static, but it needs three things on the same origin: itself,
the SVG tree, and WireView's own stylesheets. On a real web server those are
alias/location rules. This does the same thing for local use so the layout can
be tested exactly as it will be deployed.

    python serve.py
    python serve.py --install "D:\\PCM\\SchaltplanViewer\\SchaltplanViewer"

Equivalent nginx:

    location /            { root /srv/wireview/web; }
    location /sv_projects { alias /srv/SchaltplanViewer/data/sv_projects; }
    location /style_sheets{ alias /srv/SchaltplanViewer/style_sheets; }

Serves read-only and binds to localhost. This is licensed Porsche data; put
authentication in front of it before exposing it anywhere.
"""
import argparse
import os
import posixpath
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
MOUNTS = {}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def translate_path(self, path):
        p = unquote(path.split("?", 1)[0].split("#", 1)[0])
        p = posixpath.normpath(p).lstrip("/")
        top = p.split("/", 1)[0]
        if top in MOUNTS:
            rest = p[len(top):].lstrip("/")
            full = os.path.normpath(os.path.join(MOUNTS[top], rest))
            if not full.startswith(os.path.normpath(MOUNTS[top])):
                return HERE                      # refuse to climb out
            return full
        full = os.path.normpath(os.path.join(HERE, p))
        return full if full.startswith(HERE) else HERE

    def end_headers(self):
        # Cache the big immutable data, never the app itself -- caching the
        # app means editing wireview.css and reloading to no visible effect,
        # which is a maddening way to lose ten minutes.
        top = self.path.lstrip("/").split("/", 1)[0]
        if top in MOUNTS:
            self.send_header("Cache-Control", "public, max-age=3600")
        else:
            self.send_header("Cache-Control", "no-store")
        SimpleHTTPRequestHandler.end_headers(self)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8732)
    ap.add_argument("--install",
                    default=r"D:\PCM\SchaltplanViewer\SchaltplanViewer",
                    help="the SchaltplanViewer folder")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    sheets = os.path.join(a.install, "data", "sv_projects")
    styles = os.path.join(a.install, "style_sheets")
    for label, p in (("sv_projects", sheets), ("style_sheets", styles)):
        if not os.path.isdir(p):
            sys.exit("missing %s: %s" % (label, p))
        MOUNTS[label] = p

    url = "http://127.0.0.1:%d/wireview.html" % a.port
    print("app     %s" % HERE)
    print("sheets  %s" % sheets)
    print("styles  %s" % styles)
    print("\n%s\nCtrl-C to stop" % url)
    if not a.no_browser:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
