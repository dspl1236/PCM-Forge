/* ============================================================================
 * forge_splash.c -- PCM 3.1 RUNNING -> DONE status splash with a live progress
 * bar, and a NO-BLACK restore of the OEM screen.
 *
 * v2 (2026-11-12): animated. While RUNNING it redraws ~4 times a second:
 *   - the three dots in "RUNNING . . ." pulse in turn (the screen is alive);
 *   - a progress row: the current step on the left, "n/m  m:ss" on the right;
 *   - a progress bar: filled n/m when the running module reports progress,
 *     otherwise a sweeping block (indeterminate) -- the elapsed timer runs
 *     either way.
 * On DONE it shows the DONE image with a full bar and the total time.
 *
 * Progress comes from a text file next to the done-flag: <dir of flagfile>/
 * forge_progress, one line, "n/m label" (bar + label) or just "label". Any
 * module can write it; SysInfo does (mark() in sysinfo_dump.sh). A stale one
 * from an earlier run is deleted at start.
 *
 * Unchanged from v1: one 480x240 layer, getvfb FRESH for every frame (the VFB
 * is double-buffered, so every frame redraws everything), the OEM-cid discovery
 * and the restore of the OEM screen on teardown (no black).
 *   SHOW is sent for the first and the DONE frame only; the frames in between
 *   just UPDATE, which is how PCM3Root itself refreshes once shown.
 *
 * FREESTANDING SH4/QNX (crt.S, no libgcc): no division by a variable anywhere
 * (bar fill = repeated subtraction); division by constants compiles to
 * multiplies.
 *
 * Usage:  forge_splash <run.bin> <done.bin> <flagfile> [maxwait=120] [hold=4]
 * SIGTERM/SIGINT -> clean unregister.
 * ==========================================================================*/
extern int  open(const char*, int, ...);
extern int  read(int, void*, unsigned);
extern int  write(int, const void*, int);
extern int  close(int);
extern int  devctl(int, int, void*, unsigned, int*);
extern unsigned sleep(unsigned);
extern int  usleep(unsigned);
extern int  unlink(const char*);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
extern void _exit(int);

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

#include "font8x16.h"

#define SIGINT   2
#define SIGILL   4
#define SIGFPE   8
#define SIGBUS  10
#define SIGSEGV 11
#define SIGTERM 15

#define O_RDONLY 0
#define O_RDWR   2
#define O_WRONLY 1
#define O_APPEND 0x008
#define O_CREAT  0x100

#define LMGR_CONNECT    0xc00c0506u
#define LMGR_REGISTER   0xc0140500u
#define LMGR_GETVFB     0xc0100503u
#define LMGR_UPDATE     0x80040504u
#define LMGR_SHOW       0x800c0505u
#define LMGR_UNREGISTER 0x80040501u

#define PFIM_MAGIC 0x4d494650u
#define HDR_BYTES  24
#define MAX_W      480
#define MAX_H      240
#define MAX_BPP    4
#define MAX_OEM    12          /* max OEM cids we track for additive show */

/* ---- progress display: layout for the 480x240 layer (running.bin keeps all
   its content above row 181; the band below is ours) ---- */
#define FRAME_US   250000      /* 4 frames a second */
#define FRAME_MS   250
#define COL_BG     0xff0a0a0cu /* the image's own background */
#define COL_GOLD   0xffc8a44eu /* the image's gold */
#define COL_DIM    0xff4a3e22u /* a resting dot */
#define COL_TRACK  0xff1c1a16u
#define COL_EDGE   0xff5a4a28u
#define COL_TEXT   0xffd8d4c8u
#define COL_TEXT2  0xff8a8578u
#define TXT_Y      198
#define BAR_X1     24
#define BAR_X2     455
#define BAR_Y1     220
#define BAR_Y2     229
#define ADV        (FONT_W+1)  /* text advance per character */
#define SWEEP_W    80
#define SWEEP_STEP 18
/* the three dots of "RUNNING . . ." in running.bin: 11x11 at these x, y 168..178 */
static const int DOT_X[3]={301,367,433};
#define DOT_Y      168
static const unsigned char DOT_RUN[11][2]={{4,6},{2,8},{1,9},{1,9},{0,10},{0,10},{0,10},{1,9},{1,9},{2,8},{4,6}};

static unsigned char g_run [HDR_BYTES + (MAX_W*MAX_H*MAX_BPP) + 64] __attribute__((aligned(16)));
static unsigned char g_done[HDR_BYTES + (MAX_W*MAX_H*MAX_BPP) + 64] __attribute__((aligned(16)));
static unsigned char g_lm[16384];             /* /dev/layermanager text state dump */

/* ---- logging: fd 1 + USB forge_splash.txt ---- */
static int g_log=-1;
static int  slen(const char*s){ int n=0; while(s[n])n++; return n; }
static void lg(const char*s){ int n=slen(s); write(1,s,n); if(g_log>=0) write(g_log,s,n); }
static void lgn(const char*s,int n){ write(1,s,n); if(g_log>=0) write(g_log,s,n); }
static void lghx(unsigned v){ char b[11]; const char*h="0123456789abcdef"; int i;
  b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0; lg(b); }
static void lgdec(unsigned v){ char b[12]; int i=11; b[11]=0;
  if(v==0){ lg("0"); return; } while(v&&i>0){ b[--i]='0'+(v%10); v/=10; } lg(b+i); }
static void openlog(void){
  static const char*P[3]={"/fs/usb0/forge_splash.txt","/fs/usb1/forge_splash.txt","/fs/usb/forge_splash.txt"};
  int i,f; for(i=0;i<3;i++){ f=open(P[i],O_WRONLY|O_CREAT|O_APPEND,0666); if(f>=0){ g_log=f; return; } }
}
static unsigned rd32(const unsigned char*p){
  return (unsigned)p[0]|((unsigned)p[1]<<8)|((unsigned)p[2]<<16)|((unsigned)p[3]<<24); }
static int myatoi(const char*s){ int v=0; if(!s) return 0; while(*s>='0'&&*s<='9'){ v=v*10+(*s-'0'); s++; } return v; }

static int g_fd=-1; static unsigned g_cid=0; static int g_reg=0;
static void onfault(int sig){ (void)sig;
  if(g_reg && g_fd>=0){ unsigned u=g_cid; devctl(g_fd,LMGR_UNREGISTER,&u,4,0); } _exit(0); }

static unsigned char* load_blob(const char*path, unsigned char*buf, int bufsz,
                                unsigned*pW,unsigned*pH,unsigned*pStride,unsigned*pFmt){
  int bf,total=0,r; unsigned magic,W,H,fmt,stride,bpp,minneed;
  bf=open(path,O_RDONLY,0);
  if(bf<0){ lg("  open FAIL "); lg(path); lg("\n"); return 0; }
  for(;;){ r=read(bf,buf+total,(unsigned)(bufsz-total)); if(r<=0) break; total+=r; if(total>=bufsz) break; }
  close(bf);
  if(total<HDR_BYTES){ lg("  short read "); lg(path); lg("\n"); return 0; }
  magic=rd32(buf); W=rd32(buf+4); H=rd32(buf+8); fmt=rd32(buf+12); stride=rd32(buf+16); bpp=rd32(buf+20);
  if(magic!=PFIM_MAGIC){ lg("  bad magic "); lg(path); lg("\n"); return 0; }
  if(W==0||H==0||W>MAX_W||H>MAX_H||bpp==0||bpp>MAX_BPP){ lg("  bad dims "); lg(path); lg("\n"); return 0; }
  if(stride==0) stride=W*bpp;
  if(stride<W*bpp||stride>0x10000u){ lg("  bad stride "); lg(path); lg("\n"); return 0; }
  minneed=stride*(H-1)+W*bpp;
  if((unsigned)HDR_BYTES+minneed>(unsigned)total){ lg("  truncated "); lg(path); lg("\n"); return 0; }
  *pW=W;*pH=H;*pStride=stride;*pFmt=fmt;
  lg("  loaded "); lg(path); lg(" "); lgdec(W); lg("x"); lgdec(H); lg(" fmt="); lghx(fmt); lg("\n");
  return buf+HDR_BYTES;
}

/* ---- OEM visible-set discovery via read("/dev/layermanager") ---- */
static unsigned g_oem[MAX_OEM]; static int g_noem=0;
static int str_at(const unsigned char*h,int hlen,int pos,const char*n){
  int i; for(i=0;n[i];i++){ if(pos+i>=hlen || h[pos+i]!=(unsigned char)n[i]) return 0; } return 1;
}
/* read /dev/layermanager's text state dump into g_lm, log it, return length */
static int read_and_log_lmgr(const char*tag){
  int f,r,total=0,it,L;
  f=open("/dev/layermanager",O_RDONLY,0);
  lg("read /dev/layermanager ["); lg(tag); lg("] fd="); lghx((unsigned)f); lg("\n");
  if(f<0) return 0;
  for(it=0;it<8;it++){
    r=read(f,g_lm+total,(unsigned)((int)sizeof(g_lm)-1-total));
    if(r<=0) break; total+=r; if(total>=(int)sizeof(g_lm)-1) break;
  }
  close(f); g_lm[total]=0; L=total;
  lg("--- lmgr state ["); lg(tag); lg("] ("); lgdec((unsigned)L); lg(" bytes) ---\n");
  if(L>0) lgn((const char*)g_lm,L);
  lg("\n--- end ---\n");
  return L;
}
/* scan a displayable block [s,e) for "<label><digits>" and return the number */
static unsigned blk_uint(int s,int e,const char*label){
  int j,ll=slen(label);
  for(j=s;j<e;j++){ if(str_at(g_lm,e,j,label)){ int p=j+ll; unsigned v=0;
    if(p<e && g_lm[p]>='0'&&g_lm[p]<='9'){ while(p<e&&g_lm[p]>='0'&&g_lm[p]<='9'){v=v*10+(unsigned)(g_lm[p]-'0');p++;} return v; } } }
  return 0xffffffffu;   /* not found */
}
/* Find the OEM main HMI: the 800x480 displayable VISIBLE on display 0. Identify
   by SIZE, not by "which cids are on display 0" -- a leaked smaller cid (200,
   240x257) can falsely sit on display 0, and must NOT be restored. */
static void discover_oem_cids(void){
  int L=read_and_log_lmgr("startup"), i;
  g_noem=0;
  for(i=0;i+21<L;i++){
    if(!str_at(g_lm,L,i,"--- Displayable Start")) continue;
    int e=i+21; while(e<L && !str_at(g_lm,L,e,"--- Displayable End")) e++;
    unsigned cid=blk_uint(i+21,e,"Displayable ");     /* "Displayable <n> is..." */
    unsigned w  =blk_uint(i+21,e,"Width ");
    unsigned h  =blk_uint(i+21,e,"Height ");
    /* visible display index: "Is visible on layer L at display <d>" */
    int visD0=0; { int j;
      for(j=i;j<e;j++){ if(str_at(g_lm,L,j,"Is visible on layer")){ int p=j;
        while(p<e && !str_at(g_lm,e,p,"at display ")) p++;
        if(p+11<e){ p+=11; if(g_lm[p]=='0') visD0=1; } break; } } }
    if(cid!=0xffffffffu && visD0 && w==800 && h==480 && g_noem<MAX_OEM){
      int dup=0,k; for(k=0;k<g_noem;k++) if(g_oem[k]==cid) dup=1; if(!dup) g_oem[g_noem++]=cid;
    }
    i=e;
  }
  lg("OEM main HMI cid(s) [800x480 @display0]: "); { int j; for(j=0;j<g_noem;j++){ lgdec(g_oem[j]); lg(" "); } } lg("\n");
}

static void *G_dev, *G_ctx;
static int  G_W, G_H, G_fd;
static unsigned G_cid, g_surf=0;

/* ======================= progress state + drawing ======================== */
static char g_prog_path[192];
static char g_label[64];
static int  g_n=-1, g_m=0;          /* g_n<0: no n/m -> indeterminate bar */
static unsigned g_elapsed_ms=0;
static int  g_dot=0, g_dot_tick=0;  /* active dot 0..2, frames on it */
static int  g_sweep=0, g_sweep_dir=1;

static void rct(unsigned c,int x1,int y1,int x2,int y2){
  if(x1<0)x1=0; if(y1<0)y1=0; if(x2>G_W-1)x2=G_W-1; if(y2>G_H-1)y2=G_H-1;
  if(x1>x2||y1>y2) return;
  gf_context_set_fgcolor(G_ctx,c); gf_draw_rect(G_ctx,x1,y1,x2,y2);
}
/* one 8x16 glyph; each horizontal run of set pixels is a single rect */
static void glyph(int gx,int gy,int code){
  const unsigned char*g; int row,cx,start;
  if(code<FONT_FIRST||code>FONT_LAST) code='?';
  g=FONT8X16[code-FONT_FIRST];
  for(row=0;row<FONT_H;row++){
    unsigned bits=g[row]; cx=0;
    while(cx<FONT_W){
      if(bits&(0x80u>>cx)){ start=cx; while(cx<FONT_W && (bits&(0x80u>>cx))) cx++;
        if(gx+cx-1<G_W && gy+row<G_H) gf_draw_rect(G_ctx,gx+start,gy+row,gx+cx-1,gy+row); }
      else cx++;
    }
  }
}
static void text(int x,int y,unsigned col,const char*s){
  gf_context_set_fgcolor(G_ctx,col);
  while(*s){ if(*s!=' ') glyph(x,y,(unsigned char)*s); x+=ADV; s++; }
}
static int put_dec(char*b,int p,unsigned v){   /* append decimal, return new length */
  char t[12]; int i=0; if(v==0) t[i++]='0'; while(v){ t[i++]=(char)('0'+(v%10)); v/=10; }
  while(i) b[p++]=t[--i]; b[p]=0; return p;
}
/* w*n/m by repeated subtraction (no division helper in a freestanding build) */
static int muldiv(int w,int n,int m){ int t=w*n,q=0; if(m<=0) return 0; while(t>=m){ t-=m; q++; } return q; }

/* <dir of flagfile>/forge_progress */
static void make_prog_path(const char*flagp){
  int i,cut=-1,n=slen(flagp);
  for(i=0;i<n;i++) if(flagp[i]=='/') cut=i;
  if(cut<0||cut+16>=(int)sizeof g_prog_path){ g_prog_path[0]=0; return; }
  for(i=0;i<=cut;i++) g_prog_path[i]=flagp[i];
  { const char*s="forge_progress"; int k=0; while(s[k]){ g_prog_path[cut+1+k]=s[k]; k++; } g_prog_path[cut+1+k]=0; }
}
/* re-read the progress line; keep the last good one if the file is missing */
static void read_progress(void){
  char b[96]; int f,r,i,p=0,n=0,m=0,ok=0,k;
  if(!g_prog_path[0]) return;
  f=open(g_prog_path,O_RDONLY,0); if(f<0) return;
  r=read(f,b,95); close(f); if(r<=0) return; b[r]=0;
  if(b[0]>='0'&&b[0]<='9'){
    i=0; while(b[i]>='0'&&b[i]<='9'&&n<100000){ n=n*10+(b[i]-'0'); i++; }
    if(b[i]=='/'&&b[i+1]>='0'&&b[i+1]<='9'){ i++; while(b[i]>='0'&&b[i]<='9'&&m<100000){ m=m*10+(b[i]-'0'); i++; }
      if(m>0){ ok=1; p=i; while(b[p]==' ') p++; } }
  }
  if(ok){ if(n>m) n=m; } else { n=-1; m=0; p=0; }
  { char nl[64]; for(k=0;k<63&&b[p+k]&&b[p+k]!='\n'&&b[p+k]!='\r';k++){ char c=b[p+k]; nl[k]=(c>=32&&c<=126)?c:'?'; } nl[k]=0;
    /* log a change of step once, so the USB log shows how the run went */
    if(n!=g_n||m!=g_m||!str_at((const unsigned char*)g_label,64,0,nl)||slen(g_label)!=k){
      lg("  progress ["); lgdec(g_elapsed_ms/1000); lg("s] "); if(ok){ lgdec((unsigned)n); lg("/"); lgdec((unsigned)m); lg(" "); } lg(nl); lg("\n");
    }
    for(i=0;i<=k;i++) g_label[i]=nl[i];
  }
  g_n=n; g_m=m;
}

/* the band under the image: label + "n/m  m:ss", then the bar */
static void draw_progress(int done){
  char right[24], lab[64]; int rp=0, rw, maxc, i, inner;
  unsigned secs=g_elapsed_ms/1000, mins=secs/60, ss=secs-mins*60;
  rct(COL_BG,0,184,G_W-1,G_H-1);
  if(!done && g_n>=0){ rp=put_dec(right,rp,(unsigned)g_n); right[rp++]='/'; rp=put_dec(right,rp,(unsigned)g_m); right[rp++]=' '; right[rp++]=' '; }
  rp=put_dec(right,rp,mins); right[rp++]=':'; right[rp++]=(char)('0'+ss/10); right[rp++]=(char)('0'+ss%10); right[rp]=0;
  rw=rp*ADV;
  text(BAR_X2+1-rw,TXT_Y,COL_TEXT2,right);
  { const char*src= done? "done" : (g_label[0]? g_label : "working");
    maxc=(BAR_X2-rw-12-BAR_X1)/ADV; if(maxc>63) maxc=63; if(maxc<4) maxc=4;
    for(i=0;src[i]&&i<maxc;i++) lab[i]=src[i];
    if(src[i]&&i>=2){ lab[i-1]='.'; lab[i-2]='.'; }   /* cut: end with ".." */
    lab[i]=0; text(BAR_X1,TXT_Y,COL_TEXT,lab); }
  rct(COL_EDGE,BAR_X1,BAR_Y1,BAR_X2,BAR_Y2);
  rct(COL_TRACK,BAR_X1+1,BAR_Y1+1,BAR_X2-1,BAR_Y2-1);
  inner=(BAR_X2-1)-(BAR_X1+1)+1;
  if(done) rct(COL_GOLD,BAR_X1+1,BAR_Y1+1,BAR_X2-1,BAR_Y2-1);
  else if(g_n>=0){ int f=muldiv(inner,g_n,g_m); if(f>0) rct(COL_GOLD,BAR_X1+1,BAR_Y1+1,BAR_X1+f,BAR_Y2-1); }
  else rct(COL_GOLD,BAR_X1+1+g_sweep,BAR_Y1+1,BAR_X1+g_sweep+SWEEP_W,BAR_Y2-1);
}
/* dim the two resting dots of "RUNNING . . ." (the active one stays as drawn) */
static void draw_dots(void){
  int d,r;
  for(d=0;d<3;d++){ if(d==g_dot) continue;
    rct(COL_BG,DOT_X[d]-1,DOT_Y-1,DOT_X[d]+11,DOT_Y+11);
    gf_context_set_fgcolor(G_ctx,COL_DIM);
    for(r=0;r<11;r++) gf_draw_rect(G_ctx,DOT_X[d]+DOT_RUN[r][0],DOT_Y+r,DOT_X[d]+DOT_RUN[r][1],DOT_Y+r);
  }
}
static void advance_animation(void){
  if(++g_dot_tick>=2){ g_dot_tick=0; if(++g_dot>=3) g_dot=0; }        /* a dot every 0.5 s */
  { int span=(BAR_X2-1)-(BAR_X1+1)+1-SWEEP_W;                          /* ping-pong sweep */
    g_sweep+=g_sweep_dir*SWEEP_STEP;
    if(g_sweep>=span){ g_sweep=span; g_sweep_dir=-1; } else if(g_sweep<=0){ g_sweep=0; g_sweep_dir=1; } }
}

/* frame = image + (overlay); mode 0 running, 1 done */
static void draw_frame(unsigned char*px, unsigned iw, unsigned ih, unsigned stride, unsigned fmt, int mode){
  unsigned imgsurf=0;
  int dx=((int)G_W-(int)iw)/2; if(dx<0) dx=0;
  int dy=((int)G_H-(int)ih)/2; if(dy<0) dy=0;
  gf_surface_attach(&imgsurf,G_dev,iw,ih,(int)stride,(int)fmt,0,(void*)px,0);
  gf_draw_begin(G_ctx);
  gf_context_set_fgcolor(G_ctx,0xff000000u);
  gf_draw_rect(G_ctx,0,0,G_W-1,G_H-1);
  gf_draw_blit2(G_ctx,(void*)imgsurf,0, 0,0,(int)iw-1,(int)ih-1, dx,dy);
  if(G_W==480 && G_H==240){            /* the layout assumes the 480x240 layer */
    if(mode==0) draw_dots();
    draw_progress(mode==1);
  }
  gf_draw_finish(G_ctx);
  gf_draw_end(G_ctx);
  gf_surface_free((void*)imgsurf);
}

/* show our panel (proven single-show: {display=0, count=1, our_cid}). This hides
   the OEM while we're up; restore_oem() brings it back on teardown. */
static void show_ours(void){
  unsigned buf[3]; int rc;
  buf[0]=0; buf[1]=1; buf[2]=G_cid;
  rc=devctl(G_fd,LMGR_SHOW,buf,12,0);
  lg("  show ours rc="); lghx((unsigned)rc); lg("\n");
}

/* present one frame: getvfb FRESH (current back buffer) -> draw -> UPDATE [-> SHOW].
   tag==0: a quiet animation frame (no log, no SHOW). */
static void present(unsigned char*px, unsigned iw, unsigned ih, unsigned stride, unsigned fmt, const char*tag, int mode){
  unsigned gmsg[4], umsg[1], sid; int rc;
  gmsg[0]=G_cid; gmsg[1]=gmsg[2]=gmsg[3]=0;
  rc=devctl(G_fd,LMGR_GETVFB,gmsg,sizeof gmsg,0); sid=gmsg[1];
  if(tag){ lg("  "); lg(tag); lg(" getvfb sid="); lghx(sid); lg("\n"); }
  if(!(rc==0&&sid)){ if(tag) lg("  >>> getvfb failed\n"); return; }
  if(g_surf){ gf_surface_free((void*)g_surf); g_surf=0; }
  gf_surface_attach_by_sid(&g_surf,G_dev,sid);
  gf_context_set_surface(G_ctx,(void*)g_surf);
  draw_frame(px,iw,ih,stride,fmt,mode);
  umsg[0]=G_cid; devctl(G_fd,LMGR_UPDATE,umsg,sizeof umsg,0);
  if(tag) show_ours();
}

/* restore the OEM-only visible set (drop our cid) so teardown leaves no black */
static void restore_oem(void){
  unsigned buf[2+MAX_OEM]; int i,rc;
  if(g_noem<=0){ lg(">>> no OEM cids parsed -> cannot restore (screen will be black until NAV/CAR)\n"); return; }
  buf[0]=0; buf[1]=(unsigned)g_noem;
  for(i=0;i<g_noem;i++) buf[2+i]=g_oem[i];
  rc=devctl(G_fd,LMGR_SHOW,buf,(unsigned)(8+4*g_noem),0);
  lg(">>> restore OEM show count="); lgdec((unsigned)g_noem); lg(" rc="); lghx((unsigned)rc); lg("\n");
}

int main(int argc,char**argv){
  unsigned cmsg[3],rmsg[5],ureg;
  unsigned dev=0,ctx=0;
  unsigned char devinfo[256];
  int fd,rc,i,cid=0x6003,W=0,H=0,maxwait,hold,seen;
  unsigned rW,rH,rStride,rFmt,dW,dH,dStride,dFmt,limit_ms;
  unsigned char *rpx,*dpx;
  const char *runp,*donep,*flagp;
  static const int SZ[][2]={{480,240},{400,240},{320,240}};

  openlog();
  lg("== forge_splash v2 (progress bar, additive-restore) ==\n");
  if(argc<4){ lg(">>> usage: forge_splash run.bin done.bin flagfile [maxwait] [hold]\n"); return 1; }
  runp=argv[1]; donep=argv[2]; flagp=argv[3];
  maxwait=(argc>4)?myatoi(argv[4]):120; if(maxwait<1) maxwait=1; if(maxwait>86400) maxwait=86400;
  hold   =(argc>5)?myatoi(argv[5]):4;   if(hold<1) hold=1;
  make_prog_path(flagp);
  if(g_prog_path[0]){ unlink(g_prog_path); lg("progress file: "); lg(g_prog_path); lg("\n"); }

  rpx=load_blob(runp,  g_run,  (int)sizeof(g_run),  &rW,&rH,&rStride,&rFmt);
  dpx=load_blob(donep, g_done, (int)sizeof(g_done), &dW,&dH,&dStride,&dFmt);
  if(!rpx){ lg(">>> RUNNING blob failed\n"); return 1; }

  for(i=0;i<256;i++) devinfo[i]=0;
  rc=gf_dev_attach(&dev,0,devinfo); lg("gf_dev_attach rc="); lghx((unsigned)rc); lg("\n");
  fd=open("/dev/layermanager",O_RDWR); lg("open lmgr fd="); lghx((unsigned)fd); lg("\n");
  if(fd<0){ lg(">>> OPEN FAILED\n"); return 1; }
  cmsg[0]=cmsg[1]=cmsg[2]=0; devctl(fd,LMGR_CONNECT,cmsg,sizeof cmsg,0);
  lg("connect reply=["); lghx(cmsg[0]); lg(" "); lghx(cmsg[1]); lg("]\n");

  /* discover the OEM's currently-visible cids BEFORE we register ours */
  discover_oem_cids();

  for(i=0;i<3;i++){
    rmsg[0]=cid; rmsg[1]=SZ[i][0]; rmsg[2]=SZ[i][1]; rmsg[3]=0; rmsg[4]=0;
    rc=devctl(fd,LMGR_REGISTER,rmsg,sizeof rmsg,0);
    lg("  reg "); lgdec((unsigned)SZ[i][0]); lg("x"); lgdec((unsigned)SZ[i][1]); lg(" -> "); lghx(rmsg[4]);
    if(rc==0&&rmsg[4]){ W=SZ[i][0]; H=SZ[i][1]; lg(" GRANTED\n"); break; }
    { unsigned u=(unsigned)cid; devctl(fd,LMGR_UNREGISTER,&u,4,0); } lg("\n");
  }
  if(!W){ lg(">>> no size granted\n"); close(fd); return 2; }

  g_fd=fd; g_cid=(unsigned)cid; g_reg=1;
  signal(SIGSEGV,onfault); signal(SIGBUS,onfault); signal(SIGFPE,onfault); signal(SIGILL,onfault);
  signal(SIGTERM,onfault); signal(SIGINT,onfault);

  gf_context_create(&ctx);
  G_dev=(void*)dev; G_ctx=(void*)ctx; G_W=W; G_H=H; G_fd=fd; G_cid=(unsigned)cid;

  read_progress();
  present(rpx,rW,rH,rStride,rFmt,"RUNNING",0);
  read_and_log_lmgr("after-RUNNING-show");   /* diagnostic: our layer + OEM state */

  /* animate until the done-flag appears or maxwait runs out */
  seen=0; limit_ms=(unsigned)maxwait*1000u;
  for(;;){
    int ff=open(flagp,O_RDONLY,0);
    if(ff>=0){ close(ff); seen=1; break; }
    if(g_elapsed_ms>=limit_ms) break;
    usleep(FRAME_US); g_elapsed_ms+=FRAME_MS;
    read_progress();
    advance_animation();
    present(rpx,rW,rH,rStride,rFmt,0,0);
  }
  lg(seen?">>> done-flag seen -> DONE after ":">>> timeout, no done-flag -> teardown after ");
  lgdec(g_elapsed_ms/1000); lg("s\n");

  if(seen && dpx){
    present(dpx,dW,dH,dStride,dFmt,"DONE",1);
    sleep((unsigned)hold);
  } else if(seen && !dpx){
    lg(">>> done-flag seen but DONE blob missing; holding RUNNING briefly\n");
    sleep((unsigned)hold);
  }

  /* ---- restore OEM screen, THEN unregister (no black) ---- */
  restore_oem();
  read_and_log_lmgr("after-restore");        /* diagnostic: confirm OEM cid is visible again */
  lg(">>> teardown: unregister...\n");
  ureg=(unsigned)cid; rc=devctl(fd,LMGR_UNREGISTER,&ureg,4,0); g_reg=0;
  lg("unregister rc="); lghx((unsigned)rc); lg("\n");
  sleep(1); close(fd);
  if(g_surf) gf_surface_free((void*)g_surf);
  gf_context_free((void*)ctx);
  lg("== forge_splash done ==\n");
  if(g_log>=0) close(g_log);
  return 0;
}
