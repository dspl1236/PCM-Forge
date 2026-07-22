#!/usr/bin/env python3
# ============================================================
# PCM-Forge  cvalue_tool.py  --  Harman CVALUE*.CVA reader/decoder
# ------------------------------------------------------------
# Decodes the Harman/Becker PCM 3.1 "CValue" coding-value files
# (CVALUE00020686.CVA etc.) that persdump2 rejects with
# "Invalid Header" -- because CVALUE is NOT a persistence blob,
# it is a serialized C++ CValue object (CValue.cpp).
#
# Format (reverse-engineered from firmware CValue class + 8 samples,
# all little-endian):
#
#   FRAME (every node, recursive):
#       u16 tag          node type   (0x09 container | 0x0a typed | 0x02 scalar ...)
#       u16 id16         name/id hash (constant within a nested group; 0 = root)
#       u32 length       payload byte-count
#       u8  payload[length]
#     => on disk always: 8 + length == filesize   (integrity check)
#
#   tag 0x09  -> CONTAINER: payload is a run of child FRAMEs (recurse)
#   tag 0x0a  -> TYPED node. If payload opens with the coding-table
#                signature <u32 crc><0x00000065><0x00000014><u32 count><u32 len>
#                it is a CODING-CHANNEL TABLE of entries:
#                   u16 id       channel id
#                   u16 vallen   value length in bytes   (0x04->4B, 0x01->1B ...)
#                   u16 rev      write/revision counter
#                   u16 flag     0x0000 normal | 0xFFFF coded/locked-default
#                   u8  value[vallen]
#                Otherwise the payload is an opaque typed blob (hex-dumped).
#   tag 0x02  -> small scalar (payload = raw value bytes)
#
# Usage:
#   python cvalue_tool.py FILE.CVA [FILE2.CVA ...]     annotated decode
#   python cvalue_tool.py --json FILE.CVA              machine-readable JSON
#   python cvalue_tool.py --raw  FILE.CVA              force hex/ascii only
#   python cvalue_tool.py --dir  DIR                   decode every *.CVA in DIR
#
# Brick-safe: READ-ONLY. Never writes to a .CVA. github.com/dspl1236/PCM-Forge
# ============================================================
import sys, os, struct, json

# ---- low-level helpers -------------------------------------------------
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]

CODING_MAGIC = 0x65        # subheader[1]
CODING_HDRLEN = 0x14       # subheader[2] == 20 (the subheader's own size)

TAG_NAMES = {0x02: 'scalar', 0x09: 'container', 0x0a: 'typed'}

def is_printable(bs):
    if not bs:
        return False
    core = bs[:-1] if bs[-1:] == b'\x00' else bs
    if not core:
        return False
    return all(32 <= c < 127 for c in core)

def render_value(bs):
    """Human interpretations of a raw value blob."""
    out = {'hex': bs.hex(), 'len': len(bs)}
    if is_printable(bs):
        out['ascii'] = bs.rstrip(b'\x00').decode('latin-1')
    n = len(bs)
    if n == 1:
        out['u8'] = bs[0]
    elif n == 2:
        out['u16'] = struct.unpack('<H', bs)[0]
    elif n == 4:
        out['u32'] = struct.unpack('<I', bs)[0]
        out['i32'] = struct.unpack('<i', bs)[0]
        out['f32'] = round(struct.unpack('<f', bs)[0], 6)
    elif n == 8:
        out['u64'] = struct.unpack('<Q', bs)[0]
        out['f64'] = struct.unpack('<d', bs)[0]
    return out

def value_str(v):
    parts = []
    if 'ascii' in v: parts.append('"%s"' % v['ascii'])
    for k in ('u8', 'u16', 'u32', 'i32', 'f32', 'u64', 'f64'):
        if k in v: parts.append('%s=%s' % (k, v[k]))
    tag = ' '.join(parts)
    hx = v['hex']
    if len(hx) > 48: hx = hx[:48] + '..'
    return ('%-28s ' % tag if tag else '') + '[%s]' % hx

# ---- parsers -----------------------------------------------------------
def parse_coding_table(payload):
    """payload of a tag-0x0a coding-channel node. Returns dict or None."""
    if len(payload) < 20:
        return None
    crc = u32(payload, 0)
    if u32(payload, 4) != CODING_MAGIC or u32(payload, 8) != CODING_HDRLEN:
        return None
    count = u32(payload, 12)
    plen  = u32(payload, 16)
    entries, o, end = [], 20, len(payload)
    while o + 8 <= end:
        cid    = u16(payload, o)
        vallen = u16(payload, o + 2)
        rev    = u16(payload, o + 4)
        flag   = u16(payload, o + 6)
        vstart = o + 8
        if vallen > 0x1000 or vstart + vallen > end:
            entries.append({'error': 'entry@%d does not fit (vallen=%d)' % (o, vallen)})
            break
        value = payload[vstart:vstart + vallen]
        entries.append({'id': cid, 'vallen': vallen, 'rev': rev, 'flag': flag,
                        'value': render_value(value)})
        o = vstart + vallen
    return {'kind': 'coding-table', 'crc32': crc, 'count': count,
            'declared_len': plen, 'trailing': end - o, 'entries': entries}

def _tile_frames(buf, start):
    """Tile buf[start:] as a run of child FRAMEs. Return list or None."""
    frames, o, end = [], start, len(buf)
    while o + 8 <= end:
        if u16(buf, o) not in TAG_NAMES:
            return None
        length = u32(buf, o + 4)
        body_start = o + 8
        if body_start + length > end:
            return None
        frames.append(buf[o:body_start + length])
        o = body_start + length
    if o != end or not frames:
        return None
    return frames

def try_parse_frames(buf):
    """Find where the child-FRAME run starts (a container may carry a small
    metadata header first) and tile the rest. Returns (header_len, [frames])
    or None."""
    for start in range(0, min(len(buf) - 8, 32) + 1):
        # only bother trying at offsets that look like a frame tag
        if start and u16(buf, start) not in TAG_NAMES:
            continue
        frames = _tile_frames(buf, start)
        if frames is not None:
            return start, frames
    return None

def parse_frame(buf, depth=0):
    """Parse one FRAME (buf starts at the 8-byte header). Returns node dict."""
    tag    = u16(buf, 0)
    id16   = u16(buf, 2)
    length = u32(buf, 4)
    payload = buf[8:8 + length]
    node = {'tag': tag, 'tag_name': TAG_NAMES.get(tag, '0x%02x' % tag),
            'id16': id16, 'length': length}

    if tag == 0x09:                                   # container: recurse
        got = try_parse_frames(payload)
        if got is not None:
            hlen, frames = got
            node['kind'] = 'container'
            node['header'] = payload[:hlen].hex()
            node['children'] = [parse_frame(fb, depth + 1) for fb in frames]
            return node

    if tag == 0x0a:                                   # typed node
        table = parse_coding_table(payload)
        if table is not None:
            node.update(table)
            return node
        # a tag-0x0a payload may itself be nested frames (rare) -> try
        got = try_parse_frames(payload)
        if got is not None and depth < 6:
            hlen, frames = got
            node['kind'] = 'container'
            node['header'] = payload[:hlen].hex()
            node['children'] = [parse_frame(fb, depth + 1) for fb in frames]
            return node

    # scalar / opaque leaf
    node['kind'] = 'leaf'
    node['value'] = render_value(payload)
    return node

def parse_file(path):
    with open(path, 'rb') as f:
        data = f.read()
    res = {'file': os.path.basename(path), 'size': len(data)}
    if len(data) < 8:
        res['error'] = 'too short to be a CVALUE frame'
        return res
    length = u32(data, 4)
    res['integrity'] = ('OK' if 8 + length == len(data)
                        else 'MISMATCH (8+%d != %d)' % (length, len(data)))
    res['root'] = parse_frame(data)
    return res

# ---- pretty printer ----------------------------------------------------
def print_node(node, indent=0):
    pad = '  ' * indent
    hdr = '%s<%s tag=0x%02x id16=0x%04x len=%d>' % (
        pad, node['tag_name'], node['tag'], node['id16'], node['length'])
    print(hdr)
    kind = node.get('kind')
    if kind == 'container':
        for c in node['children']:
            print_node(c, indent + 1)
    elif kind == 'coding-table':
        print('%s  coding-table: %d channels  crc32=0x%08x  trailing=%d'
              % (pad, node['count'], node['crc32'], node['trailing']))
        for e in node['entries']:
            if 'error' in e:
                print('%s    ! %s' % (pad, e['error'])); continue
            fl = ' F' if e.get('flag') else '  '
            print('%s    ch 0x%03x (%4d)  rev=%-4d%s %s'
                  % (pad, e['id'], e['id'], e['rev'], fl, value_str(e['value'])))
    else:  # leaf
        v = node['value']
        if v['len'] > 32:                 # opaque typed blob: show structure
            raw = bytes.fromhex(v['hex'])
            print('%s  = opaque blob, %d bytes' % (pad, v['len']))
            fields = [struct.unpack_from('<I', raw, i)[0]
                      for i in range(0, min(20, len(raw) - 3), 4)]
            print('%s    lead u32: crc32=0x%08x  ' % (pad, fields[0])
                  + '  '.join('0x%x' % f for f in fields[1:]))
            for i in range(0, min(64, len(raw)), 16):
                chunk = raw[i:i + 16]
                asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
                print('%s    %04x  %-32s  %s' % (pad, i, chunk.hex(), asc))
            if len(raw) > 64:
                print('%s    ... (%d more bytes)' % (pad, len(raw) - 64))
        else:
            print('%s  = %s' % (pad, value_str(v)))

def print_file(res):
    print('=' * 60)
    print('%s   (%d bytes)   integrity: %s'
          % (res['file'], res['size'], res.get('integrity', '?')))
    if 'error' in res:
        print('  ERROR: %s' % res['error']); return
    print_node(res['root'])

# ---- main --------------------------------------------------------------
def main(argv):
    args = argv[1:]
    as_json = '--json' in args;  args = [a for a in args if a != '--json']
    raw     = '--raw'  in args;  args = [a for a in args if a != '--raw']
    if '--dir' in args:
        i = args.index('--dir'); d = args[i + 1]
        args = [os.path.join(d, f) for f in sorted(os.listdir(d))
                if f.lower().endswith('.cva')]
    if not args:
        print(__doc__ if __doc__ else 'usage: cvalue_tool.py FILE.CVA ...')
        return 1
    results = []
    for p in args:
        try:
            r = parse_file(p)
        except Exception as e:
            r = {'file': os.path.basename(p), 'error': 'parse crash: %r' % e}
        if raw and 'root' in r:
            r['root'] = {'tag': r['root']['tag'], 'raw': True}
        results.append(r)
        if not as_json:
            print_file(r)
    if as_json:
        print(json.dumps(results, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
