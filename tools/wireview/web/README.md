# WireView — static web app

Browser front-end for Porsche WireView (SchaltplanViewer) wiring diagrams.
Pure static: HTML, CSS and one JS file. No server-side code, no database.

The bundled `WireView.exe` does not run from a copied folder, but the sheets
are plain SVG, so a browser renders them directly.

## Layout

    wireview.html      entry page
    wireview.css       styling, including the print rules
    wireview.js        navigation, rendering, export
    serve.py           local dev server (not needed in production)
    data/
      tree.json        navigation cascade, all projects — built by ../build.py
      pins/<project>/<year>.json   extracted pin tables

## What it needs at runtime

Three things on the same origin:

| path | contents |
|------|----------|
| `/` | this folder |
| `/sv_projects` | the WireView `data/sv_projects` tree (the SVG sheets) |
| `/style_sheets` | the WireView `style_sheets` folder |

The stylesheets are not optional. `common.css` carries `path {fill:none}` and
the stroke widths; `sv_sheet.css` carries `.frame {fill:white}` and
`.text {fill:black}`. Without them a sheet renders as a black slab, or as a
page of solid-filled blobs.

Adjust `CONFIG` at the top of `wireview.js` if the paths differ.

## Building the data

    python ../build.py --out data                      # everything
    python ../build.py --out data --project Cayenne_E2 # one car
    python ../build.py --out data --no-pins            # navigation only

`tree.json` covers every project in one pass and is cheap. Pin extraction
parses each sheet SVG, so it is the slow part — but a sheet with no built pin
file simply shows an empty sidebar rather than failing, so partial builds are
fine.

## Local use

    python serve.py

Serves on `http://127.0.0.1:8732/wireview.html` with the two data mounts
wired up, so the layout can be tested exactly as it will be deployed.

## Deploying

nginx:

    location /             { root  /srv/wireview/web; }
    location /sv_projects  { alias /srv/SchaltplanViewer/data/sv_projects; }
    location /style_sheets { alias /srv/SchaltplanViewer/style_sheets; }

Apache:

    DocumentRoot /srv/wireview/web
    Alias /sv_projects  /srv/SchaltplanViewer/data/sv_projects
    Alias /style_sheets /srv/SchaltplanViewer/style_sheets

Everything is read-only and cacheable. The sheet tree is several gigabytes, so
serve it from disk rather than through any application layer.

**This is licensed Porsche data.** It is fine to hold locally; put
authentication in front of it before exposing it anywhere, and do not commit
the sheet tree itself to a repository.

## Features

- Navigation follows WireView's own cascade — model line, model, year,
  variant, then named sheets like `(20) PCM`. Includes the FUNCTION FLOW
  branch, which has no folder of its own and is invisible to a filesystem walk.
- Pinout table beside each drawing, so the machine reading can be checked
  against the diagram rather than trusting either alone.
- Search over sheet names.
- Zoom, fit-width, and 100%. Sheets are wide and short — 2112×435 units is
  typical — so they open at natural size with scrolling; scaling to the
  container squashes them into an unreadable strip.
- **Print** — drawing only, landscape, navigation chrome suppressed.
- **Save SVG** — standalone file with the stylesheet inlined, so it renders
  correctly outside this app.
- **Save PNG** — rasterised up to 4× because line art at 1:1 is unreadable,
  capped at 8000px since browsers refuse to draw much beyond that.

## Language

Sheets carry ten language variants inside SVG `<switch>` elements. Browsers
pick by their own locale, which for these files usually means German, so the
branch is chosen explicitly. Change `CONFIG.lang` for another; `build.py
--lang` does the same for sheet names in the navigation.
