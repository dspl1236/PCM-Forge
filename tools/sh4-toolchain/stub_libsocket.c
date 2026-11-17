/* Link-time STUB for QNX libsocket.so.2 -- only the symbol names/SONAME matter;
 * ldqnx.so.2 binds these to the real libsocket.so.2 on the PCM at load time. */
void *gethostbyname(const char *n)                 { return 0; }
int   socket(int d, int t, int p)                  { return -1; }
int   connect(int s, const void *a, int l)         { return -1; }
