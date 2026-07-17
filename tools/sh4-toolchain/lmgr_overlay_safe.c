/* ============================================================================
 * lmgr_overlay_safe.c -- SMALL cooperative overlay + CLEAN TEARDOWN test.
 *
 * Context: 2026-07-06 the full-screen screentest DID render (color bars) but
 * exited WITHOUT releasing its displayable. The compositor kept scanning our
 * freed framebuffer -> CRT snow that survived a soft power-off (hard cycle to
 * recover). Root cause = dirty exit, NOT the overlay itself.
 *
 * This build proves the fix: register a SMALL 480x240 box (no full-screen fight
 * with PCM3Root), draw a static image, Show it ~5s, then tear down CLEANLY:
 *   Unregister(displayable) -> settle one compositor pass -> close(fd) -> exit.
 * Unregister makes the compositor drop our surface WHILE WE ARE STILL ALIVE, so
 * when the process exits and frees the surface, nothing is scanning it.
 *
 * Expected on glass: small teal box w/ white border, green cross, red corner
 * marker for ~5s, PCM UI still visible around it; then it vanishes and the
 * normal PCM3Root screen returns with NO snow, NO freeze, NO hard reset needed.
 *
 * Unregister devctl = 0x80040501 (class5 code1, msg={cid}, 4B) -- read from the
 * PCM3Browser lmgr client (D:\PCM\lmgr_details.txt, fn @0x080a369c).
 * ==========================================================================*/
extern int  open(const char*, int, ...);
extern int  devctl(int, int, void*, unsigned, int*);
extern int  write(int, const void*, int);
extern int  close(int);
extern unsigned sleep(unsigned);
extern int  gf_dev_attach(void*, const char*, void*);
extern int  gf_surface_attach_by_sid(void*, void*, unsigned);
extern int  gf_context_create(void*);
extern int  gf_context_set_surface(void*, void*);
extern int  gf_draw_begin(void*);
extern int  gf_context_set_fgcolor(void*, unsigned);
extern int  gf_draw_rect(void*, int, int, int, int);
extern int  gf_draw_finish(void*);
extern int  gf_draw_end(void*);

#define O_RDWR          2
#define LMGR_CONNECT    0xc00c0506u
#define LMGR_REGISTER   0xc0140500u
#define LMGR_GETVFB     0xc0100503u
#define LMGR_UPDATE     0x80040504u
#define LMGR_SHOW       0x800c0505u
#define LMGR_UNREGISTER 0x80040501u   /* class5 code1, msg={cid}, 4B -- the snow-killer */

#define OW 480
#define OH 240

static void put(const char*s){int n=0;while(s[n])n++;write(1,s,n);}
static void hx(unsigned v){char b[11];const char*h="0123456789abcdef";int i;
  b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(1,b,10);}

static void *G;
static void fill(unsigned c,int x1,int y1,int x2,int y2){gf_context_set_fgcolor(G,c);gf_draw_rect(G,x1,y1,x2,y2);}

int main(int argc,char**argv){
  unsigned cmsg[3],rmsg[5],gmsg[4],umsg[1],smsg[3];
  unsigned dev=0,surf=0,ctx=0,ureg;
  unsigned char devinfo[256];
  int fd,rc,i,cid=0x5001;

  put("== lmgr_overlay_safe: small overlay + CLEAN TEARDOWN ==\n");
  for(i=0;i<256;i++)devinfo[i]=0;
  rc=gf_dev_attach(&dev,0,devinfo); put("gf_dev_attach rc="); hx((unsigned)rc); put("\n");
  fd=open("/dev/layermanager",O_RDWR); put("open fd="); hx((unsigned)fd); put("\n");
  if(fd<0){put(">>> OPEN FAILED\n");return 1;}
  cmsg[0]=cmsg[1]=cmsg[2]=0; devctl(fd,LMGR_CONNECT,cmsg,sizeof cmsg,0);
  put("connect reply=["); hx(cmsg[0]); put(" "); hx(cmsg[1]); put("]\n");

  /* register ONE small size -- deliberately NOT full-screen (no PCM3Root fight) */
  rmsg[0]=cid;rmsg[1]=OW;rmsg[2]=OH;rmsg[3]=0;rmsg[4]=0;
  rc=devctl(fd,LMGR_REGISTER,rmsg,sizeof rmsg,0);
  put("register 480x240 result="); hx(rmsg[4]); put("\n");
  if(!(rc==0&&rmsg[4])){ put(">>> register REJECTED -- closing cleanly\n"); close(fd); return 2; }

  gmsg[0]=(unsigned)cid;gmsg[1]=gmsg[2]=gmsg[3]=0; rc=devctl(fd,LMGR_GETVFB,gmsg,sizeof gmsg,0);
  put("getvfb sid="); hx(gmsg[1]); put("\n");
  if(!(rc==0&&gmsg[1])){ put(">>> no framebuffer -- unregister+close\n");
    ureg=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&ureg,4,0); close(fd); return 3; }

  gf_surface_attach_by_sid(&surf,(void*)dev,gmsg[1]);
  gf_context_create(&ctx); G=(void*)ctx;
  gf_context_set_surface((void*)ctx,(void*)surf);

  /* simple, unmistakable, OPAQUE (0xff alpha) box */
  gf_draw_begin((void*)ctx);
  fill(0xff008080,0,0,OW-1,OH-1);                                   /* teal fill        */
  fill(0xffffffff,0,0,OW-1,4);   fill(0xffffffff,0,OH-5,OW-1,OH-1); /* top/bottom border*/
  fill(0xffffffff,0,0,4,OH-1);   fill(0xffffffff,OW-5,0,OW-1,OH-1); /* left/right border*/
  fill(0xff00ff00,OW/2-40,OH/2-3,OW/2+40,OH/2+3);                   /* green cross  H   */
  fill(0xff00ff00,OW/2-3,OH/2-40,OW/2+3,OH/2+40);                   /* green cross  V   */
  fill(0xffff0000,8,8,40,40);                                      /* red corner mark  */
  gf_draw_finish((void*)ctx); gf_draw_end((void*)ctx);
  umsg[0]=(unsigned)cid; devctl(fd,LMGR_UPDATE,umsg,sizeof umsg,0);

  /* SHOW it (the compositing trigger) */
  smsg[0]=0; smsg[1]=1; smsg[2]=(unsigned)cid;
  rc=devctl(fd,LMGR_SHOW,smsg,12,0); put("show rc="); hx((unsigned)rc); put("\n");
  put(">>> overlay UP (480x240). Holding 5s -- WATCH: teal box, white border,\n");
  put(">>> green cross, red corner; PCM UI should stay visible around it.\n");
  sleep(5);

  /* ================= CLEAN TEARDOWN (the whole point) ================= */
  put(">>> teardown: unregister displayable...\n");
  ureg=(unsigned)cid; rc=devctl(fd,LMGR_UNREGISTER,&ureg,4,0);
  put("unregister rc="); hx((unsigned)rc); put("\n");
  sleep(2);                 /* let the compositor run a pass WITHOUT our displayable */
  close(fd);                /* OS-level component disconnect                        */
  put(">>> CLEAN TEARDOWN DONE -- expect normal PCM3Root, NO snow, NO freeze.\n");
  put("== overlay_safe done ==\n");
  return 0;
}
