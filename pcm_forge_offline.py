#!/usr/bin/env python3
"""PCM-Forge Offline -- activation codes and USB sticks for the Porsche PCM 3.1,
with no internet.

A small desktop window over generate_codes.py, the same code the web app's
USB Stick tab mirrors (tests/ check the two byte for byte):

  * enter the VIN, pick the model, tick features -> every code, live
  * Build activation stick...   copie_scr.sh + run.sh + PagSWAct.002 + splash
  * Build diagnostic stick...   read-only; brings back the PCM's VIN and backup
  * Open returned stick...      what the PCM has activated, and the VIN it stores

Nothing is sent anywhere. Packaged as PCM-Forge-Offline.exe by
.github/workflows/build-offline.yml.

    python pcm_forge_offline.py                 the window
    python pcm_forge_offline.py --selftest DIR  build both stick kinds into DIR
                                                (no window; for CI and checks)
"""
import contextlib
import io
import os
import sys

import generate_codes as gc

try:
    from _build import COMMIT          # stamped by the build workflow
except ImportError:
    COMMIT = "dev"

TITLE = "PCM-Forge Offline"
DEFAULT_MODEL = "cayenne-se"           # the web app's default too

# Palette shared with the web app (docs/index.html :root) and PCM-Explorer
BG, PANEL, PANEL2, LINE = "#0a0a0c", "#131318", "#1a1a22", "#2a2a35"
TEXT, DIM, ACCENT, GREEN, RED = "#e8e8ed", "#8888a0", "#c8a44e", "#4eca7a", "#e85454"


def model_choices():
    """[(label, key)] sorted by label, as the dropdown shows them."""
    return sorted(((f"{desc}  (0x{subid:04x})", key) for key, (subid, desc) in gc.MODELS.items()),
                  key=lambda t: t[0].lower())


def capture(fn, *a, **kw):
    """Run a CLI helper that prints, and return (exit code, text)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


def build_activation(vin, model_key, names, out):
    """Write an activation stick for `names` (feature names) to `out`."""
    subid = gc.MODELS[model_key][0]
    feats = [f for f in gc.features_for(subid) if f[0] in names]
    if not feats:
        raise ValueError("no features selected")
    gc.write_usb(out, gc.RUN_ACTIVATE, pagswact=gc.build_pagswact(vin, feats))
    return feats


def car_features(path):
    """What a returned stick (or a folder with PagSWAct.002) says the car has:
    (feature names, model key or None, [records not carried over as-is],
    [map databases at a single level]) or None.

    A stick built here signs each feature with its standard SubID, so a record
    with another variant, or a SWID this tool doesn't know, is listed rather
    than silently changed. A map database at one level (a dealer map update)
    is listed apart: the stick's code unlocks every level, which also works."""
    try:
        recs = gc.load_records(gc.resolve_pagswact(path))
    except (OSError, ValueError):
        return None
    known = {f[2]: f for f in gc.features_for(0x0003)}
    names, model_key, kept, levels = set(), None, [], []
    for swid, rec in recs:
        subid = int.from_bytes(rec[0x14:0x16], "little")
        code = rec[:16].decode("ascii", "replace")
        entry = known.get(swid)
        if not entry:
            kept.append("unknown 0x%04x" % swid)
            continue
        names.add(entry[0])
        if swid == gc.FEATURELEVEL_SWID:
            model_key = next((k for k, (s, _d) in gc.MODELS.items() if s == subid), None)
            if not model_key:
                kept.append("FeatureLevel 0x%04x (unknown model)" % subid)
        elif swid in gc.NAVDB_SWIDS and gc.map_level(code) is not None:
            levels.append("%s level %d" % (entry[0], gc.map_level(code)))
        elif subid not in (entry[3], gc.SUBID_WILDCARD):
            kept.append("%s variant 0x%04x" % (entry[0], subid))
    return names, model_key, kept, levels


def build_diagnostic(out):
    gc.write_usb(out, gc.RUN_DIAG)


def selftest(out):
    """Build both stick kinds into `out` and check every file landed: proves a
    packaged build found its payloads and splash assets. Exit code 0/1."""
    vin = "WP1AA2A29ELA00000"
    act, diag = os.path.join(out, "activation"), os.path.join(out, "diagnostic")
    feats = build_activation(vin, DEFAULT_MODEL, {"ENGINEERING", "UMS", "FeatureLevel"}, act)
    build_diagnostic(diag)
    need = [os.path.join(act, p) for p in ("copie_scr.sh", "run.sh", "PagSWAct.002")]
    need += [os.path.join(diag, p) for p in ("copie_scr.sh", "run.sh")]
    for d in (act, diag):
        need += [os.path.join(d, sub, name) for sub, name in gc.SPLASH_ASSETS]
    missing = [p for p in need if not os.path.isfile(p)]
    ok = not missing and os.path.getsize(os.path.join(act, "PagSWAct.002")) == 28 * len(feats)
    with open(os.path.join(out, "selftest.txt"), "w") as f:
        f.write("OK\n" if ok else "FAIL\nmissing: %s\n" % missing)
    return 0 if ok else 1


def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("%s  (%s)" % (TITLE, COMMIT))
    root.geometry("1280x800")
    root.minsize(1100, 700)
    root.configure(bg=BG)

    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Dim.TLabel", foreground=DIM)
    st.configure("Title.TLabel", foreground=ACCENT, font=("Consolas", 9, "bold"))
    st.configure("Big.TLabel", foreground=TEXT, font=("Segoe UI", 15, "bold"))
    st.configure("TCheckbutton", background=BG, foreground=TEXT)
    st.map("TCheckbutton", background=[("active", PANEL2)])
    st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                 rowheight=22, borderwidth=0)
    st.configure("Treeview.Heading", background=PANEL2, foreground=DIM, font=("Consolas", 9))
    st.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG)])
    st.configure("TButton", background=PANEL2, foreground=TEXT, padding=(10, 6))
    st.map("TButton", background=[("active", LINE), ("pressed", ACCENT)])
    st.configure("Accent.TButton", background=ACCENT, foreground=BG)
    st.configure("TCombobox", fieldbackground=PANEL, background=PANEL2, foreground=TEXT,
                 arrowcolor=TEXT)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", BG)

    # ---- header ----
    top = ttk.Frame(root); top.pack(fill="x", padx=14, pady=(12, 4))
    ttk.Label(top, text="PCM-FORGE", style="Title.TLabel").pack(anchor="w")
    ttk.Label(top, text="Porsche PCM 3.1 activation — offline", style="Big.TLabel").pack(anchor="w")
    ttk.Label(top, text="Codes and USB sticks are made on this PC. Nothing is sent anywhere.",
              style="Dim.TLabel").pack(anchor="w")

    # ---- VIN + model ----
    row = ttk.Frame(root); row.pack(fill="x", padx=14, pady=8)
    ttk.Label(row, text="VIN").grid(row=0, column=0, sticky="w")
    vin_var = tk.StringVar()
    vin_entry = tk.Entry(row, textvariable=vin_var, width=24, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=("Consolas", 13))
    vin_entry.grid(row=1, column=0, sticky="w", padx=(0, 18), ipady=4)
    ttk.Label(row, text="Model (FeatureLevel / boot logo)").grid(row=0, column=1, sticky="w")
    choices = model_choices()
    labels = [c[0] for c in choices]
    model_var = tk.StringVar(value=next(l for l, k in choices if k == DEFAULT_MODEL))
    model_box = ttk.Combobox(row, textvariable=model_var, values=labels, width=42, state="readonly")
    model_box.grid(row=1, column=1, sticky="w")
    vin_msg = ttk.Label(row, text="Enter the 17-character VIN.", style="Dim.TLabel")
    vin_msg.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # status line + action buttons are packed BEFORE the expanding body, so a
    # small window squeezes the lists, never the buttons
    status = tk.StringVar(value="Offline. Activation codes are made for the VIN the PCM stores "
                                "(a used PCM still holds its donor car's VIN).")
    tk.Label(root, textvariable=status, bg=PANEL2, fg=DIM, anchor="w", padx=8, pady=5,
             wraplength=1200, justify="left").pack(fill="x", side="bottom")
    actions = ttk.Frame(root); actions.pack(fill="x", side="bottom", padx=14, pady=10)

    body = ttk.Frame(root); body.pack(fill="both", expand=True, padx=14)
    body.columnconfigure(1, weight=1); body.rowconfigure(1, weight=1)

    # ---- features ----
    ttk.Label(body, text="FEATURES FOR THE STICK", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    fbox = ttk.Frame(body); fbox.grid(row=1, column=0, sticky="nsw", padx=(0, 14))
    feat_vars = {}
    feats0 = gc.features_for(gc.MODELS[DEFAULT_MODEL][0])
    per_col = (len(feats0) + 1) // 2                  # two columns: all 27 fit on screen
    for i, (name, _hex, _sw, _su, desc) in enumerate(feats0):
        v = tk.BooleanVar(value=False)
        feat_vars[name] = v
        ttk.Checkbutton(fbox, text="%s — %s" % (name, desc), variable=v).grid(
            row=i % per_col, column=i // per_col, sticky="w", padx=(0, 10))
    fbtn = ttk.Frame(body); fbtn.grid(row=2, column=0, sticky="w", pady=6)
    ttk.Button(fbtn, text="Select all", command=lambda: [v.set(True) for v in feat_vars.values()]).pack(side="left")
    ttk.Button(fbtn, text="Clear", command=lambda: [v.set(False) for v in feat_vars.values()]).pack(side="left", padx=6)

    # ---- codes ----
    ttk.Label(body, text="ACTIVATION CODES (double-click to copy)", style="Title.TLabel").grid(row=0, column=1, sticky="w")
    codes = ttk.Treeview(body, columns=("code", "desc"), show="tree headings")
    codes.heading("#0", text="feature"); codes.column("#0", width=150)
    codes.heading("code", text="code"); codes.column("code", width=170)
    codes.heading("desc", text="description"); codes.column("desc", width=260)
    codes.grid(row=1, column=1, rowspan=2, sticky="nsew")
    sb = ttk.Scrollbar(body, orient="vertical", command=codes.yview)
    sb.grid(row=1, column=2, rowspan=2, sticky="ns")
    codes.configure(yscrollcommand=sb.set)
    ttk.Label(body, style="Dim.TLabel", wraplength=620, justify="left",
              text="NavDB codes here unlock every map level (255), like most factory codes. If the "
                   "car's own NavDB code differs, it is probably a one-level code from a dealer map "
                   "update: both work. 'Open returned stick...' shows the level.").grid(
        row=3, column=1, sticky="w", pady=(4, 0))

    def current():
        """(vin or None, model key)."""
        key = dict(choices)[model_var.get()]
        try:
            vin = gc.validate_vin(vin_var.get().strip())
        except ValueError as e:
            return None, key, str(e)
        return vin, key, None

    def refresh(*_):
        vin, key, err = current()
        codes.delete(*codes.get_children())
        if not vin_var.get().strip():
            vin_msg.config(text="Enter the 17-character VIN.", foreground=DIM); return
        if err:
            vin_msg.config(text=err, foreground=RED); return
        notes = gc.vin_advisories(vin)
        vin_msg.config(text=("Note: " + " ".join(notes)) if notes else "VIN OK.",
                       foreground=ACCENT if notes else GREEN)
        for name, feat_hex, _sw, _su, desc in gc.features_for(gc.MODELS[key][0]):
            codes.insert("", "end", text=name, values=(gc.generate_code(vin, feat_hex), desc))

    def copy_code(_evt=None):
        sel = codes.selection()
        if sel:
            c = codes.item(sel[0], "values")[0]
            root.clipboard_clear(); root.clipboard_append(c)
            status.set("Copied %s: %s" % (codes.item(sel[0], "text"), c))

    def copy_all():
        lines = ["%s: %s" % (codes.item(i, "text"), codes.item(i, "values")[0]) for i in codes.get_children()]
        if lines:
            root.clipboard_clear(); root.clipboard_append("\n".join(lines))
            status.set("Copied all %d codes." % len(lines))

    def ask_folder(title):
        return filedialog.askdirectory(title=title)

    def make_activation():
        vin, key, err = current()
        if not vin:
            messagebox.showerror(TITLE, err or "Enter the VIN first."); return
        names = {n for n, v in feat_vars.items() if v.get()}
        if not names:
            messagebox.showerror(TITLE, "Tick the features the stick should activate."); return
        if not messagebox.askokcancel(
                TITLE, "This stick REPLACES every activation on the PCM: only the %d ticked "
                       "feature(s) will be active afterwards.\n\nTo keep what the car already has, run "
                       "a diagnostic stick first and tick everything it shows (or use Select all).\n\n"
                       "Continue?" % len(names)):
            return
        out = ask_folder("USB stick (FAT32) for the activation stick")
        if not out:
            return
        try:
            feats = build_activation(vin, key, names, out)
        except Exception as e:
            messagebox.showerror(TITLE, "Could not write the stick:\n%s" % e); return
        status.set("Activation stick written to %s: %d features for %s. Insert it after the PCM "
                   "has fully booted; wait for DONE." % (out, len(feats), vin))
        messagebox.showinfo(TITLE, "Activation stick ready (%d features).\n\nInsert it after the PCM "
                                   "has fully booted and leave it in until the screen says DONE."
                            % len(feats))

    def make_diag():
        out = ask_folder("USB stick (FAT32) for the diagnostic stick")
        if not out:
            return
        try:
            build_diagnostic(out)
        except Exception as e:
            messagebox.showerror(TITLE, "Could not write the stick:\n%s" % e); return
        status.set("Diagnostic stick written to %s. It is read-only: it brings back the VIN the "
                   "PCM stores and a backup of its activations." % out)
        messagebox.showinfo(TITLE, "Diagnostic stick ready. It changes nothing on the car.\n\n"
                                   "Insert it after the PCM has booted, wait for DONE, then use "
                                   "'Open returned stick...' here.")

    def open_returned():
        path = ask_folder("The returned diagnostic stick (or a folder with PagSWAct.002)")
        if not path:
            return
        win = tk.Toplevel(root); win.title("Returned stick — " + path); win.configure(bg=BG)
        win.geometry("880x560")
        txt = tk.Text(win, bg=PANEL, fg=TEXT, font=("Consolas", 10), relief="flat", wrap="none")
        found_vin, src = gc.vin_from_diagnostics(path)
        head = ("VIN stored in the PCM: %s   (from %s)\n\n" % (found_vin, src)) if found_vin else \
               "No VIN found on this stick (it is in pcm_dump_<date>/vin after a diagnostic run).\n\n"
        try:
            rc, out = capture(gc.show_pagswact, path, found_vin)
        except Exception as e:
            out = "Could not read an activation file here: %s\n" % e
        txt.insert("end", head + out)
        txt.config(state="disabled")
        bar = ttk.Frame(win); bar.pack(fill="x", padx=8, pady=6)
        have = car_features(path)
        if found_vin or have:
            def use():
                if found_vin:
                    vin_var.set(found_vin)
                names, model_key, kept, levels = have or (set(), None, [], [])
                if model_key:
                    model_var.set(next(l for l, k in choices if k == model_key))
                if names:
                    for n, v in feat_vars.items():
                        v.set(n in names)
                refresh(); win.destroy()
                msg = []
                if found_vin:
                    msg.append("Using the PCM's own VIN %s." % found_vin)
                if names:
                    msg.append("Ticked the %d features it has, so a new stick keeps them." % len(names))
                if kept:
                    msg.append("Not carried over (a stick here uses the standard variant): %s -- "
                               "use generate_codes.py --from-backup to keep them exactly."
                               % ", ".join(kept))
                if levels:
                    msg.append("Map databases at one level (likely a dealer map update): %s. "
                               "A stick from here unlocks every level instead, which also works."
                               % ", ".join(levels))
                status.set(" ".join(msg))
            label = "Use this PCM's VIN + features" if found_vin and have else \
                    "Use this PCM's VIN" if found_vin else "Tick these features"
            ttk.Button(bar, text=label, style="Accent.TButton", command=use).pack(side="left")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="left", padx=6)
        txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    ttk.Button(actions, text="Build activation stick...", style="Accent.TButton",
               command=make_activation).pack(side="left")
    ttk.Button(actions, text="Build diagnostic stick...", command=make_diag).pack(side="left", padx=8)
    ttk.Button(actions, text="Open returned stick...", command=open_returned).pack(side="left")
    ttk.Button(actions, text="Copy all codes", command=copy_all).pack(side="right")

    vin_var.trace_add("write", refresh)
    model_box.bind("<<ComboboxSelected>>", refresh)
    codes.bind("<Double-1>", copy_code)
    vin_entry.focus_set()
    root.mainloop()


def main(argv):
    if len(argv) >= 2 and argv[0] == "--selftest":
        return selftest(argv[1])
    run_gui()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
