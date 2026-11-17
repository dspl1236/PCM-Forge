/* nettest -- check internet + DNS from the PCM, which has no ping/telnet/nslookup.
 *
 *   nettest <host or a.b.c.d> [port]      (port defaults to 80)
 *
 * Resolves the name (through /etc/resolv.conf or the in-memory resolver
 * settings), then opens a TCP connection and closes it. Prints one line per
 * step. Exit code: 0 connected, 1 usage, 2 name lookup failed, 3 timeout (5 s),
 * 4 connect refused/failed, 5 no socket.
 * Build: ./build.sh nettest.c   (links the libsocket.so.2 stub as well)
 */
extern int  write(int, const void *, int);
extern unsigned alarm(unsigned);
extern void _exit(int);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
extern int  close(int);

/* libsocket.so.2 */
struct hostent { char *h_name; char **h_aliases; int h_addrtype; int h_length; char **h_addr_list; };
extern struct hostent *gethostbyname(const char *);
extern int socket(int, int, int);
extern int connect(int, const void *, int);

/* QNX (BSD 4.4) sockaddr_in: sin_len, sin_family, sin_port (network order), sin_addr */
struct sockaddr_in { unsigned char len, family; unsigned short port; unsigned char addr[4]; char zero[8]; };

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void out(const char *s) { write(1, s, slen(s)); }
static void outn(unsigned v) { char b[12]; int i = 11; b[i] = 0; do { b[--i] = '0' + v % 10; v /= 10; } while (v); out(b + i); }
static void on_alarm(int sig) { (void)sig; out("  TIMEOUT (5 s): no answer -- no route out, or a firewall\n"); _exit(3); }

int main(int argc, char **argv)
{
    unsigned port = 80; const char *p;
    struct hostent *h; struct sockaddr_in sa; int i, s;
    if (argc < 2) { out("usage: nettest <host or a.b.c.d> [port]\n"); return 1; }
    if (argc > 2) { port = 0; for (p = argv[2]; *p >= '0' && *p <= '9'; p++) port = port * 10 + (*p - '0'); }

    out("lookup "); out(argv[1]); out(" ... ");
    h = gethostbyname(argv[1]);
    if (!h || !h->h_addr_list || !h->h_addr_list[0] || h->h_length != 4) { out("FAILED (no DNS answer)\n"); return 2; }
    for (i = 0; i < 4; i++) { outn((unsigned char)h->h_addr_list[0][i]); out(i < 3 ? "." : "\n"); }

    for (i = 0; i < 16; i++) ((char *)&sa)[i] = 0;
    sa.len = 16; sa.family = 2; /* AF_INET */
    sa.port = (unsigned short)(((port & 0xff) << 8) | ((port >> 8) & 0xff));
    for (i = 0; i < 4; i++) sa.addr[i] = (unsigned char)h->h_addr_list[0][i];

    s = socket(2, 1, 0);        /* AF_INET, SOCK_STREAM */
    if (s < 0) { out("  no socket\n"); return 5; }
    signal(14, on_alarm);       /* SIGALRM */
    alarm(5);
    out("connect port "); outn(port); out(" ... ");
    if (connect(s, &sa, 16) != 0) { alarm(0); out("FAILED (refused or no route)\n"); close(s); return 4; }
    alarm(0);
    out("OK -- internet works\n");
    close(s);
    return 0;
}
