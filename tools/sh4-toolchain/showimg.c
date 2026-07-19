/* ============================================================================
 * showimg.c -- PCM 3.1 raw-image blitter (freestanding SH4/QNX cross-build).
 *
 * Reads a raw "PFIM" image blob from USB, wraps its pixels as a gf SOURCE
 * surface (gf_surface_attach), blits it centered onto the layermanager VFB
 * DEST surface (gf_draw_blit2), UPDATE+SHOW, holds ~20s, then does the proven
 * anti-snow clean teardown (UNREGISTER -> settle -> close).
 *
 * The ENTIRE front half (dev attach -> connect -> size-probe register ->
 * getvfb -> attach_by_sid -> context_create -> set_surface) is verbatim
 * app_oil.c / draw.c -- the only new code is the blit tail. Blob gf_format
 * lives IN THE HEADER, so pixel format is a re-bake (no recompile): change
 * img.bin's format u32 to try 0x1420/0x1620/0x1520/0x1018 etc.
 *
 * FREESTANDING: no libc startup, no malloc, no stdio. crt.S provides
 * _start(argc,argv)->main. All libc + gf symbols are extern-declared here and
 * bound to the on-car libc.so.2 / libgf.so.1 by ldqnx.so.2 at load (link
 * against the SONAME-only stub libs). The pixel buffer is a static BSS array.
 *
 * Blob format (little-endian header, then pixels):
 *   u32 magic  = 0x4d494650 ("PFIM")
 *   u32 width
 *   u32 height
 *   u32 gf_format          (travels in the header -> re-bakeable)
 *   u32 stride  (0 => width*bpp)
 *   u32 bpp                (BYTES per pixel; stride==0 => width*bpp)
 *   ... pixel bytes ...
 * Header is 24 bytes. Search: argv[1] override, then /fs/usb0/img.bin,
 * /fs/usb1/img.bin, /fs/usb/img.bin.
 * ==========================================================================*/

/* ---- libc (bound to on-car libc.so.2 at load; link vs stub) ---- */
extern int  open(const char*, int, ...);
extern int  read(int, void*, unsigned);
extern int  write(int, const void*, int);
extern int  close(int);
extern int  devctl(int, int, void*, unsigned, int*);
extern unsigned sleep(unsigned);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
extern void _exit(int);

/* ---- gf (bound to on-car libgf.so.1 at load; link vs stub) ---- */
extern int  gf_dev_attach(void*, const char*, void*);
extern int  gf_surface_attach_by_sid(void*, void*, unsigned);
extern int  gf_surface_attach(void*, void*, unsigned, unsigned, int, int, void*, void*, unsigned);
extern int  gf_context_create(void*);
extern int  gf_context_set_surface(void*, void*);
extern int  gf_context_set_fgcolor(void*, unsigned);
extern int  gf_draw_begin(void*);
extern int  gf_draw_rect(void*, int, int, int, int);
extern int  gf_draw_blit2(void*, void*, void*, int, int, int, int, int, int);
extern int  gf_draw_finish(void*);
extern int  gf_draw_end(void*);
extern int  gf_surface_free(void*);
extern int  gf_context_free(void*);

#define SIGILL   4
#define SIGFPE   8
#define SIGBUS  10
#define SIGSEGV 11

#define O_RDONLY        0
#define O_WRONLY        1
#define O_RDWR          2
#define O_APPEND        0x008
#define O_CREAT         0x100

#define LMGR_CONNECT    0xc00c0506u
#define LMGR_REGISTER   0xc0140500u
#define LMGR_GETVFB     0xc0100503u
#define LMGR_UPDATE     0x80040504u
#define LMGR_SHOW       0x800c0505u
#define LMGR_UNREGISTER 0x80040501u

#define PFIM_MAGIC 0x4d494650u
#define HDR_BYTES  24
#define MAX_W      800
#define MAX_H      480
#define MAX_BPP    4
#define HOLD_SECS  20

/* whole blob (header + up to 800x480x4 pixels) lives in BSS. aligned so the
   pixel pointer (g_blob+HDR_BYTES) is >=4-aligned for the gf source surface. */
static unsigned char g_blob[HDR_BYTES + (MAX_W*MAX_H*MAX_BPP) + 64]
    __attribute__((aligned(16)));

/* ---- combined logging: fd 1 AND the USB showimg.txt (opened once) ---- */
static int g_log = -1;
static int slen(const char*s){ int n=0; while(s[n]) n++; return n; }
static void lg(const char*s){ int n=slen(s); write(1,s,n); if(g_log>=0) write(g_log,s,n); }
static void lghx(unsigned v){ char b[11]; const char*h="0123456789abcdef"; int i;
  b[0]='0'; b[1]='x'; for(i=0;i<8;i++) b[2+i]=h[(v>>((7-i)*4))&0xf]; b[10]=0; lg(b); }
static void lgdec(unsigned v){ char b[12]; int i=11; b[11]=0;
  if(v==0){ lg("0"); return; } while(v && i>0){ b[--i]='0'+(v%10); v/=10; } lg(b+i); }
static void openlog(void){
  static const char*P[3]={"/fs/usb0/showimg.txt","/fs/usb1/showimg.txt","/fs/usb/showimg.txt"};
  int i,f; for(i=0;i<3;i++){ f=open(P[i],O_WRONLY|O_CREAT|O_APPEND,0666); if(f>=0){ g_log=f; return; } }
}

/* little-endian u32 read -- endianness/alignment safe (works byte-wise). */
static unsigned rd32(const unsigned char*p){
  return (unsigned)p[0] | ((unsigned)p[1]<<8) | ((unsigned)p[2]<<16) | ((unsigned)p[3]<<24);
}

/* anti-snow: a crash while our displayable is SHOWN must still UNREGISTER so the
   compositor stops scanning our surface (else persistent CRT-snow). */
static int g_fd=-1; static unsigned g_cid=0; static int g_reg=0;
static void onfault(int sig){
  (void)sig;
  if(g_reg && g_fd>=0){ unsigned u=g_cid; devctl(g_fd,LMGR_UNREGISTER,&u,4,0); }
  _exit(3);
}

int main(int argc,char**argv){
  unsigned cmsg[3],rmsg[5],gmsg[4],umsg[1],smsg[3],ureg;
  unsigned dev=0,surf=0,ctx=0,imgsurf=0;
  unsigned char devinfo[256];
  int fd,rc,i,bf,total,r,cid=0x6001,W=0,H=0;
  unsigned magic,imgW,imgH,fmt,stride,bpp,minneed;
  unsigned char *pixels;
  int dx,dy;
  /* COMPONENT-LAYER sizes only (proven-stable; never probe full 800x480 or we
     brawl with PCM3Root's layer 0). Same probe list as app_oil/overlay_safe. */
  static const int SZ[][2]={{480,240},{400,240},{320,240}};

  openlog();
  lg("== showimg: raw PFIM blitter ==\n");

  /* ---------- locate + slurp the blob ---------- */
  bf=-1;
  if(argc>1 && argv[1] && argv[1][0]){ bf=open(argv[1],O_RDONLY,0);
    lg("open argv1="); lghx((unsigned)bf); lg(" ["); lg(argv[1]); lg("]\n"); }
  if(bf<0){
    static const char*BP[3]={"/fs/usb0/img.bin","/fs/usb1/img.bin","/fs/usb/img.bin"};
    for(i=0;i<3;i++){ bf=open(BP[i],O_RDONLY,0);
      if(bf>=0){ lg("open blob="); lg(BP[i]); lg("\n"); break; } }
  }
  if(bf<0){ lg(">>> no img.bin found\n"); return 1; }

  total=0;
  for(;;){
    r=read(bf, g_blob+total, (unsigned)((int)sizeof(g_blob)-total));
    if(r<=0) break;
    total+=r;
    if(total>=(int)sizeof(g_blob)) break;
  }
  close(bf);
  lg("read bytes="); lgdec((unsigned)total); lg("\n");

  /* ---------- parse + validate header ---------- */
  if(total<HDR_BYTES){ lg(">>> short read (no header)\n"); return 1; }
  magic =rd32(g_blob+0);
  imgW  =rd32(g_blob+4);
  imgH  =rd32(g_blob+8);
  fmt   =rd32(g_blob+12);
  stride=rd32(g_blob+16);
  bpp   =rd32(g_blob+20);
  lg("magic="); lghx(magic); lg(" w="); lgdec(imgW); lg(" h="); lgdec(imgH);
  lg(" fmt="); lghx(fmt); lg(" stride="); lgdec(stride); lg(" bpp="); lgdec(bpp); lg("\n");

  if(magic!=PFIM_MAGIC){ lg(">>> bad magic (not PFIM)\n"); return 1; }
  if(imgW==0||imgH==0||imgW>MAX_W||imgH>MAX_H){ lg(">>> bad/oversized dimensions\n"); return 1; }
  if(bpp==0||bpp>MAX_BPP){ lg(">>> bad bpp\n"); return 1; }
  if(stride==0) stride=imgW*bpp;
  if(stride<imgW*bpp || stride>0x10000u){ lg(">>> bad stride\n"); return 1; }
  minneed=stride*(imgH-1)+imgW*bpp;                 /* bytes the surface will touch */
  if((unsigned)HDR_BYTES+minneed>(unsigned)total){ lg(">>> truncated pixel data\n"); return 1; }
  pixels=g_blob+HDR_BYTES;

  /* ---------- gf device + layermanager front half (verbatim app_oil) ---------- */
  for(i=0;i<256;i++) devinfo[i]=0;
  rc=gf_dev_attach(&dev,0,devinfo); lg("gf_dev_attach rc="); lghx((unsigned)rc); lg("\n");

  fd=open("/dev/layermanager",O_RDWR); lg("open lmgr fd="); lghx((unsigned)fd); lg("\n");
  if(fd<0){ lg(">>> OPEN FAILED\n"); return 1; }
  cmsg[0]=cmsg[1]=cmsg[2]=0; devctl(fd,LMGR_CONNECT,cmsg,sizeof cmsg,0);
  lg("connect reply=["); lghx(cmsg[0]); lg(" "); lghx(cmsg[1]); lg("]\n");

  for(i=0;i<3;i++){
    rmsg[0]=cid; rmsg[1]=SZ[i][0]; rmsg[2]=SZ[i][1]; rmsg[3]=0; rmsg[4]=0;
    rc=devctl(fd,LMGR_REGISTER,rmsg,sizeof rmsg,0);
    lg("  reg "); lgdec((unsigned)SZ[i][0]); lg("x"); lgdec((unsigned)SZ[i][1]);
    lg(" -> "); lghx(rmsg[4]);
    if(rc==0&&rmsg[4]){ W=SZ[i][0]; H=SZ[i][1]; lg(" GRANTED\n"); break; }
    { unsigned u=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&u,4,0); }   /* release a nacked reg */
    lg("\n");
  }
  if(!W){ lg(">>> no size granted\n"); close(fd); return 2; }

  /* arm the anti-snow fault handler now that a displayable is registered */
  g_fd=fd; g_cid=(unsigned)cid; g_reg=1;
  signal(SIGSEGV,onfault); signal(SIGBUS,onfault); signal(SIGFPE,onfault); signal(SIGILL,onfault);

  gmsg[0]=(unsigned)cid; gmsg[1]=gmsg[2]=gmsg[3]=0;
  rc=devctl(fd,LMGR_GETVFB,gmsg,sizeof gmsg,0);
  lg("getvfb sid="); lghx(gmsg[1]); lg("\n");
  if(!(rc==0&&gmsg[1])){ lg(">>> no framebuffer\n");
    ureg=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&ureg,4,0); close(fd); return 3; }

  /* DEST = VFB surface bound to a context */
  gf_surface_attach_by_sid(&surf,(void*)dev,gmsg[1]);
  gf_context_create(&ctx);
  gf_context_set_surface((void*)ctx,(void*)surf);

  /* SRC = our USB pixels wrapped as a gf surface (9-arg attach: palette/phys=0,
     ptr=pixels, flags=0). stride & fmt come straight from the PFIM header. */
  rc=gf_surface_attach(&imgsurf,(void*)dev,imgW,imgH,(int)stride,(int)fmt,0,(void*)pixels,0);
  lg("surface_attach rc="); lghx((unsigned)rc); lg("\n");
  if(rc!=0){ lg(">>> surface_attach failed\n");
    ureg=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&ureg,4,0); close(fd); return 4; }

  /* centered dest top-left, clamped >=0 */
  dx=((int)W-(int)imgW)/2; if(dx<0) dx=0;
  dy=((int)H-(int)imgH)/2; if(dy<0) dy=0;

  /* ---------- the blit (one clean composite) ---------- */
  gf_draw_begin((void*)ctx);
  /* letterbox: paint the whole layer black so borders around a smaller image
     are clean (proven gf_context_set_fgcolor + gf_draw_rect primitives). */
  gf_context_set_fgcolor((void*)ctx,0xff000000u);
  gf_draw_rect((void*)ctx,0,0,W-1,H-1);
  /* dst=0 => the context's bound VFB surface. src extent = imgW-1,imgH-1 (proven
     safe under both extent/inclusive-corner semantics). dst top-left = dx,dy. */
  gf_draw_blit2((void*)ctx,(void*)imgsurf,0, 0,0, (int)imgW-1,(int)imgH-1, dx,dy);
  gf_draw_finish((void*)ctx);
  gf_draw_end((void*)ctx);

  /* pixels are now copied into the VFB -> the source surface is done */
  gf_surface_free((void*)imgsurf); imgsurf=0;

  umsg[0]=(unsigned)cid; devctl(fd,LMGR_UPDATE,umsg,sizeof umsg,0);
  smsg[0]=0; smsg[1]=1; smsg[2]=(unsigned)cid;
  rc=devctl(fd,LMGR_SHOW,smsg,12,0); lg("show rc="); lghx((unsigned)rc); lg("\n");
  lg(">>> image up "); lgdec(imgW); lg("x"); lgdec(imgH);
  lg(" at dx="); lgdec((unsigned)dx); lg(" dy="); lgdec((unsigned)dy);
  lg(" on layer "); lgdec((unsigned)W); lg("x"); lgdec((unsigned)H); lg("\n");

  /* ---------- hold: ONE clean composite, no per-frame churn ---------- */
  sleep(HOLD_SECS);

  /* ---------- CLEAN TEARDOWN (anti-snow ordering) ---------- */
  lg(">>> teardown: unregister...\n");
  ureg=(unsigned)cid; rc=devctl(fd,LMGR_UNREGISTER,&ureg,4,0);
  g_reg=0;
  lg("unregister rc="); lghx((unsigned)rc); lg("\n");
  sleep(2);
  close(fd);

  /* final gf cleanup (layer already released; local handles only) */
  gf_context_free((void*)ctx);
  gf_surface_free((void*)surf);

  lg(">>> done -- press NAV/CAR to restore OEM screen. NO snow expected.\n");
  lg("== showimg done ==\n");
  if(g_log>=0) close(g_log);
  return 0;
}
