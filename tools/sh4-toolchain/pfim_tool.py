#!/usr/bin/env python3
"""
PCM-Forge PFIM Tool  --  view / create the raw .bin image blobs that showimg
blits onto the Porsche PCM 3.1 screen.

A PFIM blob = 24-byte little-endian header + raw pixels:
    u32 magic('PFIM'=0x4d494650) | u32 W | u32 H | u32 gf_format | u32 stride | u32 bpp
Byte order is IDENTICAL to make_img.py, so blobs are interchangeable.

  * Create : image (PNG/JPG/...) -> .bin, any format/size, WYSIWYG preview
             (the preview is the bytes decoded back, so it shows exactly what
             you are writing). "Save all 4" writes every 8888 channel order at
             once -- handy for finding the car's real order in one trip.
  * Inspect: open a .bin -> header readout + render. "Interpret as" re-decodes
             the SAME bytes under a different channel order (this is how you
             diagnose a color swap on the car), and Compare shows all four at
             once. Save-as re-bakes to any format with no original PNG needed.

Requires: Python 3 + Pillow (pip install pillow). Tkinter ships with Python.
"""
import struct
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    import tkinter.messagebox as mb
    r = tk.Tk(); r.withdraw()
    mb.showerror("Pillow missing", "This tool needs Pillow.\n\n  pip install pillow")
    raise SystemExit(1)

MAGIC = 0x4d494650  # 'PFIM'

# name -> (gf_format code [tune on car], bytes/pixel, channel order | None=rgb565)
# The order tuple is, for each OUTPUT byte, which source RGBA channel it holds
# (R=0 G=1 B=2 A=3). Matches make_img.py's packers exactly.
FORMATS = {
    "bgra8888": (0x1420, 4, (2, 1, 0, 3)),   # B,G,R,A  -- make_img default
    "argb8888": (0x1520, 4, (3, 0, 1, 2)),   # A,R,G,B
    "rgba8888": (0x1620, 4, (0, 1, 2, 3)),   # R,G,B,A
    "abgr8888": (0x1720, 4, (3, 2, 1, 0)),   # A,B,G,R
    "rgb565":   (0x0565, 2, None),
}
CODE2NAME = {c: n for n, (c, _, _) in FORMATS.items()}
NAMES = list(FORMATS.keys())

# ---- PCM-Forge palette (the app dresses itself in the same colors) ----
BG, PANEL, LINE, GOLD, GREEN, INK, DIM = "#0a0a0c", "#141310", "#2a281f", "#c8a44e", "#4eca7a", "#f0efe9", "#8f8b7f"


# ------------------------------------------------------------------ codec
def encode(img_rgba, fmt):
    """PIL RGBA image -> packed pixel bytes for `fmt`."""
    _, bpp, order = FORMATS[fmt]
    if bpp == 4:
        rgba = img_rgba.convert("RGBA").tobytes()       # interleaved R,G,B,A
        out = bytearray(len(rgba))
        for k, src in enumerate(order):                 # out byte k = source channel `src`
            out[k::4] = rgba[src::4]
        return bytes(out)
    out = bytearray()
    px = img_rgba.load()
    w, h = img_rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            out += struct.pack("<H", ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
    return bytes(out)


def decode(data, w, h, fmt):
    """packed pixel bytes -> PIL RGBA image, interpreted as `fmt`."""
    _, bpp, order = FORMATS[fmt]
    need = w * h * bpp
    if len(data) < need:
        data = data + b"\x00" * (need - len(data))
    data = data[:need]
    if bpp == 4:
        rgba = bytearray(need)                          # target R,G,B,A interleaved
        for k, src in enumerate(order):                 # data byte k holds source channel `src`
            rgba[src::4] = data[k::4]
        return Image.frombytes("RGBA", (w, h), bytes(rgba))
    img = Image.new("RGB", (w, h))
    px = img.load()
    i = 0
    for y in range(h):
        for x in range(w):
            v = struct.unpack_from("<H", data, i)[0]; i += 2
            px[x, y] = (((v >> 11) & 0x1f) << 3, ((v >> 5) & 0x3f) << 2, (v & 0x1f) << 3)
    return img.convert("RGBA")


def fit_image(img, size, mode):
    """Resize to `size`. mode='stretch' fills exactly; 'contain' letterboxes on black."""
    img = img.convert("RGBA")
    if mode == "stretch":
        return img.resize(size, Image.LANCZOS)
    w, h = size
    src = img.copy()
    src.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    canvas.paste(src, ((w - src.width) // 2, (h - src.height) // 2), src)
    return canvas


def write_bin(path, img_rgba, fmt):
    w, h = img_rgba.size
    code, bpp, _ = FORMATS[fmt]
    body = encode(img_rgba, fmt)
    hdr = struct.pack("<6I", MAGIC, w, h, code, w * bpp, bpp)
    with open(path, "wb") as f:
        f.write(hdr); f.write(body)
    return len(hdr) + len(body)


def read_bin(path):
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) < 24:
        raise ValueError("file smaller than a 24-byte PFIM header")
    magic, w, h, code, stride, bpp = struct.unpack_from("<6I", raw, 0)
    return raw[24:], magic, w, h, code, stride, bpp


# ------------------------------------------------------------------ GUI
class PfimTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCM-Forge PFIM Tool  --  showimg .bin viewer / baker")
        self.configure(bg=BG)
        self.geometry("980x620")
        self.minsize(820, 540)

        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=INK, fieldbackground=PANEL, bordercolor=LINE)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=INK)
        st.configure("Dim.TLabel", foreground=DIM)
        st.configure("Gold.TLabel", foreground=GOLD, font=("Consolas", 11, "bold"))
        st.configure("TButton", background=PANEL, foreground=INK, bordercolor=LINE, focuscolor=GOLD)
        st.map("TButton", background=[("active", LINE)])
        st.configure("TNotebook", background=BG, bordercolor=LINE)
        st.configure("TNotebook.Tab", background=PANEL, foreground=DIM, padding=(16, 7))
        st.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", GOLD)])
        st.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=INK, arrowcolor=GOLD)
        st.configure("TCheckbutton", background=BG, foreground=INK)
        st.map("TCheckbutton", background=[("active", BG)])

        self._tkimg = None  # keep a ref so the preview isn't garbage-collected

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        self.create_tab = CreateTab(nb, self)
        self.inspect_tab = InspectTab(nb, self)
        nb.add(self.create_tab, text="  Create .bin  ")
        nb.add(self.inspect_tab, text="  Inspect .bin  ")

        self.status = tk.StringVar(value="Ready.  PFIM = 24-byte header + raw pixels; byte-compatible with make_img.py.")
        bar = tk.Label(self, textvariable=self.status, bg=PANEL, fg=DIM, anchor="w",
                       font=("Consolas", 9), padx=10, pady=4)
        bar.pack(fill="x", side="bottom")

    def say(self, msg):
        self.status.set(msg)


class PreviewPane(ttk.Frame):
    """A black canvas that renders a PIL image at a chosen integer zoom."""
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg="#000000", highlightthickness=1, highlightbackground=LINE)
        self.canvas.pack(fill="both", expand=True)
        self._ref = None

    def show(self, pil_img, zoom=1):
        self.canvas.delete("all")
        if pil_img is None:
            self._ref = None
            return
        disp = pil_img
        if zoom != 1:
            disp = pil_img.resize((pil_img.width * zoom, pil_img.height * zoom), Image.NEAREST)
        self._ref = ImageTk.PhotoImage(disp.convert("RGB"))
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), disp.width)
        ch = max(self.canvas.winfo_height(), disp.height)
        self.canvas.create_image(cw // 2, ch // 2, image=self._ref, anchor="center")


class CreateTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.src = None          # loaded PIL image (original)
        self.src_path = None

        ctl = ttk.Frame(self); ctl.pack(fill="x", padx=8, pady=8)
        ttk.Button(ctl, text="Open image...", command=self.open_img).grid(row=0, column=0, padx=(0, 10))
        self.name = ttk.Label(ctl, text="(no image loaded)", style="Dim.TLabel")
        self.name.grid(row=0, column=1, columnspan=6, sticky="w")

        ttk.Label(ctl, text="W").grid(row=1, column=0, sticky="e", pady=(10, 0))
        self.w = tk.StringVar(value="480")
        ttk.Entry(ctl, textvariable=self.w, width=6).grid(row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Label(ctl, text="H").grid(row=1, column=2, sticky="e", pady=(10, 0))
        self.h = tk.StringVar(value="240")
        ttk.Entry(ctl, textvariable=self.h, width=6).grid(row=1, column=3, sticky="w", pady=(10, 0))

        ttk.Label(ctl, text="Format").grid(row=1, column=4, sticky="e", padx=(14, 4), pady=(10, 0))
        self.fmt = tk.StringVar(value="bgra8888")
        cb = ttk.Combobox(ctl, textvariable=self.fmt, values=NAMES, width=10, state="readonly")
        cb.grid(row=1, column=5, sticky="w", pady=(10, 0)); cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        ttk.Label(ctl, text="Fit").grid(row=1, column=6, sticky="e", padx=(14, 4), pady=(10, 0))
        self.fit = tk.StringVar(value="stretch")
        cb2 = ttk.Combobox(ctl, textvariable=self.fit, values=["stretch", "contain"], width=8, state="readonly")
        cb2.grid(row=1, column=7, sticky="w", pady=(10, 0)); cb2.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        ttk.Label(ctl, text="Zoom").grid(row=1, column=8, sticky="e", padx=(14, 4), pady=(10, 0))
        self.zoom = tk.IntVar(value=1)
        cb3 = ttk.Combobox(ctl, textvariable=self.zoom, values=[1, 2, 3], width=4, state="readonly")
        cb3.grid(row=1, column=9, sticky="w", pady=(10, 0)); cb3.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        cb3.current(0)

        for v in (self.w, self.h):
            v.trace_add("write", lambda *a: self.refresh())

        self.preview = PreviewPane(self); self.preview.pack(fill="both", expand=True, padx=8, pady=4)

        act = ttk.Frame(self); act.pack(fill="x", padx=8, pady=8)
        ttk.Button(act, text="Save .bin...", command=self.save_one).pack(side="left")
        ttk.Button(act, text="Save all 4 channel orders...", command=self.save_all).pack(side="left", padx=8)
        self.info = ttk.Label(act, text="", style="Dim.TLabel"); self.info.pack(side="right")

    def open_img(self):
        p = filedialog.askopenfilename(title="Open image",
                                       filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All", "*.*")])
        if not p:
            return
        try:
            self.src = Image.open(p).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Open failed", str(e)); return
        self.src_path = p
        self.name.config(text="%s  (%dx%d)" % (os.path.basename(p), self.src.width, self.src.height))
        if self.w.get() in ("", "0"):
            self.w.set(str(self.src.width)); self.h.set(str(self.src.height))
        self.refresh()

    def _size(self):
        try:
            return (max(1, int(self.w.get())), max(1, int(self.h.get())))
        except ValueError:
            return None

    def _baked(self):
        sz = self._size()
        if not self.src or not sz:
            return None
        fitted = fit_image(self.src, sz, self.fit.get())
        # WYSIWYG: round-trip through the chosen format so the preview == the bytes
        return decode(encode(fitted, self.fmt.get()), sz[0], sz[1], self.fmt.get()), sz

    def refresh(self):
        b = self._baked()
        if not b:
            self.preview.show(None); self.info.config(text=""); return
        img, sz = b
        self.preview.show(img, self.zoom.get())
        code, bpp, _ = FORMATS[self.fmt.get()]
        self.info.config(text="%dx%d  %s  gffmt=%s  %d bytes" %
                         (sz[0], sz[1], self.fmt.get(), hex(code), 24 + sz[0] * sz[1] * bpp))

    def save_one(self):
        sz = self._size()
        if not self.src or not sz:
            self.app.say("Load an image and set a size first."); return
        p = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("PFIM blob", "*.bin")],
                                         initialfile="image.bin")
        if not p:
            return
        img = fit_image(self.src, sz, self.fit.get())
        n = write_bin(p, img, self.fmt.get())
        self.app.say("Wrote %s  (%dx%d %s, %d bytes)" % (os.path.basename(p), sz[0], sz[1], self.fmt.get(), n))

    def save_all(self):
        sz = self._size()
        if not self.src or not sz:
            self.app.say("Load an image and set a size first."); return
        d = filedialog.askdirectory(title="Folder for the 4 variants")
        if not d:
            return
        stem = os.path.splitext(os.path.basename(self.src_path or "image"))[0]
        img = fit_image(self.src, sz, self.fit.get())
        made = []
        for fmt in ("bgra8888", "argb8888", "rgba8888", "abgr8888"):
            p = os.path.join(d, "%s_%s.bin" % (stem, fmt))
            write_bin(p, img, fmt); made.append(os.path.basename(p))
        self.app.say("Wrote 4 variants: " + ", ".join(made))


class InspectTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.body = None
        self.dim = (0, 0)
        self.hdr_fmt = "bgra8888"

        ctl = ttk.Frame(self); ctl.pack(fill="x", padx=8, pady=8)
        ttk.Button(ctl, text="Open .bin...", command=self.open_bin).grid(row=0, column=0, padx=(0, 10))
        self.hdr = ttk.Label(ctl, text="(no blob loaded)", style="Gold.TLabel")
        self.hdr.grid(row=0, column=1, columnspan=8, sticky="w")

        ttk.Label(ctl, text="Interpret as").grid(row=1, column=0, sticky="e", pady=(10, 0))
        self.fmt = tk.StringVar(value="bgra8888")
        cb = ttk.Combobox(ctl, textvariable=self.fmt, values=NAMES, width=10, state="readonly")
        cb.grid(row=1, column=1, sticky="w", pady=(10, 0)); cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        ttk.Label(ctl, text="Zoom").grid(row=1, column=2, sticky="e", padx=(14, 4), pady=(10, 0))
        self.zoom = tk.IntVar(value=1)
        cb2 = ttk.Combobox(ctl, textvariable=self.zoom, values=[1, 2, 3], width=4, state="readonly")
        cb2.grid(row=1, column=3, sticky="w", pady=(10, 0)); cb2.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        cb2.current(0)

        ttk.Button(ctl, text="Compare all formats", command=self.compare).grid(row=1, column=4, padx=(14, 0), pady=(10, 0))

        self.preview = PreviewPane(self); self.preview.pack(fill="both", expand=True, padx=8, pady=4)

        act = ttk.Frame(self); act.pack(fill="x", padx=8, pady=8)
        ttk.Button(act, text="Save as .bin (re-bake to 'Interpret as')...", command=self.save_as).pack(side="left")
        self.note = ttk.Label(act, text="", style="Dim.TLabel"); self.note.pack(side="right")

    def open_bin(self):
        p = filedialog.askopenfilename(title="Open .bin", filetypes=[("PFIM blob", "*.bin"), ("All", "*.*")])
        if not p:
            return
        try:
            body, magic, w, h, code, stride, bpp = read_bin(p)
        except Exception as e:
            messagebox.showerror("Read failed", str(e)); return
        self.body, self.dim = body, (w, h)
        name = CODE2NAME.get(code)
        self.hdr_fmt = name or "bgra8888"
        self.fmt.set(self.hdr_fmt)
        magic_ok = "OK" if magic == MAGIC else "BAD(0x%08x)" % magic
        exp = 24 + w * h * bpp
        sz_ok = "OK" if len(body) + 24 == exp else "have %d exp %d" % (len(body) + 24, exp)
        self.hdr.config(text="%s   magic=%s   %dx%d   fmt=%s (%s)   stride=%d bpp=%d   size=%s"
                        % (os.path.basename(p), magic_ok, w, h,
                           name or "unknown", hex(code), stride, bpp, sz_ok))
        self.refresh()

    def _img(self, fmt):
        w, h = self.dim
        return decode(self.body, w, h, fmt)

    def refresh(self):
        if not self.body:
            self.preview.show(None); return
        self.preview.show(self._img(self.fmt.get()), self.zoom.get())
        tag = "  <- header format" if self.fmt.get() == self.hdr_fmt else "  (re-interpreted; differs from header)"
        self.note.config(text=self.fmt.get() + tag)

    def compare(self):
        if not self.body:
            self.app.say("Open a .bin first."); return
        w, h = self.dim
        pad, cols = 8, 2
        cellw, cellh = w + pad, h + 20 + pad
        grid = Image.new("RGB", (cellw * cols + pad, cellh * 2 + pad), (10, 10, 12))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(grid)
        for i, fmt in enumerate(("bgra8888", "argb8888", "rgba8888", "abgr8888")):
            cx = pad + (i % cols) * cellw
            cy = pad + (i // cols) * cellh
            grid.paste(self._img(fmt).convert("RGB"), (cx, cy + 16))
            mark = "  <- header" if fmt == self.hdr_fmt else ""
            dr.text((cx + 2, cy + 2), fmt + mark, fill=(200, 164, 78))
        self.preview.show(grid, 1)
        self.app.say("Comparing 4 channel orders -- pick the one where colors look right, that's your --format.")

    def save_as(self):
        if not self.body:
            self.app.say("Open a .bin first."); return
        fmt = self.fmt.get()
        img = self._img(fmt)  # decode under current interpretation = true RGB for that reading
        p = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("PFIM blob", "*.bin")],
                                         initialfile="rebaked_%s.bin" % fmt)
        if not p:
            return
        n = write_bin(p, img, fmt)
        self.app.say("Re-baked %s as %s (%d bytes)" % (os.path.basename(p), fmt, n))


if __name__ == "__main__":
    PfimTool().mainloop()
