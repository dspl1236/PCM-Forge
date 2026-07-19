/* Link-time STUB for QNX libgf.so.1 -- names/SONAME only; ldqnx.so.2 binds
 * these to the real libgf.so.1 on the PCM at load time. */
int gf_dev_attach(void *d, const char *n, void *i)       { return -1; }
int gf_surface_attach_by_sid(void *s, void *d, unsigned x){ return -1; }
int gf_context_create(void *c)                           { return -1; }
int gf_context_set_surface(void *c, void *s)             { return -1; }
int gf_draw_begin(void *c)                               { return -1; }
int gf_context_set_fgcolor(void *c, unsigned col)        { return -1; }
int gf_draw_rect(void *c, int a, int b, int e, int f)    { return -1; }
int gf_draw_finish(void *c)                              { return -1; }
int gf_draw_end(void *c)                                 { return -1; }
/* ---- added for showimg: image-surface wrap + blit + frees ---- */
int gf_surface_attach(void *s, void *d, unsigned w, unsigned h, int st, int f, void *pal, void *ptr, unsigned fl) { return -1; }
int gf_draw_blit2(void *c, void *sr, void *ds, int a, int b, int e, int g, int i, int j) { return -1; }
int gf_surface_free(void *s)                             { return -1; }
int gf_context_free(void *c)                             { return -1; }
