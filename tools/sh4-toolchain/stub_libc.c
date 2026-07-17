/* Link-time STUB for QNX libc.so.2 — only the symbol names/SONAME matter;
 * ldqnx.so.2 binds these to the real libc.so.2 on the PCM at load time. */
int  open(const char *p, int f, ...)              { return -1; }
int  devctl(int a, int b, void *c, unsigned d, int *e) { return -1; }
int  write(int a, const void *b, int c)           { return 0; }
int  read(int a, void *b, unsigned c)             { return -1; }
long lseek(int a, long o, int w)                  { return -1; }
unsigned alarm(unsigned s)                         { return 0; }
int  close(int a)                                 { return 0; }
unsigned sleep(unsigned s)                        { return 0; }
int  usleep(unsigned u)                           { return 0; }
void _exit(int c)                                 { for (;;) ; }
typedef void (*sighandler_t)(int);
sighandler_t signal(int a, sighandler_t h)        { return h; }
int  getpid(void)                                  { return 0; }
/* QNX Neutrino IPC — real impls resolved from libc.so.2 on the PCM at load */
int  ChannelCreate(unsigned f)                     { return -1; }
int  ChannelDestroy(int c)                         { return -1; }
int  ConnectAttach(unsigned n,int p,int c,unsigned i,int f) { return -1; }
int  ConnectDetach(int c)                          { return -1; }
int  MsgSend(int c,const void*s,int sb,void*r,int rb)       { return -1; }
int  MsgReceive(int c,void*m,int b,void*i)         { return -1; }
int  MsgReply(int r,int st,const void*m,int b)     { return -1; }
