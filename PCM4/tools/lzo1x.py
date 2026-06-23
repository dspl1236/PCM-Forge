#!/usr/bin/env python3
"""Pure-Python LZO1X decompressor — faithful port of the Linux kernel
lib/lzo/lzo1x_decompress_safe.c (classic bitstream, version 0).

Key correctness points vs naive ports:
  - explicit `state` machine (0 = expect literal-run, 1..3 = trailing-literal
    count, 4 = just had a literal run)
  - the post-literal-run short match (state==4) copies 3 bytes (NOT 2)
  - the in-state 1..3 short match copies 2 bytes
  - `next` (trailing literal count) comes from opcode&3 (M1/M2) or LE16&3 (M3/M4)

decompress_stream(src, ip) decodes ONE self-terminating LZO1X stream and returns
(out:bytearray, ip:int, reason). For QNX block-framed images, decode each block's
slice separately (the EOF marker may be absent; rely on the block length).
"""

M2_MAX_OFFSET = 0x0800  # 2048


def decompress_stream(src, ip=0, out=None):
    if out is None:
        out = bytearray()
    n = len(src)
    state = 0
    t = 0
    next_ = 0

    try:
        # ---- initial literal handling ----
        if src[ip] > 17:
            t = src[ip] - 17; ip += 1
            if t < 4:
                next_ = t
                state = next_
                if next_:
                    out += src[ip:ip+next_]; ip += next_
            else:
                out += src[ip:ip+t]; ip += t
                state = 4

        # ---- main loop ----
        while True:
            t = src[ip]; ip += 1
            if t < 16:
                if state == 0:
                    # literal run
                    if t == 0:
                        while src[ip] == 0:
                            t += 255; ip += 1
                        t += 15 + src[ip]; ip += 1
                    t += 3
                    out += src[ip:ip+t]; ip += t
                    state = 4
                    continue
                elif state != 4:
                    # short match, state 1..3 : copy 2 bytes
                    next_ = t & 3
                    pos = len(out) - (1 + (t >> 2) + (src[ip] << 2)); ip += 1
                    if pos < 0:
                        return out, ip, f"error:bad_pos({pos})"
                    out.append(out[pos]); out.append(out[pos+1])
                else:
                    # state == 4 : post-literal-run short match, copy 3 bytes
                    next_ = t & 3
                    pos = len(out) - (1 + M2_MAX_OFFSET + (t >> 2) + (src[ip] << 2)); ip += 1
                    if pos < 0:
                        return out, ip, f"error:bad_pos({pos})"
                    out.append(out[pos]); out.append(out[pos+1]); out.append(out[pos+2])
            elif t >= 64:
                next_ = t & 3
                pos = len(out) - (1 + ((t >> 2) & 7) + (src[ip] << 3)); ip += 1
                length = (t >> 5) + 1
                if pos < 0:
                    return out, ip, f"error:bad_pos({pos})"
                for _ in range(length):
                    out.append(out[pos]); pos += 1
            elif t >= 32:
                length = t & 31
                if length == 0:
                    while src[ip] == 0:
                        length += 255; ip += 1
                    length += 31 + src[ip]; ip += 1
                length += 2
                d = src[ip] | (src[ip+1] << 8); ip += 2
                next_ = d & 3
                pos = len(out) - (1 + (d >> 2))
                if pos < 0:
                    return out, ip, f"error:bad_pos({pos})"
                for _ in range(length):
                    out.append(out[pos]); pos += 1
            else:  # 16 <= t < 32
                hi = (t & 8) << 11
                length = t & 7
                if length == 0:
                    while src[ip] == 0:
                        length += 255; ip += 1
                    length += 7 + src[ip]; ip += 1
                length += 2
                d = src[ip] | (src[ip+1] << 8); ip += 2
                next_ = d & 3
                off = hi + (d >> 2)
                if off == 0:
                    return out, ip, "eof"
                pos = len(out) - (off + 0x4000)
                if pos < 0:
                    return out, ip, f"error:bad_pos({pos})"
                for _ in range(length):
                    out.append(out[pos]); pos += 1

            # ---- match_next: copy trailing literals ----
            state = next_
            if next_:
                out += src[ip:ip+next_]; ip += next_
    except IndexError:
        return out, ip, "exhausted"
    return out, ip, "done"


# backward-compat alias used by older harness scripts
def lzo1x_decompress_stream(src, ip=0, out=None, max_out=None):
    return decompress_stream(src, ip=ip, out=out)


if __name__ == "__main__":
    print("lzo1x (kernel-faithful) loaded")
