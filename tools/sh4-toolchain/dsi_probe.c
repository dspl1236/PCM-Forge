/* ============================================================================
 * dsi_probe.c -- attach to the "KeyInput.SPHKeyInput" service via the DSI
 * servicebroker (/srv/servicebroker). Step 1 of the touch-input client.
 *
 * Protocol PORTED VERBATIM from open source github.com/DSIHarman/DSI (Harman's
 * own DSI middleware): platform.h (__DIOTF, _DCMD_MISC=0x05), servicebroker.h
 * (structs + DCMD_FND_ATTACH_INTERFACE), version.h (SFNDInterfaceVersion=2xu16,
 * DSI_SERVICEBROKER_VERSION 4.0). Uses only open+devctl (proven on this PCM).
 *
 * Goal: does the broker respond + return a provider {nid,pid,chid} for
 * KeyInput.SPHKeyInput? Tries several protocol versions since the on-car DSI
 * predates the 4.0 repo. Logs everything to USB dsi_probe.txt.
 * ==========================================================================*/
extern int open(const char*, int, ...);
extern int devctl(int, int, void*, unsigned, int*);
extern int write(int, const void*, int);
extern int close(int);

#define O_RDWR   2
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_APPEND 0x008

/* ---- QNX + DSI types/macros (from DSIHarman/DSI) ---- */
typedef unsigned short u16; typedef unsigned int u32; typedef int i32; typedef unsigned long long u64;
#define NAME_MAX 255
#define _DCMD_MISC 0x05
#define __DIOTF(kind,cmd,data) ((int)((sizeof(data)<<16)+((kind)<<8)+(cmd)+0xC0000000))

struct SFNDInterfaceVersion { u16 majorVersion; u16 minorVersion; };
struct SFNDInterfaceDescription { struct SFNDInterfaceVersion version; char name[NAME_MAX+1]; };
struct SFNDChannelInfo { u32 nid; i32 pid; i32 chid; };
struct SPartyID { union { struct { u32 localID; u32 extendedID; } s; u64 globalID; } __attribute__((aligned(8))); };
struct SConnectionInfo {
  struct SFNDInterfaceVersion ifVersion;
  struct SFNDChannelInfo channel;
  struct SPartyID serverID;
  struct SPartyID clientID;
};
union SFNDInterfaceAttachArg {
  struct { struct SFNDInterfaceVersion sbVersion; struct SFNDInterfaceDescription ifDescription; } i;
  struct SConnectionInfo o;
};
#define DCMD_FND_ATTACH_INTERFACE __DIOTF(_DCMD_MISC,2,union SFNDInterfaceAttachArg)

static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static void zero(void*p,int n){char*c=(char*)p;while(n--)*c++=0;}
static void scopy(char*d,const char*s){while(*s)*d++=*s++;*d=0;}

/* logging: to stdout AND usb file */
static void wr(int fd,const char*s){write(fd,s,slen(s));}
static void whex(int fd,u32 v){char b[11];const char*h="0123456789abcdef";int i;
  b[0]='0';b[1]='x';for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(fd,b,10);}
static void wdec(int fd,int v){char b[12];int i=11,neg=0;b[11]=0;if(v<0){neg=1;v=-v;}
  if(v==0){write(fd,"0",1);return;} while(v&&i){b[--i]='0'+v%10;v/=10;} if(neg&&i)b[--i]='-'; write(fd,b+i,11-i);}

static int g_usb=-1;
static void L(const char*s){ wr(1,s); if(g_usb>=0) wr(g_usb,s); }
static void LX(u32 v){ whex(1,v); if(g_usb>=0) whex(g_usb,v); }
static void LD(int v){ wdec(1,v); if(g_usb>=0) wdec(g_usb,v); }

int main(int argc,char**argv){
  static const char*upaths[3]={"/fs/usb0/dsi_probe.txt","/fs/usb1/dsi_probe.txt","/fs/usb/dsi_probe.txt"};
  union SFNDInterfaceAttachArg a;
  int fd,rc,info,i;
  u16 sbmaj[4]={4,3,2,1};
  const char*NAME="KeyInput.SPHKeyInput";

  for(i=0;i<3;i++){ g_usb=open(upaths[i],O_WRONLY|O_CREAT|O_APPEND,0666); if(g_usb>=0)break; }

  L("== dsi_probe: attach KeyInput.SPHKeyInput ==\n");
  L("DCMD_FND_ATTACH_INTERFACE="); LX((u32)DCMD_FND_ATTACH_INTERFACE);
  L("  argsize="); LD((int)sizeof(union SFNDInterfaceAttachArg)); L("\n");

  fd=open("/srv/servicebroker",O_RDWR);
  L("open /srv/servicebroker fd="); LD(fd); L("\n");
  if(fd<0){ L(">>> broker open FAILED\n"); if(g_usb>=0)close(g_usb); return 1; }

  for(i=0;i<4;i++){
    zero(&a,sizeof a);
    a.i.sbVersion.majorVersion=sbmaj[i]; a.i.sbVersion.minorVersion=0;
    a.i.ifDescription.version.majorVersion=0; a.i.ifDescription.version.minorVersion=0; /* any */
    scopy(a.i.ifDescription.name,NAME);
    info=0;
    rc=devctl(fd,DCMD_FND_ATTACH_INTERFACE,&a,sizeof a,&info);
    L("attach sbVer="); LD(sbmaj[i]); L(".0  rc="); LD(rc); L(" info="); LD(info);
    L("  -> nid="); LD((int)a.o.channel.nid); L(" pid="); LX((u32)a.o.channel.pid);
    L(" chid="); LD(a.o.channel.chid); L(" serverID="); LX((u32)a.o.serverID.s.localID);
    L("\n");
    if(rc==0){ L(">>> ATTACH OK at sbVer "); LD(sbmaj[i]); L(".0 -- provider found!\n"); break; }
  }
  close(fd);
  L("== dsi_probe done ==\n");
  if(g_usb>=0)close(g_usb);
  return 0;
}
