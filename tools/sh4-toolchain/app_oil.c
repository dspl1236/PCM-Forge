/* ============================================================================
 * app_oil.c -- PCM 3.1 "Oil Service" overlay app (first real UI on the glass).
 *
 * Forks the PROVEN overlay_safe.c lifecycle and adds a real UI drawn ENTIRELY
 * from the two primitives already proven on hardware: gf_context_set_fgcolor +
 * gf_draw_rect. NO new gf/libc symbols -> links & runs exactly like the binary
 * that already worked. Text = self-shipped 8x16 bitmap font (font8x16.h), each
 * set pixel plotted as a scale*scale rect. Widgets (panel/button/bar/droplet)
 * are all rect compositions. Layout adapts to whatever layer size is granted.
 *
 * Lifecycle: connect -> register(size probe) -> getvfb -> draw UI -> update ->
 * SHOW -> live countdown (redraw+update each second) -> CLEAN TEARDOWN
 * (unregister 0x80040501 -> settle a compositor pass -> close -> exit).
 * The clean teardown is what prevents the dirty-exit CRT-snow; keep its order.
 *
 * EXIT this round is timer-based (counts down, then releases). Returning to the
 * OEM screen after release is a NAV/CAR press (event-driven HMI redraw) -- an
 * on-screen tap-to-exit needs the unsolved input subsystem and is NOT wired.
 * ==========================================================================*/
#include "font8x16.h"

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

typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
extern void _exit(int);
#define SIGILL   4
#define SIGFPE   8
#define SIGBUS  10
#define SIGSEGV 11

#define O_RDWR          2
#define O_WRONLY        1
#define O_CREAT         0x100
#define O_APPEND        0x008
#define LMGR_CONNECT    0xc00c0506u
#define LMGR_REGISTER   0xc0140500u
#define LMGR_GETVFB     0xc0100503u
#define LMGR_UPDATE     0x80040504u
#define LMGR_SHOW       0x800c0505u
#define LMGR_UNREGISTER 0x80040501u

#define HOLD_SECS 25

/* ---- PCM-Forge palette (opaque ARGB) -- gold accent on near-black, per docs/index.html ---- */
#define C_BG       0xff0a0a0cu   /* --bg      */
#define C_BAR_BG   0xff131318u   /* --surface */
#define C_LINE     0xff2a2a35u   /* --border  */
#define C_BRAND    0xffc8a44eu   /* --accent (gold) */
#define C_ACCENT   0xffc8a44eu   /* --accent (gold) */
#define C_MUTED    0xff8888a0u   /* --text2   */
#define C_LABEL    0xff8888a0u   /* --text2   */
#define C_BIG      0xffe8e8edu   /* --text    */
#define C_BAR_ON   0xff4eca7au   /* --green   */
#define C_BAR_OFF  0xff2a2a35u   /* --border  */
#define C_RST_BG   0xff131318u   /* reset = gold outline (btn-outline) */
#define C_RST_BD   0xffc8a44eu
#define C_RST_TX   0xffc8a44eu
#define C_EXT_BG   0xff131318u   /* exit = muted outline */
#define C_EXT_BD   0xff2a2a35u
#define C_EXT_TX   0xff8888a0u
#define C_FOOT_BG  0xff131318u   /* --surface */

static int  slen(const char*s){int n=0;while(s[n])n++;return n;}
static void put(const char*s){write(1,s,slen(s));}
static void hx(unsigned v){char b[11];const char*h="0123456789abcdef";int i;
  b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(1,b,10);}

/* best-effort persistent service log on the USB (proves on-car file-append plumbing;
   VIN/mileage/reset-result get filled in once those reads/actions are wired). */
static void svc_log(const char*rec){
  static const char*paths[3]={"/fs/usb0/service_log.txt","/fs/usb1/service_log.txt","/fs/usb/service_log.txt"};
  int i,lf;
  for(i=0;i<3;i++){ lf=open(paths[i],O_WRONLY|O_CREAT|O_APPEND,0666);
    if(lf>=0){ write(lf,rec,slen(rec)); close(lf); return; } }
}

static void *G;
static int W,H,footY,footH,u,scLbl,scBig,scBtn,scFoot;   /* geometry, set after size probe */

/* anti-snow: a crash while our displayable is SHOWN must still unregister so the
   compositor stops scanning our surface. This fault handler converts any
   SIGSEGV/BUS/FPE/ILL into a clean unregister + exit instead of persistent CRT-snow. */
static int g_fd=-1; static unsigned g_cid=0; static int g_reg=0;
static void onfault(int sig){
  (void)sig;
  if(g_reg && g_fd>=0){ unsigned u=g_cid; devctl(g_fd,LMGR_UNREGISTER,&u,4,0); }
  _exit(3);
}

/* every rect goes through here: clamps to the surface so no negative/out-of-bounds
   coordinate can reach gf_draw_rect (critical on the post-SHOW hot path). */
static void crect(int x1,int y1,int x2,int y2){
  if(x1<0)x1=0; if(y1<0)y1=0; if(x2>W-1)x2=W-1; if(y2>H-1)y2=H-1;
  if(x1<=x2 && y1<=y2) gf_draw_rect(G,x1,y1,x2,y2);
}
static void fill(unsigned c,int x1,int y1,int x2,int y2){
  gf_context_set_fgcolor(G,c); crect(x1,y1,x2,y2);
}
static void border(unsigned c,int x,int y,int w,int h,int t){
  fill(c,x,y,x+w-1,y+t-1); fill(c,x,y+h-t,x+w-1,y+h-1);
  fill(c,x,y,x+t-1,y+h-1); fill(c,x+w-t,y,x+w-1,y+h-1);
}

/* ---- bitmap-font text (each set pixel -> scale*scale rect) ---- */
static void glyph(int gx,int gy,int sc,unsigned col,int code){
  const unsigned char *g; int row,cx;
  if(code<FONT_FIRST||code>FONT_LAST)code=FONT_FIRST;
  g=FONT8X16[code-FONT_FIRST];
  gf_context_set_fgcolor(G,col);
  for(row=0;row<FONT_H;row++){
    unsigned bits=g[row];
    for(cx=0;cx<FONT_W;cx++){
      if(bits&(0x80u>>cx)){
        int px=gx+cx*sc, py=gy+row*sc;
        crect(px,py,px+sc-1,py+sc-1);
      }
    }
  }
}
static int adv(int sc){ return (FONT_W+1)*sc; }              /* per-char advance */
static int text_w(int sc,const char*s){int n=0;while(s[n])n++;return n*adv(sc);}
static void text(int x,int y,int sc,unsigned col,const char*s){
  int cx=x;
  while(*s){ if(*s!=' ') glyph(cx,y,sc,col,(unsigned char)*s); cx+=adv(sc); s++; }
}
static void text_c(int cx,int y,int sc,unsigned col,const char*s){ /* centered on cx */
  text(cx-text_w(sc,s)/2,y,sc,col,s);
}

/* ---- droplet emblem from rects (disc + triangular spike) ---- */
static int isqrt(int v){int r=0;while((r+1)*(r+1)<=v)r++;return r;}
static void droplet(int cx,int cy,int r,unsigned col){
  int y,hw;
  gf_context_set_fgcolor(G,col);
  for(y=-r;y<=r;y++){ hw=isqrt(r*r-y*y); crect(cx-hw,cy+y,cx+hw,cy+y); }
  for(y=0;y<2*r;y++){ hw=y/2; crect(cx-hw,(cy-2*r)+y,cx+hw,(cy-2*r)+y); }
}

static void button(int x,int y,int w,int h,unsigned bg,unsigned bd,unsigned tx,int sc,const char*label){
  fill(bg,x,y,x+w-1,y+h-1);
  border(bd,x,y,w,h,2);
  text_c(x+w/2, y+(h-FONT_H*sc)/2, sc, tx, label);
}

static const char *FOOT1="AUTO-RETURNS SHORTLY  -  OR PRESS NAV / CAR";

int main(int argc,char**argv){
  unsigned cmsg[3],rmsg[5],gmsg[4],umsg[1],smsg[3],ureg;
  unsigned dev=0,surf=0,ctx=0;
  unsigned char devinfo[256];
  int fd,rc,i,cid=0x6001,w=0,h=0;
  /* COMPONENT-LAYER sizes only. 480x240 is the proven-stable size (overlay_safe):
     it sits on layer 1 and does NOT fight PCM3Root's full-screen layer 0. Taking
     800x480 = brawling with PCM3Root -> the oil/media/snow rotation. Never probe full. */
  static const int SZ[][2]={{480,240},{400,240},{320,240}};

  put("== app_oil: oil-service overlay ==\n");
  for(i=0;i<256;i++)devinfo[i]=0;
  rc=gf_dev_attach(&dev,0,devinfo); put("gf_dev_attach rc="); hx((unsigned)rc); put("\n");
  fd=open("/dev/layermanager",O_RDWR); put("open fd="); hx((unsigned)fd); put("\n");
  if(fd<0){put(">>> OPEN FAILED\n");return 1;}
  cmsg[0]=cmsg[1]=cmsg[2]=0; devctl(fd,LMGR_CONNECT,cmsg,sizeof cmsg,0);
  put("connect reply=["); hx(cmsg[0]); put(" "); hx(cmsg[1]); put("]\n");

  for(i=0;i<3;i++){
    rmsg[0]=cid;rmsg[1]=SZ[i][0];rmsg[2]=SZ[i][1];rmsg[3]=0;rmsg[4]=0;
    rc=devctl(fd,LMGR_REGISTER,rmsg,sizeof rmsg,0);
    put("  reg "); { int a=SZ[i][0],b=SZ[i][1]; char t[8]; int k=0;
      if(a>=100)t[k++]='0'+a/100; t[k++]='0'+(a/10)%10; t[k++]='0'+a%10; t[k++]='x';
      if(b>=100)t[k++]='0'+b/100; t[k++]='0'+(b/10)%10; t[k++]='0'+b%10; t[k]=0; put(t);}
    put(" -> "); hx(rmsg[4]);
    if(rc==0&&rmsg[4]){ w=SZ[i][0]; h=SZ[i][1]; put(" GRANTED\n"); break; }
    { unsigned u=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&u,4,0); }   /* release a nacked reg before next size */
    put("\n");
  }
  if(!w){ put(">>> no size granted\n"); close(fd); return 2; }

  /* arm the anti-snow fault handler now that a displayable is registered */
  g_fd=fd; g_cid=(unsigned)cid; g_reg=1;
  signal(SIGSEGV,onfault); signal(SIGBUS,onfault); signal(SIGFPE,onfault); signal(SIGILL,onfault);

  gmsg[0]=(unsigned)cid;gmsg[1]=gmsg[2]=gmsg[3]=0; rc=devctl(fd,LMGR_GETVFB,gmsg,sizeof gmsg,0);
  put("getvfb sid="); hx(gmsg[1]); put("\n");
  if(!(rc==0&&gmsg[1])){ put(">>> no framebuffer\n"); ureg=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&ureg,4,0); close(fd); return 3; }

  gf_surface_attach_by_sid(&surf,(void*)dev,gmsg[1]);
  gf_context_create(&ctx); G=(void*)ctx;
  gf_context_set_surface((void*)ctx,(void*)surf);

  /* ---- layout scales from granted size ---- */
  W=w; H=h; u=(H>=400)?2:1;
  scLbl=u; scBig=2*u; scBtn=u+1; scFoot=u;
  int barH=H/8; if(barH<24)barH=24;
  footH=(FONT_H*scFoot)+10; footY=H-footH;

  /* ---- full render ---- */
  gf_draw_begin((void*)ctx);
  fill(C_BG,0,0,W-1,H-1);
  /* top bar */
  fill(C_BAR_BG,0,0,W-1,barH-1); fill(C_LINE,0,barH-2,W-1,barH-1);
  text(14,(barH-FONT_H*u)/2,u,C_BRAND,"PCM-FORGE");
  text(W-14-text_w(u,"OIL SERVICE"),(barH-FONT_H*u)/2,u,C_MUTED,"OIL SERVICE");

  /* body: emblem + readout */
  int bodyY=barH+H/12;
  int embR=H/10; int embCx=embR*2+20; int embCy=bodyY+embR*2;
  border(C_EXT_BD, embCx-embR-14, bodyY-6, (embR+14)*2, (embR*3)+18, 3);
  droplet(embCx,embCy,embR,C_ACCENT);

  int tx=embCx+embR+34;
  text(tx,bodyY,scLbl,C_LABEL,"OIL SERVICE DUE IN");
  int ny=bodyY+FONT_H*scLbl+10;
  int nx=tx;
  text(nx,ny,scBig,C_BIG,"8,200"); nx+=text_w(scBig,"8,200")+adv(scLbl);
  text(nx,ny+FONT_H*(scBig-scLbl),scLbl,C_MUTED,"MI"); nx+=text_w(scLbl,"MI")+adv(scBig)/2;
  text(nx,ny,scBig,C_LINE,"/"); nx+=text_w(scBig,"/")+adv(scBig)/2;
  text(nx,ny,scBig,C_BIG,"340"); nx+=text_w(scBig,"340")+adv(scLbl);
  text(nx,ny+FONT_H*(scBig-scLbl),scLbl,C_MUTED,"DAYS");

  /* progress bar (16 segments, 10 filled) */
  int pbY=ny+FONT_H*scBig+18, pbX=tx, pbW=W-tx-30, segG=4, seg=(pbW-15*segG)/16, pbH=8*u;
  for(i=0;i<16;i++){ unsigned c=(i<10)?C_BAR_ON:C_BAR_OFF; int sx=pbX+i*(seg+segG); fill(c,sx,pbY,sx+seg-1,pbY+pbH-1); }

  /* buttons */
  int btnH=barH+H/12, btnY=footY-btnH-H/16, gap=20;
  int extW=W/4; int rstW=W-extW-gap-40; int bx=20;
  button(bx,btnY,rstW,btnH,C_RST_BG,C_RST_BD,C_RST_TX,scBtn,"RESET OIL SERVICE");
  button(bx+rstW+gap,btnY,extW,btnH,C_EXT_BG,C_EXT_BD,C_EXT_TX,scBtn,"EXIT");

  /* footer (STATIC -- no per-frame update, so we stay on one clean composite) */
  fill(C_FOOT_BG,0,footY,W-1,H-1); fill(C_LINE,0,footY,W-1,footY+1);
  text_c(W/2,footY+5,scFoot,C_MUTED,FOOT1);
  gf_draw_finish((void*)ctx); gf_draw_end((void*)ctx);
  umsg[0]=(unsigned)cid; devctl(fd,LMGR_UPDATE,umsg,sizeof umsg,0);

  smsg[0]=0; smsg[1]=1; smsg[2]=(unsigned)cid;
  rc=devctl(fd,LMGR_SHOW,smsg,12,0); put("show rc="); hx((unsigned)rc); put("\n");
  put(">>> oil-service UI up at "); hx((unsigned)W); put("x"); hx((unsigned)H); put("\n");
  svc_log("PCM-FORGE oil-service tool: screen shown (vin/mileage/reset: pending wiring)\n");

  /* ---- hold: ONE clean composite, NO per-frame updates -> no recomposite churn.
     This is exactly overlay_safe's proven-stable pattern (Show once, sleep, teardown). ---- */
  sleep(HOLD_SECS);
  (void)umsg;

  /* ---- CLEAN TEARDOWN (the anti-snow ordering) ---- */
  put(">>> teardown: unregister...\n");
  ureg=(unsigned)cid; rc=devctl(fd,LMGR_UNREGISTER,&ureg,4,0);
  put("unregister rc="); hx((unsigned)rc); put("\n");
  sleep(2);
  close(fd);
  put(">>> done -- press NAV/CAR to restore OEM screen. NO snow expected.\n");
  put("== app_oil done ==\n");
  return 0;
}
