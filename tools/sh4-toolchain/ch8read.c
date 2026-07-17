/* ============================================================================
 * ch8read.c -- read the Harman input stream off /dev/ipc/ioc/ch8 directly.
 * No overlay, no layermanager (zero snow risk). The PCM has no dd/cat-that-works,
 * so we open + read() ourselves and append every frame straight to the USB
 * (flush per read, so nothing is lost if the stick is pulled). alarm() bounds it.
 * Goal: prove touch/key frames are readable, and capture them to decode coords.
 * ==========================================================================*/
extern int  open(const char*, int, ...);
extern int  read(int, void*, unsigned);
extern int  write(int, const void*, int);
extern int  close(int);
extern unsigned alarm(unsigned);
extern void _exit(int);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);

#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_APPEND 0x008
#define SIGALRM  14
#define RUN_SECS 15

static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static void put(const char*s){write(1,s,slen(s));}
static void dec(int v){char b[12];int i=11;b[11]=0;if(v==0){put("0");return;}
  while(v&&i){b[--i]='0'+v%10;v/=10;}put(b+i);}
static void hx2(unsigned char v){const char*h="0123456789abcdef";char b[3];b[0]=h[v>>4];b[1]=h[v&0xf];b[2]=' ';write(1,b,3);}

static int g_fd=-1, g_total=0, g_frames=0;

static void appendbin(const char*b,int n){
  static const char*paths[3]={"/fs/usb0/ch8_touch.bin","/fs/usb1/ch8_touch.bin","/fs/usb/ch8_touch.bin"};
  int i,f; for(i=0;i<3;i++){ f=open(paths[i],O_WRONLY|O_CREAT|O_APPEND,0666);
    if(f>=0){ write(f,b,n); close(f); return; } }
}
static void report(void){
  put("\n>>> ch8 result: "); dec(g_total); put(" bytes in "); dec(g_frames);
  put(" reads -> ch8_touch.bin\n");
  if(g_total>0) put(">>> INPUT IS READABLE. decode the .bin for coords/keycodes.\n");
  else          put(">>> no frames (needs a registration handshake, or wrong channel).\n");
}
static void onalarm(int s){ (void)s; put("\n[timeout] "); report(); if(g_fd>=0)close(g_fd); _exit(0); }

int main(int c,char**v){
  char buf[64]; int n, errs=0, i;
  put("== ch8read: open /dev/ipc/ioc/ch8 ==\n");
  g_fd=open("/dev/ipc/ioc/ch8",O_RDONLY);
  put("open fd="); dec(g_fd); put("\n");
  if(g_fd<0){ put(">>> OPEN FAILED\n"); return 1; }
  put(">>> ch8 open OK -- TOUCH the screen (corners, center) + press MEDIA for 15s\n");
  signal(SIGALRM,onalarm); alarm(RUN_SECS);
  for(;;){
    n=read(g_fd,buf,sizeof buf);
    if(n>0){
      appendbin(buf,n); g_total+=n; g_frames++; errs=0;
      put("frame "); dec(g_frames); put(" ("); dec(n); put("B): ");
      for(i=0;i<n && i<16;i++) hx2((unsigned char)buf[i]);
      put("\n");
      if(g_frames>=1000) break;
    } else {
      /* n<=0: either a fast error-spin (read unsupported) or EINTR from alarm */
      if(++errs>20000){ put(">>> read returns no data quickly -- ch8 not deliverable via plain read()\n"); break; }
    }
  }
  report(); if(g_fd>=0)close(g_fd);
  put("== ch8read done ==\n");
  return 0;
}
