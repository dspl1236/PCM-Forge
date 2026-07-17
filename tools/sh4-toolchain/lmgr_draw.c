/* ============================================================================
 * lmgr_draw.c  --  PCM 3.1: draw a solid rectangle on our own layer (QNX SH4)
 * Extends the proven probe: connect -> register -> getvfb (all confirmed on the
 * Cayenne), then attaches a libgf surface to the returned sid and paints a
 * magenta rectangle, then lmgrUpdateVfb to composite it over PCM3Root.
 * gf_* call order mirrors showScreen + the layermanager dummy-splash draw path.
 * ==========================================================================*/
extern int  open(const char *path, int oflag, ...);
extern int  devctl(int fd, int dcmd, void *data, unsigned nbytes, int *info);
extern int  write(int fd, const void *buf, int n);
extern int  close(int fd);
extern unsigned sleep(unsigned sec);

/* libgf (resolved at runtime from libgf.so.1 on the unit) */
extern int  gf_dev_attach(void *dev, const char *name, void *info);
extern int  gf_surface_attach_by_sid(void *surf, void *dev, unsigned sid);
extern int  gf_context_create(void *ctx);
extern int  gf_context_set_surface(void *ctx, void *surf);
extern int  gf_draw_begin(void *ctx);
extern int  gf_context_set_fgcolor(void *ctx, unsigned color);
extern int  gf_draw_rect(void *ctx, int x1, int y1, int x2, int y2);
extern int  gf_draw_finish(void *ctx);
extern int  gf_draw_end(void *ctx);

#define O_RDWR        2
#define LMGR_CONNECT  0xc00c0506u
#define LMGR_REGISTER 0xc0140500u
#define LMGR_GETVFB   0xc0100503u
#define LMGR_UPDATE   0x80040504u   /* class 5, code 4, 4-byte, TO-only */

#define CID   0x5000u
#define W     480
#define H     240
#define MAGENTA 0x00FF00FFu

static void put(const char *s){ int n=0; while(s[n])n++; write(1,s,n); }
static void hx(unsigned v){ char b[11]; const char*h="0123456789abcdef"; int i;
    b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0; write(1,b,10); }

int main(int argc, char **argv)
{
    unsigned cmsg[3], rmsg[5], gmsg[4], umsg[1];
    unsigned dev, surf, ctx;          /* gf handles (opaque) */
    unsigned char devinfo[256];       /* gf_dev_info_t buffer (filled by attach) */
    int fd, rc, i;

    put("== lmgr_draw: cross-build RAN ==\n");

    /* graphics device */
    dev = 0;
    for (i=0;i<256;i++) devinfo[i]=0;
    rc = gf_dev_attach(&dev, 0, devinfo);
    put("gf_dev_attach rc="); hx((unsigned)rc); put("\n");
    if (rc != 0) { put(">>> gf_dev_attach failed (libgf/crt-init issue)\n"); }

    fd = open("/dev/layermanager", O_RDWR);
    put("open fd="); hx((unsigned)fd); put("\n");
    if (fd < 0) { put(">>> OPEN FAILED\n"); return 1; }

    cmsg[0]=cmsg[1]=cmsg[2]=0;
    rc = devctl(fd, LMGR_CONNECT, cmsg, sizeof cmsg, 0);
    put("connect rc="); hx((unsigned)rc); put(" reply=["); hx(cmsg[0]); put(" "); hx(cmsg[1]); put("]\n");

    rmsg[0]=CID; rmsg[1]=W; rmsg[2]=H; rmsg[3]=0; rmsg[4]=0;
    rc = devctl(fd, LMGR_REGISTER, rmsg, sizeof rmsg, 0);
    put("register rc="); hx((unsigned)rc); put(" result="); hx(rmsg[4]); put("\n");
    if (!(rc==0 && rmsg[4]!=0)) { put(">>> no layer / register failed\n"); close(fd); return 2; }

    gmsg[0]=CID; gmsg[1]=gmsg[2]=gmsg[3]=0;
    rc = devctl(fd, LMGR_GETVFB, gmsg, sizeof gmsg, 0);
    put("getvfb rc="); hx((unsigned)rc); put(" sid="); hx(gmsg[1]); put("\n");
    if (!(rc==0 && gmsg[1]!=0)) { put(">>> no framebuffer\n"); close(fd); return 3; }

    /* attach a gf surface to our VFB sid and paint */
    surf = 0;
    rc = gf_surface_attach_by_sid(&surf, (void*)dev, gmsg[1]);
    put("surface_attach_by_sid rc="); hx((unsigned)rc); put(" surf="); hx(surf); put("\n");

    ctx = 0;
    gf_context_create(&ctx);
    gf_context_set_surface((void*)ctx, (void*)surf);
    rc = gf_draw_begin((void*)ctx);
    put("draw_begin rc="); hx((unsigned)rc); put("\n");
    gf_context_set_fgcolor((void*)ctx, MAGENTA);
    gf_draw_rect((void*)ctx, 0, 0, W-1, H-1);
    gf_draw_finish((void*)ctx);
    gf_draw_end((void*)ctx);
    put("painted rect\n");

    /* push to the compositor */
    umsg[0]=CID;
    rc = devctl(fd, LMGR_UPDATE, umsg, sizeof umsg, 0);
    put("updatevfb rc="); hx((unsigned)rc); put("\n");

    put(">>> LOOK AT THE SCREEN -- magenta box for ~40s\n");
    sleep(40);                        /* keep the layer up so you can see it */

    close(fd);
    put("== draw done ==\n");
    return 0;
}
