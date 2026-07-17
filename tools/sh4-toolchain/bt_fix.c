/* ============================================================================
 * bt_fix.c -- UNIVERSAL self-locating BT/FM-boot patcher for PCM 3.1 (SH4/QNX).
 *
 * The AUX/BT "defaults to FM on startup" bug is a single instruction in PCM3Root
 * that writes the FM source-index (1) into the BT source descriptor. That
 * instruction carries a UNIQUE 6-byte signature that is byte-identical across
 * every region/model/facelift build that has the bug (v2.00 -> v4.00) -- only its
 * ADDRESS moves. So instead of a per-version address, we find it by signature in
 * the *running* PCM3Root via /proc/<pid>/as and flip the index 1 (FM) -> 7 (A2DP).
 *
 * Runtime patch = reboot-to-undo (no flash, no IFS repack -> cannot brick).
 * FAIL-SAFE: writes ONLY when EXACTLY one signature match is found AND the current
 * byte is 0x01. 0 matches (e.g. v1.00, which lacks this code) or >1 -> NO CHANGE.
 * Dry-run by default; --apply to write; --revert to undo (07 -> 01).
 *
 * Usage:  bt_fix <pid> [--apply | --revert]
 *   (get pid with: pidin | grep PCM3Root   -- or use bt_run.sh)
 *
 * Signature (SH4 LE): mov.l r?,@(5,Rn); mov #1,r1; mov.l r1,@(5,Rn)
 *   = 05 1e  01 e1  15 1e   (the 01 at +2 is the FM index we flip to 07)
 * ==========================================================================*/
extern int  open(const char*, int, ...);
extern int  close(int);
extern int  read(int, void*, unsigned);
extern int  write(int, const void*, int);
extern long lseek(int, long, int);

#define O_RDONLY 0
#define O_RDWR   2
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_APPEND 0x008
#define SEEK_SET 0

typedef unsigned char u8; typedef unsigned int u32;

static const u8 SIG[6] = {0x05,0x1e,0x01,0xe1,0x15,0x1e};
#define SIG_LEN  6
#define IMM_OFF  2          /* the 0x01/0x07 byte inside the signature */
#define FM_IDX   0x01
#define A2DP_IDX 0x07

/* scan only PCM3Root's own image (EXEC, non-PIE -> loaded at its ELF vaddr).
 * shared libs live elsewhere, so this range keeps the signature unique. */
#define CODE_LO  0x08040000u
#define CODE_HI  0x08700000u
#define CHUNK    65536
#define OVER     8

/* ---- tiny libc + logging (stdout + USB) ---- */
static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static int g_usb=-1;
static void wr(const char*s){int n=slen(s);write(1,s,n);if(g_usb>=0)write(g_usb,s,n);}
static void wx(u32 v){char b[11];const char*h="0123456789abcdef";int i;b[0]='0';b[1]='x';
  for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(1,b,10);if(g_usb>=0)write(g_usb,b,10);}
static void wb(u8 v){char b[5];const char*h="0123456789abcdef";b[0]='0';b[1]='x';
  b[2]=h[(v>>4)&0xf];b[3]=h[v&0xf];b[4]=0;write(1,b,4);if(g_usb>=0)write(g_usb,b,4);}
static void wd(int v){char b[12];int i=11,neg=0;b[11]=0;if(v<0){neg=1;v=-v;}
  if(v==0){wr("0");return;}while(v&&i){b[--i]='0'+v%10;v/=10;}if(neg&&i)b[--i]='-';
  int n=11-i;write(1,b+i,n);if(g_usb>=0)write(g_usb,b+i,n);}

static int atoiu(const char*s){int v=0;if(!s)return 0;while(*s>='0'&&*s<='9'){v=v*10+(*s-'0');s++;}return v;}
static int streq(const char*a,const char*b){if(!a||!b)return 0;while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int match6(const u8*p){int i;for(i=0;i<SIG_LEN;i++)if(p[i]!=SIG[i])return 0;return 1;}

int main(int argc,char**argv){
  static const char*upaths[3]={"/fs/usb0/bt_fix.txt","/fs/usb1/bt_fix.txt","/fs/usb/bt_fix.txt"};
  static u8 buf[CHUNK+OVER];
  char path[40];
  int i,fd,pid,apply=0,revert=0,matches=0,n; u32 base,match_va=0,imm_va; u8 cur=0,rb=0;

  for(i=0;i<3;i++){ g_usb=open(upaths[i],O_WRONLY|O_CREAT|O_APPEND,0666); if(g_usb>=0)break; }
  wr("==== PCM-Forge bt_fix (universal FM->BT boot patcher) ====\n");

  pid=atoiu(argc>1?argv[1]:0);
  if(argc>2){ if(streq(argv[2],"--apply"))apply=1; else if(streq(argv[2],"--revert"))revert=1; }
  if(pid<=0){ wr("usage: bt_fix <pid> [--apply|--revert]   (pidin | grep PCM3Root)\n");
              if(g_usb>=0)close(g_usb); return 1; }
  wr("pid="); wd(pid); wr(apply?"  mode=APPLY\n":(revert?"  mode=REVERT\n":"  mode=DRY-RUN (no write)\n"));

  /* build /proc/<pid>/as */
  { const char*a="/proc/"; const char*b="/as"; char num[12]; int k=0,j=0,t; int p=pid;
    while(a[j]){path[j]=a[j];j++;} { int q=p,c=0; char tmp[12]; if(q==0)num[k++]='0';
      while(q){tmp[c++]='0'+q%10;q/=10;} while(c)num[k++]=tmp[--c]; } for(t=0;t<k;t++)path[j++]=num[t];
    { int z=0; while(b[z])path[j++]=b[z++]; } path[j]=0; }
  wr("open "); wr(path); wr(" ...\n");
  fd=open(path,(apply||revert)?O_RDWR:O_RDONLY);
  if(fd<0){ wr(">>> open FAILED (wrong pid? not root?) -> NO CHANGE\n"); if(g_usb>=0)close(g_usb); return 2; }

  /* scan PCM3Root's code range for the unique signature */
  for(base=CODE_LO; base<CODE_HI; base+=CHUNK){
    if(lseek(fd,(long)base,SEEK_SET)<0) continue;
    n=read(fd,buf,CHUNK+OVER);
    if(n<SIG_LEN) continue;
    int lim=n-SIG_LEN+1; if(lim>CHUNK) lim=CHUNK;
    for(i=0;i<lim;i++){
      if(match6(buf+i)){ matches++; if(matches==1) match_va=base+(u32)i; }
    }
  }
  wr("signature matches in PCM3Root code = "); wd(matches); wr("\n");

  if(matches==0){ wr(">>> signature NOT found (unsupported build / v1.00 lacks this code) -> NO CHANGE (safe)\n"); goto done; }
  if(matches>1){ wr(">>> AMBIGUOUS (>1 match) -> ABORT, NO CHANGE (safe)\n"); goto done; }

  imm_va=match_va+IMM_OFF;
  wr("FM-map found @ vaddr="); wx(match_va); wr("  index byte @ "); wx(imm_va); wr("\n");
  lseek(fd,(long)imm_va,SEEK_SET); read(fd,&cur,1);
  wr("current index byte = "); wb(cur); wr(cur==FM_IDX?"  (FM)\n":(cur==A2DP_IDX?"  (A2DP - already patched)\n":"  (UNEXPECTED)\n"));

  if(revert){
    if(cur==A2DP_IDX){ lseek(fd,(long)imm_va,SEEK_SET); write(fd,(u8[]){FM_IDX},1);
      lseek(fd,(long)imm_va,SEEK_SET); read(fd,&rb,1); wr(">>> REVERTED 07->01, readback="); wb(rb); wr("\n"); }
    else wr(">>> not patched (byte!=07) -> NO CHANGE\n");
  } else if(apply){
    if(cur==FM_IDX){ lseek(fd,(long)imm_va,SEEK_SET); write(fd,(u8[]){A2DP_IDX},1);
      lseek(fd,(long)imm_va,SEEK_SET); read(fd,&rb,1);
      wr(rb==A2DP_IDX?">>> APPLIED 01->07 (BT now routes to A2DP). readback=":">>> WRITE FAILED readback="); wb(rb); wr("\n");
      wr("    (reboot to undo, or run --revert)\n"); }
    else if(cur==A2DP_IDX) wr(">>> already patched -> NO CHANGE\n");
    else wr(">>> UNEXPECTED byte -> ABORT, NO CHANGE (safe)\n");
  } else {
    if(cur==FM_IDX) wr(">>> DRY-RUN: would flip 01->07 here. Re-run with --apply to do it.\n");
    else if(cur==A2DP_IDX) wr(">>> already patched (07). Nothing to do.\n");
    else wr(">>> UNEXPECTED byte -> would ABORT (safe).\n");
  }
done:
  close(fd);
  wr("==== bt_fix done ====\n");
  if(g_usb>=0)close(g_usb);
  return 0;
}
