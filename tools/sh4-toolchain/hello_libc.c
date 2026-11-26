/* hello_libc -- stdio, heap and environment from QNX's own libc.so.2, built
 * without the QNX SDK. build.sh links it with crt_libc.S, which initialises libc
 * (_init_libc) the way a real QNX _start does.
 *
 *   ./build.sh hello_libc.c       then on the unit:  ./hello_libc
 *
 * Each stage first says what it is about to try with a raw write(), so if one
 * of them fails the last line printed names it. Writes nothing anywhere;
 * allocates and frees 64 KB of RAM. Exits 0 when every stage passed. */
extern int   write(int, const void *, int);
extern int   printf(const char *, ...);
extern int   snprintf(char *, unsigned, const char *, ...);
extern void *malloc(unsigned);
extern void  free(void *);
extern void *memset(void *, int, unsigned);
extern unsigned strlen(const char *);
extern char *getenv(const char *);
extern int   getpid(void);
extern long  time(long *);

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void mark(const char *s) { write(1, s, slen(s)); }   /* no libc needed */

int main(int argc, char **argv, char **envp)
{
    char buf[160];
    int n, i, bad;
    unsigned char *p;
    const char *path;

    mark("[1] main reached: _init_libc returned\n");

    mark("[2] snprintf + strlen ...\n");
    n = snprintf(buf, sizeof buf, "    argc=%d pid=%d time=%ld strlen(argv[0])=%u\n",
                 argc, getpid(), time(0), argc > 0 ? strlen(argv[0]) : 0);
    if (n <= 0 || n >= (int)sizeof buf) { mark("    snprintf FAILED\n"); return 2; }
    write(1, buf, n);

    mark("[3] malloc 64 KB, fill, check, free ...\n");
    p = malloc(65536);
    if (!p) { mark("    malloc returned NULL\n"); return 3; }
    memset(p, 0x5a, 65536);
    for (i = bad = 0; i < 65536; i++)
        bad += p[i] != 0x5a;
    free(p);
    if (bad) { mark("    memory check FAILED\n"); return 3; }
    mark("    ok\n");

    mark("[4] printf + getenv + envp ...\n");
    path = getenv("PATH");
    for (n = 0; envp && envp[n]; n++)
        ;
    printf("    argv[0]=%s  envp has %d entries  PATH=%.60s\n",
           argc > 0 ? argv[0] : "?", n, path ? path : "(unset)");

    printf("[5] all stages passed\n");
    return 0;                       /* exit() flushes stdout */
}
