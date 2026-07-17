# ============================================================================
# scan_all_firmware.py -- batch harness that reproduces the "universal BT/AUX
# fix" tested matrix: for every firmware package x every model variant, extract
# PCM3Root and report the signature verdict (PATCH / NO-OP / anomaly).
#
# This is the FULL pipeline we used to validate 31 builds. It is environment-
# coupled (Windows + WSL + WinRAR + liblzo2); for a single already-extracted
# PCM3Root use the portable, dependency-free scan_pcm3root.py instead.
#
# Pipeline per binary:  UnRAR the IFS1  ->  LZO inflate  ->  carve PCM3Root  ->
#                       scan for  05 1e 01 e1 15 1e  (flip byte at +2: 01->07)
#
# Config via environment (defaults shown):
#   PCM_ISO      dir of PCM31<REGION><VER>.rar packages   (D:\PCM\ISO Extract)
#   PCM_WORK     scratch dir for extraction               (%TEMP%\fw_matrix)
#   PCM_UNRAR    UnRAR/unrar executable                   (WinRAR UnRAR.exe)
#   PCM_INFLATE  IFS LZO inflate helper (see note below)  (env-supplied)
#   PCM_LZO      liblzo2 shared object for the inflater    (/lib/.../liblzo2.so.2)
#
# INFLATE note: the IFS1 payload is a Harman hbcifs LZO1X stream. Any inflater
# that turns an .ifs into a raw QNX imagefs works here; PCM-Forge ships one at
# PCM4/tools/lzo1x.py (pure Python). Set PCM_INFLATE to whichever you use.
# ============================================================================
import subprocess, struct, os, re, tempfile

UNRAR   = os.environ.get('PCM_UNRAR',   r"C:\Program Files\WinRAR\UnRAR.exe")
ISO     = os.environ.get('PCM_ISO',     r"D:\PCM\ISO Extract")
WORK    = os.environ.get('PCM_WORK',    os.path.join(tempfile.gettempdir(), "fw_matrix"))
INFLATE = os.environ.get('PCM_INFLATE', '')   # path to your IFS LZO inflater
LZO     = os.environ.get('PCM_LZO',     '/lib/x86_64-linux-gnu/liblzo2.so.2')
SIG      = bytes.fromhex('051e01e1151e')
FALLBACK = b'Fallback from A2DP to TUNER_FM'
os.makedirs(WORK, exist_ok=True)

def wsl(p):
    p = os.path.abspath(p); return '/mnt/' + p[0].lower() + p[2:].replace('\\', '/')

# ---- Phase 1: extract every PCM3_IFS1*.ifs from every PCM31*.rar ----
rars = sorted(f for f in os.listdir(ISO) if re.match(r'PCM31[A-Z]+\d+\.rar$', f))
jobs = []
for rar in rars:
    pkg = rar[:-4]
    lst = subprocess.run([UNRAR, 'l', os.path.join(ISO, rar)], capture_output=True, text=True, errors='ignore').stdout
    variants = sorted(set(re.findall(r'(\S+PCM3_IFS1\w*\.ifs)', lst)))
    got = 0
    for inner in variants:
        base = inner.replace('/', '\\').split('\\')[-1]
        subprocess.run([UNRAR, 'e', os.path.join(ISO, rar), inner, WORK + os.sep, '-y'], capture_output=True)
        src = os.path.join(WORK, base)
        if not os.path.exists(src):
            continue
        dst = os.path.join(WORK, pkg + '__' + base)
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst); jobs.append((pkg, base, dst)); got += 1
    print(f"[extract] {pkg}: {got} IFS1 variants")

# ---- Phase 2: inflate all in one WSL call (delete each .ifs after) ----
if not INFLATE:
    raise SystemExit("Set PCM_INFLATE to your IFS LZO inflater (e.g. PCM4/tools/lzo1x.py); see header.")
cmds = []
for pkg, base, ifs in jobs:
    raw = ifs[:-4] + '.raw'
    cmds.append(f'python3 {INFLATE} "{wsl(ifs)}" -o "{wsl(raw)}" --lzo {LZO} >/dev/null 2>&1 && rm -f "{wsl(ifs)}" || echo "FAIL {base}"')
print(f"[inflate] {len(cmds)} images ...")
subprocess.run(['wsl', 'bash', '-c', '\n'.join(cmds)])

# ---- Phase 3: carve PCM3Root + scan signature ----
def carve(raw):
    d = open(raw, 'rb').read(); pos = 0
    while True:
        pos = d.find(b'\x7fELF\x01\x01\x01', pos)
        if pos < 0:
            return None
        if struct.unpack_from('<H', d, pos + 18)[0] == 0x2A:
            e_phoff = struct.unpack_from('<I', d, pos + 0x1c)[0]; ents, num = struct.unpack_from('<HH', d, pos + 0x2a); end = 0
            for i in range(num):
                o = pos + e_phoff + i * ents
                if o + 20 <= len(d):
                    po, pv, pp, fs = struct.unpack_from('<IIII', d, o + 4); end = max(end, po + fs)
            body = d[pos:pos + end]
            if end > 1_500_000 and b'CPSoundPresCtrl' in body:
                return body
        pos += 4

def o2v_fn(b):
    e_phoff = struct.unpack_from('<I', b, 0x1c)[0]; ents, num = struct.unpack_from('<HH', b, 0x2a); segs = []
    for i in range(num):
        o = e_phoff + i * ents; t, po, pv, pp, fs = struct.unpack_from('<IIIII', b, o)
        if t == 1:
            segs.append((po, pv, fs))
    return lambda off: next((pv + (off - po) for po, pv, fs in segs if po <= off < po + fs), None)

def parse(pkg, base):
    m = re.match(r'PCM31([A-Z]+)(\d+)', pkg); region = m.group(1); ver = f"v{int(m.group(2))/100:.2f}"
    model = '9x1' if '_9x1' in base else 'Macan' if '_Macan' in base else 'Navis' if '_Navis' in base else 'generic'
    face = 'MOPF' if 'MOPF' in base else 'pre'
    return region, ver, model, face

rows = []
for pkg, base, ifs in jobs:
    raw = ifs[:-4] + '.raw'; region, ver, model, face = parse(pkg, base)
    if not os.path.exists(raw):
        rows.append((region, ver, model, face, 'INFLATE-FAIL', '-', '-')); continue
    body = carve(raw)
    if body is None:
        rows.append((region, ver, model, face, 'no-PCM3Root', '-', '-'))
    else:
        n = body.count(SIG); has_fb = FALLBACK in body
        if n == 1:
            j = body.find(SIG); va = o2v_fn(body)(j + 2); byte = body[j + 2]
            verdict = 'PATCH' if byte == 1 else f'byte=0x{byte:02x}?'
            rows.append((region, ver, model, face, verdict, hex(va) if va else '?', f'0x{byte:02x}'))
        elif n == 0:
            rows.append((region, ver, model, face, 'NO-OP(safe)' if not has_fb else 'BUG-BUT-NO-SIG!', '-', '-'))
        else:
            rows.append((region, ver, model, face, f'AMBIG({n})', '-', '-'))
    try:
        os.remove(raw)
    except OSError:
        pass

print("\n================ COMPREHENSIVE BT-FIX MATRIX ================")
print("%-4s %-6s %-8s %-4s %-14s %-12s %s" % ('reg', 'ver', 'model', 'face', 'verdict', 'address', 'byte'))
print("-" * 70)
for r in sorted(rows):
    print("%-4s %-6s %-8s %-4s %-14s %-12s %s" % (r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
patch = sum(1 for r in rows if r[4] == 'PATCH'); noop = sum(1 for r in rows if 'NO-OP' in r[4])
anom = sum(1 for r in rows if 'BUG-BUT' in r[4] or 'AMBIG' in r[4] or '?' in r[4])
print("-" * 70)
print(f"TOTAL {len(rows)} binaries:  PATCH={patch}  NO-OP(safe)={noop}  ANOMALIES={anom}")
