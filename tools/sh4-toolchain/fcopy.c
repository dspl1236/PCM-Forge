/*
 * fcopy -- copy with a chosen block size, and time it (PCM 3.1, QNX SH4).
 *
 * Built for the USB speed test: Flash Backup's `cp /dev/fs0` writes to the
 * stick at ~29 KB/s, and this tells apart a slow read, a slow write, and a
 * write size that is too small.
 *
 *   fcopy SRC DST BLOCK_KB MAX_SECONDS [MAX_KB]
 *
 * Copies SRC to DST (DST is created/truncated) in BLOCK_KB reads and writes,
 * until SRC ends, MAX_SECONDS have passed, or MAX_KB are copied. Prints one
 * line:  bytes=N secs=S kbps=R block_kb=B stop=eof|time|size|readerr|writeerr
 * The clock is time(): 1 s resolution, so give tests 20 s or more.
 *
 * Build: ./build.sh fcopy.c   (no QNX SDK -- see build.sh)
 */
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_TRUNC  0x200

extern int  open(const char*, int, ...);
extern int  read(int, void*, unsigned);
extern int  write(int, const void*, int);
extern int  close(int);
extern long time(long*);

#define MAXBLK (1024 * 1024)
static char buf[MAXBLK];

/* no libgcc in these builds, so no '/' or '%': shift-and-subtract division */
static unsigned long udiv(unsigned long a, unsigned long b, unsigned long *rem) {
    unsigned long q = 0, r = 0;
    int i;
    for (i = 31; i >= 0; i--) {
        r = (r << 1) | ((a >> i) & 1);
        if (r >= b) { r -= b; q |= 1UL << i; }
    }
    if (rem) *rem = r;
    return q;
}

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void puts1(const char *s) { write(1, s, slen(s)); }
static void putu(unsigned long v) {
    char t[24]; int i = 23; t[i] = 0;
    if (!v) t[--i] = '0';
    while (v) { unsigned long r; v = udiv(v, 10, &r); t[--i] = '0' + (char)r; }
    puts1(t + i);
}
static unsigned long atou(const char *s) {
    unsigned long v = 0;
    while (*s >= '0' && *s <= '9') v = v * 10 + (unsigned long)(*s++ - '0');
    return v;
}

int main(int argc, char **argv) {
    unsigned long blk, secs, maxb = 0, done = 0;
    long t0, el;
    int in, out;
    const char *stop = "eof";
    if (argc < 5) {
        puts1("usage: fcopy SRC DST BLOCK_KB MAX_SECONDS [MAX_KB]\n");
        return 2;
    }
    blk = atou(argv[3]) * 1024;
    if (blk == 0 || blk > MAXBLK) blk = 64 * 1024;
    secs = atou(argv[4]);
    if (argc > 5) maxb = atou(argv[5]) * 1024;
    in = open(argv[1], O_RDONLY, 0);
    if (in < 0) { puts1("fcopy: cannot open source\n"); return 1; }
    out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (out < 0) { puts1("fcopy: cannot open destination\n"); close(in); return 1; }
    t0 = time(0);
    for (;;) {
        unsigned want = (unsigned)blk;
        int n, w;
        if (maxb && done + want > maxb) want = (unsigned)(maxb - done);
        if (want == 0) { stop = "size"; break; }
        n = read(in, buf, want);
        if (n < 0) { stop = "readerr"; break; }
        if (n == 0) break;
        w = write(out, buf, n);
        if (w != n) { stop = "writeerr"; if (w > 0) done += (unsigned long)w; break; }
        done += (unsigned long)n;
        if (secs && (unsigned long)(time(0) - t0) >= secs) { stop = "time"; break; }
    }
    close(out);                 /* the close is part of the cost: count it */
    close(in);
    el = time(0) - t0;
    puts1("bytes="); putu(done);
    puts1(" secs="); putu((unsigned long)el);
    puts1(" kbps="); putu(el > 0 ? udiv(done >> 10, (unsigned long)el, 0) : 0);
    puts1(" block_kb="); putu(blk >> 10);
    puts1(" stop="); puts1(stop); puts1("\n");
    return 0;
}
