/* Link-time STUB, part 2: the libc.so.2 functions that need libc initialised
 * first -- stdio, heap, strings, environment -- plus the start-up calls that
 * crt_libc.S makes. build.sh builds libc.so.2 from stub_libc.c + this file only
 * for programs that use them, so the freestanding tools link exactly as before
 * (and the shipped ones still rebuild byte for byte). Like stub_libc.c, only
 * the names matter: ldqnx.so.2 binds them to the real libc.so.2 on the unit.
 * Add a line here for any other libc function your program calls. */
void _init_libc(int a, char **v, char **e, void *x) { }
void __set_fpscr(unsigned v)                       { }
int  atexit(void (*f)(void))                       { return 0; }
void exit(int c)                                   { for (;;) ; }
int  printf(const char *f, ...)                    { return 0; }
int  snprintf(char *b, unsigned n, const char *f, ...) { return 0; }
int  puts(const char *s)                           { return 0; }
int  fflush(void *fp)                              { return 0; }
void *malloc(unsigned n)                           { return 0; }
void *calloc(unsigned n, unsigned s)               { return 0; }
void *realloc(void *p, unsigned n)                 { return 0; }
void free(void *p)                                 { }
void *memset(void *d, int c, unsigned n)           { return d; }
void *memcpy(void *d, const void *s, unsigned n)   { return d; }
unsigned strlen(const char *s)                     { return 0; }
int  strcmp(const char *a, const char *b)          { return 0; }
char *getenv(const char *n)                        { return 0; }
