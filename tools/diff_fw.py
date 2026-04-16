#!/usr/bin/env python3
"""
PCM-Forge firmware comparison tool.

Compares two or more binary files and reports:
  - Byte ranges that are identical across all inputs
  - Byte ranges that differ, with context hex dumps
  - Overall statistics (total size, % identical)

Useful for comparing PCM 3.1 IOC firmware variants like
PCM31_IOC_D1_9600_UPD.bin vs PCM31_IOC_E2_D1_9608_UPD.bin to identify
which regions changed between firmware releases.

Based on the approach in jilleb/binary_tools (MIT-style) extended with:
  - Proper CLI arg parsing
  - Works with any number of files (not just a directory scan)
  - Context hex dumps at diff boundaries
  - Byte-range summarization
  - Performance: O(n) file scan instead of O(n^2) seeks

Usage:
    python tools/diff_fw.py file1.bin file2.bin
    python tools/diff_fw.py --context 32 file1.bin file2.bin
    python tools/diff_fw.py --only-diffs file1.bin file2.bin file3.bin
    python tools/diff_fw.py --dir research/firmware --ext .bin
"""
import argparse
import glob
import os
import sys


def hexdump_line(data, offset):
    """Format 16 bytes as 'OFFSET  HH HH HH ...  ascii'."""
    hex_part = ' '.join(f'{b:02x}' for b in data)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    return f'{offset:08x}  {hex_part:<48s}  {ascii_part}'


def compare_files(file_paths, context=16, only_diffs=False):
    """Compare N files byte-by-byte. Returns (identical_ranges, diff_ranges)."""
    # Read all files fully — these are small-ish firmware images
    blobs = []
    for path in file_paths:
        with open(path, 'rb') as f:
            blobs.append(f.read())

    sizes = [len(b) for b in blobs]
    min_size = min(sizes)
    max_size = max(sizes)

    if min_size != max_size:
        print(f"Note: files have different sizes ({min_size} to {max_size}), "
              f"comparing first {min_size} bytes", file=sys.stderr)

    # Walk byte by byte, tracking identical/diff ranges
    identical_ranges = []
    diff_ranges = []
    in_diff = False
    range_start = 0

    for i in range(min_size):
        bytes_at_i = [b[i] for b in blobs]
        all_same = all(x == bytes_at_i[0] for x in bytes_at_i)

        if all_same:
            if in_diff:
                # Close current diff range, start identical range
                diff_ranges.append((range_start, i - 1))
                range_start = i
                in_diff = False
        else:
            if not in_diff:
                # Close identical range, start diff range
                if i > range_start:
                    identical_ranges.append((range_start, i - 1))
                range_start = i
                in_diff = True

    # Close final range
    final = (range_start, min_size - 1)
    if in_diff:
        diff_ranges.append(final)
    else:
        if final[1] >= final[0]:
            identical_ranges.append(final)

    return identical_ranges, diff_ranges, blobs, sizes


def print_report(file_paths, identical_ranges, diff_ranges, blobs, sizes,
                 context=16, only_diffs=False):
    """Pretty-print the comparison results."""
    print(f"\nFiles compared:")
    for path, size in zip(file_paths, sizes):
        print(f"  {path}  ({size:,} bytes)")
    print()

    total = min(sizes)
    id_bytes = sum(r[1] - r[0] + 1 for r in identical_ranges)
    diff_bytes = sum(r[1] - r[0] + 1 for r in diff_ranges)

    print(f"Total bytes compared:  {total:,}")
    print(f"Identical:             {id_bytes:,} ({id_bytes/total*100:.1f}%)")
    print(f"Different:             {diff_bytes:,} ({diff_bytes/total*100:.1f}%)")
    print(f"Identical ranges:      {len(identical_ranges)}")
    print(f"Different ranges:      {len(diff_ranges)}")
    print()

    if not only_diffs and identical_ranges:
        print("=" * 78)
        print("IDENTICAL RANGES (merged contiguous regions)")
        print("=" * 78)
        for start, end in identical_ranges:
            length = end - start + 1
            print(f"  0x{start:08x}-0x{end:08x}  ({length:>10,} bytes)")
        print()

    print("=" * 78)
    print(f"DIFFERENT RANGES (with {context}-byte context dumps)")
    print("=" * 78)
    if not diff_ranges:
        print("  (no differences found)")
        return

    for rank, (start, end) in enumerate(diff_ranges, 1):
        length = end - start + 1
        print(f"\n─── Diff #{rank} at 0x{start:08x}-0x{end:08x} ({length:,} bytes) ───")

        # Show context around the diff
        ctx_start = max(0, start - context)
        ctx_end = min(len(blobs[0]), end + context + 1)

        for i, (path, blob) in enumerate(zip(file_paths, blobs)):
            print(f"\n  [{chr(ord('A')+i)}] {os.path.basename(path)}:")
            for off in range(ctx_start, ctx_end, 16):
                chunk = blob[off:off+16]
                line = hexdump_line(chunk, off)
                # Mark diff bytes with a '*' prefix
                marker = '*' if start <= off <= end or start <= off+15 <= end else ' '
                print(f"  {marker}{line}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='Files to compare (2 or more)')
    ap.add_argument('--dir', help='Directory to scan for files (alternative to listing files)')
    ap.add_argument('--ext', default='.bin',
                    help='File extension for --dir scan (default: .bin)')
    ap.add_argument('--context', type=int, default=16,
                    help='Bytes of context to show around each diff (default: 16)')
    ap.add_argument('--only-diffs', action='store_true',
                    help='Only show diff ranges, not identical ones')
    args = ap.parse_args()

    if args.dir:
        pattern = os.path.join(args.dir, f'*{args.ext}')
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"No {args.ext} files found in {args.dir}", file=sys.stderr)
            return 1
    else:
        files = args.files

    if len(files) < 2:
        print("Need at least 2 files to compare. Use --help.", file=sys.stderr)
        return 1

    for f in files:
        if not os.path.isfile(f):
            print(f"Not a file: {f}", file=sys.stderr)
            return 1

    id_ranges, diff_ranges, blobs, sizes = compare_files(files, args.context, args.only_diffs)
    print_report(files, id_ranges, diff_ranges, blobs, sizes,
                 args.context, args.only_diffs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
