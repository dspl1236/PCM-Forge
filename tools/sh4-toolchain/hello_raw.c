/* hello_raw -- the smallest PCM-Forge SH4 program: freestanding, bare crt.S,
 * only raw libc calls (write, getpid, time). Proves the toolchain end to end.
 *
 *   ./build.sh hello_raw.c        then on the unit:  ./hello_raw
 * Prints a few lines and exits 0. Writes nothing anywhere. */
extern int  write(int, const void *, int);
extern int  getpid(void);
extern long time(long *);

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void out(const char *s) { write(1, s, slen(s)); }

static void out_num(long v)
{
    char b[24];
    int i = sizeof b;
    int neg = v < 0;
    unsigned long u = neg ? -(unsigned long)v : (unsigned long)v;
    b[--i] = 0;
    do { b[--i] = '0' + u % 10; u /= 10; } while (u && i > 1);
    if (neg) b[--i] = '-';
    out(b + i);
}

int main(int argc, char **argv)
{
    out("hello_raw: PCM-Forge SH4 toolchain, freestanding build\n");
    out("  argc="); out_num(argc);
    out("  argv[0]="); out(argc > 0 && argv[0] ? argv[0] : "?");
    out("\n  pid="); out_num(getpid());
    out("  time="); out_num(time(0));
    out("\nhello_raw: OK\n");
    return 0;
}
