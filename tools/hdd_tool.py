#!/usr/bin/env python3
"""
PCM-Forge HDD Tool  --  open and browse a Porsche PCM / Audi MMI hard-drive image.

Point it at a raw disk image (a `dd` clone of a PCM 3.1 / MMI HDD) and it maps the
partition table, identifies each filesystem, and reconstructs the full directory
tree so you can see what is on a drive you cannot otherwise mount. Nothing on the
image is ever written -- the file is opened read-only, always.

Why this exists: QNX6 ("power-safe") filesystems are effectively unreadable off a
QNX box. Linux has a read-only qnx6 driver aimed at QNX 6.4+, Windows has nothing,
and the Harman 6.3.2 variant in these head units diverges from the public layout
anyway. So a dead PCM's drive is normally a black box.

  * Partitions : MBR parse + per-partition filesystem detection.
  * Browse     : full directory tree. This does NOT rely on the superblock -- QNX6
                 directory blocks self-identify ('.' holds their own inode number,
                 '..' their parent), so the tree is rebuilt from those fragments.
                 That makes it robust on damaged or partially-zeroed drives.
  * Inspect    : per-file details, plus a hex/text view of any offset on the disk.
  * Extract    : best-effort. Resolving an inode number to its data blocks is
                 solved for part of the disk (see resolve_inode); where that fails
                 the tool says so rather than writing a wrong file.

Read-only by construction: the image is opened 'rb' and no code path writes to it.

CLI (no GUI needed):
    python hdd_tool.py <image>                 partition table + fs detection
    python hdd_tool.py <image> tree P2 [depth] print the directory tree
    python hdd_tool.py <image> hex <offset>    hex dump at a byte offset

GUI:
    python hdd_tool.py                         (or: python hdd_tool.py <image> gui)

Tkinter ships with Python; nothing else is required.
"""
import os
import struct
import sys
import threading

# ---------------------------------------------------------------- constants --
SECTOR = 512
QNX6_MAGIC = 0x68191122          # QNX6 superblock magic
QNX4_MAGIC = b"QNX4FS"
INODE_SZ = 128                   # QNX6 inode struct size
NIL = 0xFFFFFFFF

# MBR partition type -> label. 0x4d/0x4e/0x4f are the QNX ones used by these units.
PART_TYPES = {
    0x4d: "QNX", 0x4e: "QNX", 0x4f: "QNX",
    0x07: "NTFS/exFAT", 0x0b: "FAT32", 0x0c: "FAT32 (LBA)", 0x83: "Linux",
}


# ------------------------------------------------------------------- reader --
class DiskImage:
    """Read-only view of a raw disk image. Never loads the whole file."""

    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path)
        self.f = open(path, "rb")          # read-only, always
        self.parts = self._read_mbr()

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass

    def read(self, off, n):
        if off < 0 or off >= self.size:
            return b""
        self.f.seek(off)
        return self.f.read(n)

    # -- partition table --
    def _read_mbr(self):
        mbr = self.read(0, 512)
        parts = []
        if len(mbr) < 512 or mbr[510:512] != b"\x55\xaa":
            return parts
        for i in range(4):
            e = mbr[446 + i * 16: 446 + (i + 1) * 16]
            ptype = e[4]
            if ptype == 0:
                continue
            lba = struct.unpack_from("<I", e, 8)[0]
            cnt = struct.unpack_from("<I", e, 12)[0]
            if cnt == 0:
                continue
            parts.append({
                "name": "P%d" % (i + 1),
                "type": ptype,
                "type_name": PART_TYPES.get(ptype, "0x%02x" % ptype),
                "base": lba * SECTOR,
                "length": cnt * SECTOR,
                "bootable": e[0] == 0x80,
            })
        return parts

    def part(self, name):
        for p in self.parts:
            if p["name"] == name:
                return p
        return None

    # -- filesystem detection --
    def detect_fs(self, p):
        """Identify the filesystem in a partition. Returns (label, detail)."""
        sbs = self.superblocks(p)
        if sbs:
            live = sbs[0]
            return "QNX6", ("blocksize=%d inodes=%d/%d blocks=%d free=%d groups=%d"
                            % (live["blocksize"], live["num_inodes"] - live["free_inodes"],
                               live["num_inodes"], live["num_blocks"],
                               live["free_blocks"], live["allocgroup"]))
        head = self.read(p["base"], 4096)
        if QNX4_MAGIC in head:
            return "QNX4", "QNX4 signature found"
        if head[3:11] in (b"NTFS    ",):
            return "NTFS", ""
        if b"FAT32" in head[:100] or b"FAT16" in head[:100]:
            return "FAT", ""
        # Directory blocks may still be recoverable even with no superblock.
        return "unknown", "no superblock found (browse may still work)"

    # -- QNX6 superblocks --
    def superblocks(self, p):
        """Both QNX6 superblocks (power-safe keeps two), newest serial first."""
        base, plen = p["base"], p["length"]
        out = []
        for cand in (base + 0x2000, base + plen - 0x1000):
            d = self.read(cand, 256)
            if len(d) < 256:
                continue
            if struct.unpack_from("<I", d, 0)[0] != QNX6_MAGIC:
                continue
            out.append({
                "off": cand,
                "serial": struct.unpack_from("<Q", d, 8)[0],
                "blocksize": struct.unpack_from("<I", d, 0x30)[0],
                "num_inodes": struct.unpack_from("<I", d, 0x34)[0],
                "free_inodes": struct.unpack_from("<I", d, 0x38)[0],
                "num_blocks": struct.unpack_from("<I", d, 0x3c)[0],
                "free_blocks": struct.unpack_from("<I", d, 0x40)[0],
                "allocgroup": struct.unpack_from("<I", d, 0x44)[0],
                "inode_ptr": struct.unpack_from("<I", d, 0x50)[0],
                "inode_levels": d[0x90],
                "raw": d,
            })
        return sorted(out, key=lambda s: -s["serial"])

    def blocksize(self, p):
        sbs = self.superblocks(p)
        return sbs[0]["blocksize"] if sbs else 1024

    # -- directory-tree reconstruction (superblock-free) --
    def scan_dirs(self, p, cap_mb=1200, progress=None, cancel=None):
        """Rebuild the directory tree by finding self-identifying dir blocks.

        QNX6 dirents are 32 bytes: u32 inode, u8 namelen, name[]. A directory
        block opens with '.' (its own inode) then '..' (its parent), which lets us
        rebuild the hierarchy without trusting any superblock -- and still work on
        a damaged drive.
        """
        base, plen = p["base"], p["length"]
        rem = min(plen, cap_mb * 1024 * 1024)
        total = rem
        self.f.seek(base)
        dirs = {}
        carry = b""
        carry_off = base
        done = 0
        while rem > 0:
            if cancel is not None and cancel():
                break
            chunk = self.f.read(min(8 * 1024 * 1024, rem))
            if not chunk:
                break
            rem -= len(chunk)
            done += len(chunk)
            buf = carry + chunk
            j = 0
            while True:
                k = buf.find(b"\x01.", j)
                if k < 0:
                    break
                e = k - 4
                j = k + 2
                if e < 0 or e + 64 > len(buf):
                    continue
                # second entry must be '..' for this to be a directory block
                if buf[e + 36] == 0x02 and buf[e + 37:e + 39] == b"..":
                    self_ino = struct.unpack_from("<I", buf, e)[0]
                    par_ino = struct.unpack_from("<I", buf, e + 32)[0]
                    kids = _parse_dirents(buf, e + 64)
                    if self_ino and self_ino not in dirs:
                        dirs[self_ino] = {
                            "parent": par_ino,
                            "kids": kids,
                            "offset": carry_off + e,
                        }
            carry = buf[-64:]
            carry_off += len(buf) - 64
            if progress:
                progress(done, total, len(dirs))
        return dirs

    # -- inode resolution (best-effort; see module docstring) --
    def find_inode_regions(self, p, cap_mb=64):
        """Locate regions that look like dense arrays of valid inode structs."""
        base = p["base"]
        bs = self.blocksize(p)
        regions = []
        run_start = None
        off = base
        end = base + min(p["length"], cap_mb * 1024 * 1024)
        while off < end:
            blk = self.read(off, bs)
            if len(blk) < bs:
                break
            good = 0
            for s in range(0, bs - INODE_SZ + 1, INODE_SZ):
                if _looks_like_inode(blk[s:s + INODE_SZ], p["length"]):
                    good += 1
            per_block = bs // INODE_SZ
            if good >= max(2, per_block // 2):
                if run_start is None:
                    run_start = off
            else:
                if run_start is not None:
                    regions.append((run_start, off))
                    run_start = None
            off += bs
        if run_start is not None:
            regions.append((run_start, end))
        return regions

    def resolve_inode(self, p, ino, regions=None):
        """Inode number -> (offset, parsed struct), or None.

        The QNX6 inode file scrambles inode numbers across allocation groups, and
        the Harman 6.3.2 variant's superblock chain does not describe it fully. So
        we try the plausible schemes and accept the first that yields a structurally
        valid inode. Returns None rather than guessing when nothing validates.
        """
        if regions is None:
            regions = self.find_inode_regions(p)
        for rs, re_ in regions:
            for cand in (rs + (ino - 1) * INODE_SZ, rs + ino * INODE_SZ):
                if rs <= cand < re_:
                    raw = self.read(cand, INODE_SZ)
                    if _looks_like_inode(raw, p["length"]):
                        return cand, parse_inode(raw)
        return None

    def read_file(self, p, inode, max_bytes=8 * 1024 * 1024):
        """Read a file's bytes via its inode's direct block pointers.

        Only direct blocks are handled (filelevels==0). Deeper trees return what
        is available and flag truncation rather than emitting wrong bytes.
        """
        bs = self.blocksize(p)
        out = bytearray()
        remaining = min(inode["size"], max_bytes)
        if inode.get("filelevels", 0) != 0:
            return b"", "indirect blocks (filelevels=%d) not supported" % inode["filelevels"]
        for bp in inode["block_ptr"]:
            if remaining <= 0:
                break
            if bp == NIL or bp == 0:
                continue
            data = self.read(p["base"] + bp * bs, min(bs, remaining))
            if not data:
                break
            out += data
            remaining -= len(data)
        if len(out) < inode["size"]:
            return bytes(out), "truncated (%d of %d bytes)" % (len(out), inode["size"])
        return bytes(out), None


def _parse_dirents(buf, i):
    """Parse consecutive 32-byte QNX6 directory entries."""
    out = []
    while i + 32 <= len(buf):
        ino = struct.unpack_from("<I", buf, i)[0]
        nl = buf[i + 4]
        if nl == 0 or nl > 27:
            break
        nm = buf[i + 5:i + 5 + nl]
        if not nm or not all(33 <= c < 127 for c in nm):
            break
        out.append((nm.decode("latin-1"), ino))
        i += 32
    return out


def parse_inode(raw):
    """Parse a 128-byte QNX6 inode struct."""
    return {
        "size": struct.unpack_from("<Q", raw, 0x00)[0],
        "uid": struct.unpack_from("<I", raw, 0x08)[0],
        "gid": struct.unpack_from("<I", raw, 0x0c)[0],
        "mtime": struct.unpack_from("<I", raw, 0x14)[0],
        "mode": struct.unpack_from("<H", raw, 0x20)[0],
        "block_ptr": list(struct.unpack_from("<16I", raw, 0x24)),
        "filelevels": raw[0x64],
        "status": raw[0x65],
    }


def _looks_like_inode(raw, part_len):
    """Heuristic validity test for a 128-byte inode struct."""
    if len(raw) < INODE_SZ or not any(raw):
        return False
    size = struct.unpack_from("<Q", raw, 0x00)[0]
    mode = struct.unpack_from("<H", raw, 0x20)[0]
    if size > part_len:
        return False
    if (mode & 0xF000) not in (0x8000, 0x4000, 0xA000, 0x2000, 0x6000, 0x1000):
        return False
    ptrs = struct.unpack_from("<16I", raw, 0x24)
    max_blk = part_len // 1024
    for bp in ptrs:
        if bp != NIL and bp != 0 and bp > max_blk:
            return False
    return True


def mode_str(mode):
    kind = {0x8000: "-", 0x4000: "d", 0xA000: "l", 0x2000: "c",
            0x6000: "b", 0x1000: "p"}.get(mode & 0xF000, "?")
    bits = ""
    for shift in (6, 3, 0):
        p = (mode >> shift) & 7
        bits += ("r" if p & 4 else "-") + ("w" if p & 2 else "-") + ("x" if p & 1 else "-")
    return kind + bits


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def hexdump(data, base_off=0, width=16):
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hx = " ".join("%02x" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append("%08x  %-*s  %s" % (base_off + i, width * 3 - 1, hx, asc))
    return "\n".join(lines)


def build_paths(dirs):
    """inode -> full path, walking the reconstructed tree from the root."""
    roots = [1] if 1 in dirs else [i for i, d in dirs.items() if d["parent"] not in dirs]
    paths = {}
    for r in roots:
        stack = [(r, "" if len(roots) == 1 else "/(root %d)" % r)]
        seen = set()
        while stack:
            ino, prefix = stack.pop()
            if ino in seen:
                continue
            seen.add(ino)
            paths.setdefault(ino, prefix or "/")
            for nm, cino in dirs.get(ino, {}).get("kids", []):
                if nm in (".", ".."):
                    continue
                child = prefix + "/" + nm
                paths.setdefault(cino, child)
                if cino in dirs:
                    stack.append((cino, child))
    return paths


# ---------------------------------------------------------------------- CLI --
def cli(argv):
    path = argv[0]
    cmd = argv[1] if len(argv) > 1 else "parts"
    img = DiskImage(path)
    print("%s  (%s)" % (os.path.basename(path), human(img.size)))
    if not img.parts:
        print("  no MBR partition table found")
        return 0
    if cmd == "parts":
        print("\n  %-4s %-12s %-14s %-14s %s" % ("part", "type", "start", "size", "filesystem"))
        print("  " + "-" * 74)
        for p in img.parts:
            fs, detail = img.detect_fs(p)
            print("  %-4s %-12s %-14d %-14s %s  %s"
                  % (p["name"], p["type_name"], p["base"], human(p["length"]), fs, detail))
    elif cmd == "tree":
        pname = argv[2] if len(argv) > 2 else "P2"
        maxd = int(argv[3]) if len(argv) > 3 else 3
        p = img.part(pname)
        if not p:
            print("no such partition: %s" % pname)
            return 1
        print("scanning %s ..." % pname)
        dirs = img.scan_dirs(p)
        print("%d directory blocks recovered" % len(dirs))
        paths = build_paths(dirs)
        for ino, pt in sorted(paths.items(), key=lambda kv: kv[1]):
            if pt.count("/") <= maxd:
                print("  %-60s [ino %d]%s" % (pt, ino, "/" if ino in dirs else ""))
    elif cmd == "hex":
        off = int(argv[2], 0)
        n = int(argv[3], 0) if len(argv) > 3 else 512
        print(hexdump(img.read(off, n), off))
    else:
        print(__doc__)
    img.close()
    return 0


# ---------------------------------------------------------------------- GUI --
BG, PANEL, LINE, TEXT, DIM, ACCENT = "#14161a", "#1b1e24", "#2b3038", "#dfe3ea", "#8b93a1", "#d2a24c"


def gui(initial=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class HddTool(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("PCM-Forge HDD Tool")
            self.geometry("1180x740")
            self.configure(bg=BG)
            self.img = None
            self.dirs = {}
            self.paths = {}
            self.cur_part = None
            self._cancel = False

            st = ttk.Style(self)
            try:
                st.theme_use("clam")
            except tk.TclError:
                pass
            st.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL)
            st.configure("TFrame", background=BG)
            st.configure("TLabel", background=BG, foreground=TEXT)
            st.configure("Dim.TLabel", foreground=DIM)
            st.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                         foreground=TEXT, rowheight=20, borderwidth=0)
            st.configure("Treeview.Heading", background=LINE, foreground=TEXT)
            st.map("Treeview", background=[("selected", ACCENT)],
                   foreground=[("selected", "#000000")])

            top = ttk.Frame(self)
            top.pack(fill="x", padx=8, pady=8)
            ttk.Button(top, text="Open image...", command=self.open_image).pack(side="left")
            self.lbl = ttk.Label(top, text="(no image)", style="Dim.TLabel")
            self.lbl.pack(side="left", padx=12)

            pan = ttk.PanedWindow(self, orient="horizontal")
            pan.pack(fill="both", expand=True, padx=8)

            left = ttk.Frame(pan)
            ttk.Label(left, text="Partitions").pack(anchor="w")
            self.plist = ttk.Treeview(left, columns=("type", "size", "fs"),
                                      show="tree headings", height=5)
            self.plist.heading("#0", text="part")
            self.plist.column("#0", width=60)
            for c, w in (("type", 90), ("size", 90), ("fs", 150)):
                self.plist.heading(c, text=c)
                self.plist.column(c, width=w)
            self.plist.pack(fill="x")
            self.plist.bind("<<TreeviewSelect>>", self.on_part)

            ttk.Label(left, text="Files").pack(anchor="w", pady=(10, 0))
            self.tree = ttk.Treeview(left, columns=("ino",), show="tree headings")
            self.tree.heading("#0", text="name")
            self.tree.column("#0", width=340)
            self.tree.heading("ino", text="inode")
            self.tree.column("ino", width=70)
            self.tree.pack(fill="both", expand=True)
            self.tree.bind("<<TreeviewSelect>>", self.on_node)
            pan.add(left, weight=3)

            right = ttk.Frame(pan)
            ttk.Label(right, text="Details").pack(anchor="w")
            self.info = tk.Text(right, height=8, bg=PANEL, fg=TEXT, bd=0,
                                insertbackground=TEXT, font=("Consolas", 9))
            self.info.pack(fill="x")
            bar = ttk.Frame(right)
            bar.pack(fill="x", pady=6)
            ttk.Button(bar, text="Extract...", command=self.extract).pack(side="left")
            ttk.Button(bar, text="Export tree...", command=self.export_tree).pack(side="left", padx=6)
            ttk.Label(right, text="Content / hex").pack(anchor="w")
            self.hexv = tk.Text(right, bg=PANEL, fg=TEXT, bd=0, wrap="none",
                                insertbackground=TEXT, font=("Consolas", 9))
            self.hexv.pack(fill="both", expand=True)
            pan.add(right, weight=4)

            self.status = tk.StringVar(value="Read-only. The image is never modified.")
            tk.Label(self, textvariable=self.status, bg=PANEL, fg=DIM, anchor="w",
                     padx=8, pady=4).pack(fill="x", side="bottom")

            if initial:
                self.load(initial)

        def set_status(self, s):
            self.status.set(s)
            self.update_idletasks()

        def open_image(self):
            p = filedialog.askopenfilename(
                title="Open disk image",
                filetypes=[("Disk images", "*.img *.dd *.raw *.bin *.gz"), ("All files", "*.*")])
            if p:
                self.load(p)

        def load(self, path):
            try:
                if self.img:
                    self.img.close()
                self.img = DiskImage(path)
            except Exception as e:
                messagebox.showerror("Open failed", str(e))
                return
            self.lbl.config(text="%s   %s" % (os.path.basename(path), human(self.img.size)))
            self.plist.delete(*self.plist.get_children())
            self.tree.delete(*self.tree.get_children())
            if not self.img.parts:
                self.set_status("No MBR partition table found.")
                return
            for p in self.img.parts:
                fs, detail = self.img.detect_fs(p)
                self.plist.insert("", "end", iid=p["name"], text=p["name"],
                                  values=(p["type_name"], human(p["length"]), fs))
            self.set_status("%d partitions. Select one to scan its directory tree."
                            % len(self.img.parts))

        def on_part(self, _evt=None):
            sel = self.plist.selection()
            if not sel or not self.img:
                return
            p = self.img.part(sel[0])
            if not p:
                return
            self.cur_part = p
            fs, detail = self.img.detect_fs(p)
            self.info.delete("1.0", "end")
            self.info.insert("end", "%s   type %s (0x%02x)\nbase   %d (0x%x)\nsize   %s\nfs     %s  %s\n"
                             % (p["name"], p["type_name"], p["type"], p["base"],
                                p["base"], human(p["length"]), fs, detail))
            for sb in self.img.superblocks(p):
                self.info.insert("end", "sb@0x%x serial=%d inode_ptr=0x%x levels=%d\n"
                                 % (sb["off"], sb["serial"], sb["inode_ptr"], sb["inode_levels"]))
            self.hexv.delete("1.0", "end")
            self.hexv.insert("end", hexdump(self.img.read(p["base"], 512), p["base"]))
            self.tree.delete(*self.tree.get_children())
            threading.Thread(target=self._scan, args=(p,), daemon=True).start()

        def _scan(self, p):
            self._cancel = False

            def prog(done, total, n):
                if done % (64 * 1024 * 1024) < 8 * 1024 * 1024:
                    self.set_status("Scanning %s: %s / %s, %d directories..."
                                    % (p["name"], human(done), human(total), n))

            dirs = self.img.scan_dirs(p, progress=prog, cancel=lambda: self._cancel)
            self.dirs = dirs
            self.paths = build_paths(dirs)
            self.after(0, self._fill_tree, p)

        def _fill_tree(self, p):
            self.tree.delete(*self.tree.get_children())
            if not self.dirs:
                self.set_status("%s: no directory blocks found. "
                                "Filesystem may differ or the area is empty." % p["name"])
                return
            roots = [1] if 1 in self.dirs else [
                i for i, d in self.dirs.items() if d["parent"] not in self.dirs]
            for r in roots[:8]:
                self._add_node("", r, "/" if r == 1 else "(root %d)" % r, set())
            self.set_status("%s: %d directories, %d paths. Read-only."
                            % (p["name"], len(self.dirs), len(self.paths)))

        def _add_node(self, parent, ino, name, seen):
            node = self.tree.insert(parent, "end", text=name, values=(ino,))
            if ino in seen:
                return
            seen.add(ino)
            d = self.dirs.get(ino)
            if not d:
                return
            for nm, cino in sorted(d["kids"]):
                if nm in (".", ".."):
                    continue
                if cino in self.dirs:
                    self._add_node(node, cino, nm + "/", seen)
                else:
                    self.tree.insert(node, "end", text=nm, values=(cino,))

        def _sel_inode(self):
            sel = self.tree.selection()
            if not sel:
                return None, None
            vals = self.tree.item(sel[0], "values")
            if not vals:
                return None, None
            return int(vals[0]), self.tree.item(sel[0], "text")

        def on_node(self, _evt=None):
            ino, name = self._sel_inode()
            if ino is None or not self.cur_part:
                return
            self.info.delete("1.0", "end")
            path = self.paths.get(ino, "?")
            self.info.insert("end", "%s\ninode  %d\npath   %s\n" % (name, ino, path))
            if ino in self.dirs:
                d = self.dirs[ino]
                self.info.insert("end", "type   directory (%d entries)\nparent inode %d\n"
                                 % (len(d["kids"]), d["parent"]))
                self.hexv.delete("1.0", "end")
                self.hexv.insert("end", hexdump(self.img.read(d["offset"], 512), d["offset"]))
                return
            res = self.img.resolve_inode(self.cur_part, ino)
            if not res:
                self.info.insert("end", "type   file\nstatus inode struct not located\n"
                                        "       (QNX6 scrambles inode numbers across allocation\n"
                                        "        groups; this build's map is not yet solved)\n")
                self.hexv.delete("1.0", "end")
                return
            off, node = res
            self.info.insert("end", "type   file  %s\nsize   %s\ninode@ 0x%x\nblocks %s\n"
                             % (mode_str(node["mode"]), human(node["size"]), off,
                                ", ".join(str(b) for b in node["block_ptr"] if b not in (0, NIL))))
            data, warn = self.img.read_file(self.cur_part, node, max_bytes=64 * 1024)
            if warn:
                self.info.insert("end", "note   %s\n" % warn)
            self.hexv.delete("1.0", "end")
            self.hexv.insert("end", hexdump(data[:4096], 0) if data else "(no data)")

        def extract(self):
            from tkinter import filedialog, messagebox
            ino, name = self._sel_inode()
            if ino is None or not self.cur_part:
                return
            res = self.img.resolve_inode(self.cur_part, ino)
            if not res:
                messagebox.showinfo("Cannot extract",
                                    "The inode struct for this file could not be located.\n\n"
                                    "Browsing works because directory blocks self-identify, but "
                                    "resolving an inode number to its data blocks is not solved "
                                    "for this filesystem build yet.")
                return
            _off, node = res
            data, warn = self.img.read_file(self.cur_part, node)
            if not data:
                messagebox.showinfo("Cannot extract", warn or "No data.")
                return
            dest = filedialog.asksaveasfilename(initialfile=name.rstrip("/"))
            if not dest:
                return
            with open(dest, "wb") as fh:
                fh.write(data)
            self.set_status("Wrote %s (%s)%s" % (dest, human(len(data)),
                                                 "  -- " + warn if warn else ""))

        def export_tree(self):
            from tkinter import filedialog
            if not self.paths:
                return
            dest = filedialog.asksaveasfilename(defaultextension=".txt",
                                                initialfile="tree.txt")
            if not dest:
                return
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("# %s  %s\n" % (os.path.basename(self.img.path),
                                         self.cur_part["name"] if self.cur_part else ""))
                for i, pth in sorted(self.paths.items(), key=lambda kv: kv[1]):
                    fh.write("%-70s [ino %d]%s\n" % (pth, i, "/" if i in self.dirs else ""))
            self.set_status("Wrote %s (%d paths)" % (dest, len(self.paths)))

    HddTool().mainloop()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
    elif len(args) >= 2 and args[1] == "gui":
        gui(args[0])
    elif args and os.path.isfile(args[0]) and len(args) > 1:
        sys.exit(cli(args))
    elif args and os.path.isfile(args[0]):
        sys.exit(cli(args))
    else:
        gui()
