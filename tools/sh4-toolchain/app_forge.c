/* ============================================================================
 * app_forge.c -- PCM-Forge multi-page toolkit framework (on-car).
 *
 * Fork of the proven-stable app_oil: 480x240 component layer, Show ONCE, then
 * ONLY UpdateVfb to switch pages (exactly how PCM3Root changes screens -> no
 * thrash), clean teardown, anti-snow fault handler. All drawing = gf_draw_rect
 * + gf_context_set_fgcolor (proven primitives only) + our bitmap font.
 *
 * Pages: HOME (branded button grid) / OIL (service readout) / INFO (reads local
 * firmware version, dumps to USB). Buttons are drawn touch-ready; navigation is
 * AUTO-CYCLE for now (input via the SPHKeyInput DSI client is a separate track).
 * ==========================================================================*/
#include "font8x16.h"

extern int  open(const char*, int, ...);
extern int  read(int, void*, unsigned);
extern int  devctl(int, int, void*, unsigned, int*);
extern int  write(int, const void*, int);
extern int  close(int);
extern unsigned sleep(unsigned);
extern void _exit(int);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
extern int  gf_dev_attach(void*, const char*, void*);
extern int  gf_surface_attach_by_sid(void*, void*, unsigned);
extern int  gf_context_create(void*);
extern int  gf_context_set_surface(void*, void*);
extern int  gf_draw_begin(void*);
extern int  gf_context_set_fgcolor(void*, unsigned);
extern int  gf_draw_rect(void*, int, int, int, int);
extern int  gf_draw_finish(void*);
extern int  gf_draw_end(void*);

#define O_RDWR   2
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_APPEND 0x008
#define SIGILL   4
#define SIGFPE   8
#define SIGBUS  10
#define SIGSEGV 11

#define LMGR_CONNECT    0xc00c0506u
#define LMGR_REGISTER   0xc0140500u
#define LMGR_GETVFB     0xc0100503u
#define LMGR_UPDATE     0x80040504u
#define LMGR_SHOW       0x800c0505u
#define LMGR_UNREGISTER 0x80040501u

#define PAGE_HOME 0
#define PAGE_OIL  1
#define PAGE_INFO 2
#define PAGE_SECS 6

/* PCM-Forge palette (gold on near-black, per docs/index.html) */
#define C_BG      0xff0a0a0cu
#define C_BAR     0xff131318u
#define C_LINE    0xff2a2a35u
#define C_GOLD    0xffc8a44eu
#define C_MUTED   0xff8888a0u
#define C_TEXT    0xffe8e8edu
#define C_GREEN   0xff4eca7au
#define C_SELBG   0xff2a2410u
#define C_BAROFF  0xff2a2a35u

static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static void put(const char*s){write(1,s,slen(s));}
static void hx(unsigned v){char b[11];const char*h="0123456789abcdef";int i;
  b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(1,b,10);}

static void usb_append(const char*path_rel,const char*rec){
  static const char*root[3]={"/fs/usb0/","/fs/usb1/","/fs/usb/"};
  char p[64]; int i,k,j,f;
  for(i=0;i<3;i++){
    for(k=0;root[i][k];k++)p[k]=root[i][k];
    for(j=0;path_rel[j];j++)p[k++]=path_rel[j]; p[k]=0;
    f=open(p,O_WRONLY|O_CREAT|O_APPEND,0666);
    if(f>=0){ write(f,rec,slen(rec)); close(f); return; }
  }
}

/* ---- geometry + anti-snow fault handler ---- */
static void *G;
static int W,H,footY,u;
static int g_fd=-1; static unsigned g_cid=0; static int g_reg=0;
static void onfault(int s){ (void)s; if(g_reg&&g_fd>=0){ unsigned x=g_cid; devctl(g_fd,LMGR_UNREGISTER,&x,4,0); } _exit(3); }

static void crect(int x1,int y1,int x2,int y2){
  if(x1<0)x1=0; if(y1<0)y1=0; if(x2>W-1)x2=W-1; if(y2>H-1)y2=H-1;
  if(x1<=x2&&y1<=y2) gf_draw_rect(G,x1,y1,x2,y2);
}
static void fill(unsigned c,int x1,int y1,int x2,int y2){ gf_context_set_fgcolor(G,c); crect(x1,y1,x2,y2); }
static void border(unsigned c,int x,int y,int w,int h,int t){
  fill(c,x,y,x+w-1,y+t-1); fill(c,x,y+h-t,x+w-1,y+h-1);
  fill(c,x,y,x+t-1,y+h-1); fill(c,x+w-t,y,x+w-1,y+h-1);
}

/* ---- bitmap-font text ---- */
static void glyph(int gx,int gy,int sc,unsigned col,int code){
  const unsigned char*g; int row,cx;
  if(code<FONT_FIRST||code>FONT_LAST)code=FONT_FIRST;
  g=FONT8X16[code-FONT_FIRST]; gf_context_set_fgcolor(G,col);
  for(row=0;row<FONT_H;row++){ unsigned bits=g[row];
    for(cx=0;cx<FONT_W;cx++) if(bits&(0x80u>>cx)) crect(gx+cx*sc,gy+row*sc,gx+cx*sc+sc-1,gy+row*sc+sc-1);
  }
}
static int adv(int sc){ return (FONT_W+1)*sc; }
static int text_w(int sc,const char*s){ return slen(s)*adv(sc); }
static void text(int x,int y,int sc,unsigned col,const char*s){
  int cx=x; while(*s){ if(*s!=' ') glyph(cx,y,sc,col,(unsigned char)*s); cx+=adv(sc); s++; }
}
static void text_c(int cx,int y,int sc,unsigned col,const char*s){ text(cx-text_w(sc,s)/2,y,sc,col,s); }

static int isqrt(int v){int r=0;while((r+1)*(r+1)<=v)r++;return r;}
static void droplet(int cx,int cy,int r,unsigned col){
  int y,hw; gf_context_set_fgcolor(G,col);
  for(y=-r;y<=r;y++){ hw=isqrt(r*r-y*y); crect(cx-hw,cy+y,cx+hw,cy+y); }
  for(y=0;y<2*r;y++){ hw=y/2; crect(cx-hw,(cy-2*r)+y,cx+hw,(cy-2*r)+y); }
}

static int barH(void){ int b=H/8; return b<24?24:b; }
static void topbar(const char*right){
  fill(C_BAR,0,0,W-1,barH()-1); fill(C_LINE,0,barH()-2,W-1,barH()-1);
  text(12,(barH()-FONT_H*u)/2,u,C_GOLD,"PCM-FORGE");
  text(W-12-text_w(u,right),(barH()-FONT_H*u)/2,u,C_MUTED,right);
}
static void footer(const char*s){
  int fh=FONT_H*u+8; footY=H-fh;
  fill(C_BAR,0,footY,W-1,H-1); fill(C_LINE,0,footY,W-1,footY+1);
  text_c(W/2,footY+4,u,C_MUTED,s);
}
static void button(int x,int y,int w,int h,int sel,const char*label){
  fill(sel?C_SELBG:C_BAR,x,y,x+w-1,y+h-1);
  border(sel?C_GOLD:C_LINE,x,y,w,h,2);
  text_c(x+w/2,y+(h-FONT_H*(u+1))/2,u+1,sel?C_GOLD:C_TEXT,label);
}
/* footer Y estimate for layout (footer() sets the real footY each draw) */
static int footY_est(void){ return H-(FONT_H*u+8); }

/* ---- INFO data: read local firmware version, dump to USB ---- */
static char g_ver[64];
static void load_info(void){
  static const char*paths[2]={"/mnt/ifs1/HBproject/version.txt","/HBproject/version.txt"};
  int i,fd,n; g_ver[0]=0;
  for(i=0;i<2;i++){ fd=open(paths[i],O_RDONLY);
    if(fd>=0){ n=read(fd,g_ver,sizeof g_ver-1); close(fd); if(n>0){ g_ver[n]=0; break; } } }
  for(i=0;g_ver[i];i++){ unsigned char c=(unsigned char)g_ver[i]; if(c<32||c>126){ g_ver[i]=0; break; } }
  if(!g_ver[0]){ const char*na="(not found)"; for(i=0;na[i];i++)g_ver[i]=na[i]; g_ver[i]=0; }
  usb_append("info_dump.txt","PCM-FORGE INFO: firmware=");
  usb_append("info_dump.txt",g_ver);
  usb_append("info_dump.txt","\n");
}

/* ---- pages (each draws the full 480x240 frame) ---- */
static void field(int y,const char*label,const char*val){
  text(18,y,u,C_MUTED,label);
  text(150,y,u,C_TEXT,val);
}
static void render_home(int sel){
  fill(C_BG,0,0,W-1,H-1); topbar("TOOLKIT");
  int y=barH()+10, bw=W-40, bh=(footY_est()-y-16)/3, i;
  static const char*items[3]={"OIL SERVICE","ACTIVATIONS","INFO"};
  for(i=0;i<3;i++) button(20,y+i*(bh+6),bw,bh,i==sel,items[i]);
  footer("AUTO-CYCLING  -  TOUCH COMING SOON");
}
static void render_oil(void){
  fill(C_BG,0,0,W-1,H-1); topbar("OIL SERVICE");
  int r=H/10, cx=r*2+16, cy=barH()+6+r*2;
  border(C_LINE,cx-r-12,barH()+8,(r+12)*2,r*3+14,2);
  droplet(cx,cy,r,C_GOLD);
  int tx=cx+r+28, ny=barH()+18;
  text(tx,ny,u,C_MUTED,"OIL SERVICE DUE IN");
  int by=ny+FONT_H*u+8, nx=tx;
  text(nx,by,2*u,C_TEXT,"8,200"); nx+=text_w(2*u,"8,200")+adv(u);
  text(nx,by+FONT_H*u,u,C_MUTED,"MI"); nx+=text_w(u,"MI")+adv(u);
  text(nx,by,2*u,C_LINE,"/"); nx+=text_w(2*u,"/")+adv(u);
  text(nx,by,2*u,C_TEXT,"340"); nx+=text_w(2*u,"340")+adv(u);
  text(nx,by+FONT_H*u,u,C_MUTED,"DAYS");
  int pbY=by+FONT_H*2*u+12, seg=(W-tx-24-15*3)/16, i;
  for(i=0;i<16;i++){ unsigned c=(i<10)?C_GREEN:C_BAROFF; int sx=tx+i*(seg+3); fill(c,sx,pbY,sx+seg-1,pbY+7); }
  button(20,footY_est()-40,W-40,32,1,"RESET OIL SERVICE");
  footer("SELECT TO RESET  (WIRED WHEN INPUT LANDS)");
}
static void render_info(void){
  fill(C_BG,0,0,W-1,H-1); topbar("INFO");
  int y=barH()+14, dy=FONT_H*u+10;
  field(y,        "FIRMWARE", g_ver);
  field(y+dy,     "VIN",      "PENDING (CODING)");
  field(y+2*dy,   "MODEL",    "CAYENNE 958");
  field(y+3*dy,   "SCREEN",   "480 x 240");
  footer("DUMPED TO USB  ->  INFO_DUMP.TXT");
}

static void render_page(int p,int sel){
  gf_draw_begin(G);
  if(p==PAGE_OIL) render_oil();
  else if(p==PAGE_INFO) render_info();
  else render_home(sel);
  gf_draw_finish(G); gf_draw_end(G);
}

int main(int argc,char**argv){
  unsigned cmsg[3],rmsg[5],gmsg[4],umsg[1],smsg[3],ureg;
  unsigned dev=0,surf=0,ctx=0; unsigned char devinfo[256];
  int fd,rc,i,cid=0x6002,w=0,h=0;
  static const int SZ[][2]={{480,240},{400,240},{320,240}};
  static const int SEQ[6]={PAGE_HOME,PAGE_OIL,PAGE_INFO,PAGE_HOME,PAGE_OIL,PAGE_INFO};

  put("== app_forge: PCM-Forge toolkit ==\n");
  for(i=0;i<256;i++)devinfo[i]=0;
  gf_dev_attach(&dev,0,devinfo);
  fd=open("/dev/layermanager",O_RDWR); put("open fd="); hx((unsigned)fd); put("\n");
  if(fd<0){put(">>> OPEN FAILED\n");return 1;}
  cmsg[0]=cmsg[1]=cmsg[2]=0; devctl(fd,LMGR_CONNECT,cmsg,sizeof cmsg,0);
  for(i=0;i<3;i++){
    rmsg[0]=cid;rmsg[1]=SZ[i][0];rmsg[2]=SZ[i][1];rmsg[3]=0;rmsg[4]=0;
    rc=devctl(fd,LMGR_REGISTER,rmsg,sizeof rmsg,0);
    if(rc==0&&rmsg[4]){ w=SZ[i][0]; h=SZ[i][1]; break; }
    { unsigned x=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&x,4,0); }
  }
  if(!w){ put(">>> no size granted\n"); close(fd); return 2; }
  put("register "); hx((unsigned)w); put("x"); hx((unsigned)h); put(" cid="); hx((unsigned)cid); put("\n");
  g_fd=fd; g_cid=(unsigned)cid; g_reg=1;
  signal(SIGSEGV,onfault); signal(SIGBUS,onfault); signal(SIGFPE,onfault); signal(SIGILL,onfault);

  gmsg[0]=(unsigned)cid;gmsg[1]=gmsg[2]=gmsg[3]=0; rc=devctl(fd,LMGR_GETVFB,gmsg,sizeof gmsg,0);
  if(!(rc==0&&gmsg[1])){ put(">>> no framebuffer\n"); ureg=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&ureg,4,0); close(fd); return 3; }
  gf_surface_attach_by_sid(&surf,(void*)dev,gmsg[1]);
  gf_context_create(&ctx); G=(void*)ctx; gf_context_set_surface((void*)ctx,(void*)surf);
  W=w; H=h; u=(H>=400)?2:1;
  load_info();

  /* Show ONCE, then only UpdateVfb per page change (mimic PCM3Root -> stable) */
  for(i=0;i<6;i++){
    render_page(SEQ[i], 0);
    umsg[0]=(unsigned)cid; devctl(fd,LMGR_UPDATE,umsg,sizeof umsg,0);
    if(i==0){
      smsg[0]=0; smsg[1]=1; smsg[2]=(unsigned)cid;
      rc=devctl(fd,LMGR_SHOW,smsg,12,0); put("show rc="); hx((unsigned)rc); put("\n");
      usb_append("service_log.txt","PCM-FORGE toolkit: shown (home/oil/info auto-cycle)\n");
    }
    sleep(PAGE_SECS);
  }

  put(">>> teardown: unregister...\n");
  ureg=(unsigned)cid; rc=devctl(fd,LMGR_UNREGISTER,&ureg,4,0);
  put("unregister rc="); hx((unsigned)rc); put("\n");
  sleep(2); close(fd);
  put("== app_forge done -- press NAV/CAR to restore OEM ==\n");
  return 0;
}
