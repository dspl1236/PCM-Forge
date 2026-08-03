#!/usr/bin/env python3
"""Pre-build the static WireView web app's data files.

The viewer in viewer.py needs Python running. This produces JSON so the app in
web/ is pure static -- drop the folder on any web server, point it at the
sv_projects tree, and nothing server-side is required.

    python build.py --out web/data
    python build.py --out web/data --project Cayenne_E2
    python build.py --out web/data --project Cayenne_E2 --no-pins

Writes:
    tree.json                 the whole navigation cascade, all projects
    pins/<project>/<year>.json  pin tables, keyed by sheet

The tree is cheap (one XML parse). Pins mean parsing every sheet SVG, which is
slow, so --project limits it; sheets without a built pin file simply show
nothing in the sidebar rather than erroring.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wireview as W
import viewer as V


def build_tree(lang):
    nodes = V.load_tree(lang)
    # Strip to what the app needs, and drop the pass-through levels here
    # rather than in the browser -- the client should not have to know the
    # index has unlabelled containers in it.
    out = {}
    for nid, n in nodes.items():
        kids = list(n["kids"])
        while len(kids) == 1 and not nodes[kids[0]]["label"] \
                and nodes[kids[0]]["kids"]:
            kids = list(nodes[kids[0]]["kids"])
        kids = [k for k in kids
                if nodes[k]["label"] or nodes[k]["kids"]]
        out[nid] = {"l": n["label"], "p": n["path"], "k": kids}
    return out


def build_pins(project, outdir):
    base = os.path.join(W.ROOT, project)
    if not os.path.isdir(base):
        sys.exit("no such project: %s" % project)
    years = sorted(d for d in os.listdir(base)
                   if os.path.isdir(os.path.join(base, d)))
    os.makedirs(os.path.join(outdir, "pins", project), exist_ok=True)
    total = 0
    for year in years:
        ydir = os.path.join(base, year)
        sheets = sorted(d for d in os.listdir(ydir)
                        if os.path.isfile(os.path.join(ydir, d, "sheet.svg")))
        data = {}
        for sheet in sheets:
            try:
                rows = W.pins(project, year, sheet)
            except SystemExit:
                rows = []
            if rows:
                data[sheet] = [list(r) for r in rows]
                total += len(rows)
        path = os.path.join(outdir, "pins", project, "%s.json" % year)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        print("  %-10s %3d sheets with pins  %6.1f KB"
              % (year, len(data), os.path.getsize(path) / 1024.0))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/data")
    ap.add_argument("--root", default=W.ROOT,
                    help="sv_projects directory")
    ap.add_argument("--project", action="append",
                    help="limit pin extraction (repeatable)")
    ap.add_argument("--lang", default="EN")
    ap.add_argument("--no-pins", action="store_true")
    a = ap.parse_args()

    W.ROOT = a.root
    V.ROOT = a.root
    V._TREE.clear()
    if not os.path.isdir(W.ROOT):
        sys.exit("no such directory: %s" % W.ROOT)

    os.makedirs(a.out, exist_ok=True)

    print("building tree ...")
    tree = build_tree(a.lang)
    p = os.path.join(a.out, "tree.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, separators=(",", ":"))
    print("  %d nodes  %.1f KB\n" % (len(tree), os.path.getsize(p) / 1024.0))

    if a.no_pins:
        return 0
    projects = a.project or sorted(
        d for d in os.listdir(W.ROOT)
        if os.path.isdir(os.path.join(W.ROOT, d)))
    for proj in projects:
        print("pins: %s" % proj)
        n = build_pins(proj, a.out)
        print("  %d pins total\n" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
