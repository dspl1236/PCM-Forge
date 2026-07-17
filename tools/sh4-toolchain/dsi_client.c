/* ============================================================================
 * dsi_client.c -- full staged DSI input client for "KeyInput.SPHKeyInput".
 *
 * Joins the SPHKeyInput service as an EXTRA listener (the SAFE, multi-listener
 * path -- zero contention with PCM3Root, HMI untouched). Diagnostic-first: every
 * stage logs raw to USB (dsi_client.txt) and it subscribes to ALL candidate
 * updateId encodings, so ONE on-car run reveals the exact protocol + which id
 * carries touch vs key -- then we decode.
 *
 * Wire protocol PORTED from github.com/DSIHarman/DSI (DSI.hpp / CClient*.cpp):
 *   MessageHeader(40B) + [EventInfo(16B) for DataRequest] + body.
 *   ConnectRequest(cmd=9) body = ConnectRequestInfo{pid, channel=our chid}.
 *   Subscribe = DataRequest(cmd=7) + EventInfo{requestType=REQUEST_NOTIFY 0x0101,
 *   requestID=updateId}. Attribute ids live at 0xC0000000+ (descriptor showed
 *   0x2b-0x2e), so we try both encodings.
 *
 * Decode (from PCM3Root trace strings): TOUCH = x,y,type(0=move/2=press/3=release);
 *   KEY = keyCode,source,status,slider. We dump the raw payload + candidate
 *   int fields so a corner-touch calibrates the offsets on the car.
 *
 * Transport = QNX IPC (all in on-car libc.so.2, resolved via the stub-soname
 * trick -- same pipeline as chread/dsi_probe).
 * ==========================================================================*/

/* ---- libc (resolved to real libc.so.2 at load) ---- */
extern int open(const char*, int, ...);
extern int devctl(int, int, void*, unsigned, int*);
extern int write(int, const void*, int);
extern int close(int);
extern int getpid(void);
extern unsigned alarm(unsigned);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
/* ---- QNX Neutrino IPC ---- */
extern int ChannelCreate(unsigned flags);
extern int ChannelDestroy(int chid);
extern int ConnectAttach(unsigned nd, int pid, int chid, unsigned index, int flags);
extern int ConnectDetach(int coid);
extern int MsgSend(int coid, const void* smsg, int sbytes, void* rmsg, int rbytes);
extern int MsgReceive(int chid, void* msg, int bytes, void* info);
extern int MsgReply(int rcvid, int status, const void* msg, int bytes);

#define O_RDWR   2
#define O_WRONLY 1
#define O_CREAT  0x100
#define O_APPEND 0x008
#define SIGALRM  14
#define _NTO_SIDE_CHANNEL 0x40000000u

typedef unsigned short u16; typedef unsigned int u32; typedef int i32;
typedef unsigned long long u64; typedef unsigned char u8;

/* ---- servicebroker (from DSIHarman/DSI servicebroker.h) ---- */
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

/* ---- DSI wire (from DSI.hpp) ---- */
#define DSI_CMD_DATAREQ     7
#define DSI_CMD_CONNECT     9
#define DSI_CMD_DISCONNECT 10
#define DSI_REQUEST_NOTIFY 0x0101
#define DSI_HDR_TYPE 0            /* flush() zeroes type on the wire; flip to 0x200 if rejected */
#define DSI_PROTO_MAJOR 4
#define DSI_PROTO_MINOR 0
struct MessageHeader {            /* 40 bytes */
  i32 type; u16 protoMajor; u16 protoMinor;
  struct SPartyID serverID; struct SPartyID clientID;
  u32 cmd; u32 flags; u32 packetLength; i32 reserved;
};
struct ConnectRequestInfo { u32 pid; u32 channel; };            /* 8 bytes */
struct EventInfo { u32 ifVersion; u32 requestType; u32 requestID; i32 sequenceNumber; }; /* 16 */

/* ---- tiny libc ---- */
static int slen(const char*s){int n=0;while(s[n])n++;return n;}
static void zero(void*p,int n){char*c=(char*)p;while(n--)*c++=0;}
static void scopy(char*d,const char*s){while(*s)*d++=*s++;*d=0;}

static int g_usb=-1;
static void wr(const char*s){int n=slen(s);write(1,s,n);if(g_usb>=0)write(g_usb,s,n);}
static void wx(u32 v){char b[11];const char*h="0123456789abcdef";int i;b[0]='0';b[1]='x';
  for(i=0;i<8;i++)b[2+i]=h[(v>>((7-i)*4))&0xf];b[10]=0;write(1,b,10);if(g_usb>=0)write(g_usb,b,10);}
static void wd(int v){char b[12];int i=11,neg=0;b[11]=0;if(v<0){neg=1;v=-v;}
  if(v==0){wr("0");return;}while(v&&i){b[--i]='0'+v%10;v/=10;}if(neg&&i)b[--i]='-';
  int n=11-i;write(1,b+i,n);if(g_usb>=0)write(g_usb,b+i,n);}
static void dumphex(const u8*p,int n){int i;for(i=0;i<n;i++){wx(p[i]&0xff);/*compact*/ if((i&15)==15)wr("\n");else wr(" ");}if(n&15)wr("\n");}
/* dump buffer as bytes only (2-hex each) on one line, wrapping */
static void dumpb(const u8*p,int n){const char*h="0123456789abcdef";char line[3];line[2]=0;int i;
  for(i=0;i<n;i++){line[0]=h[(p[i]>>4)&0xf];line[1]=h[p[i]&0xf];write(1,line,2);if(g_usb>=0)write(g_usb,line,2);
    if((i&31)==31)wr("\n");else wr(" ");}if(n&31)wr("\n");}

/* ---- globals for teardown from signal ---- */
static int g_coid=-1, g_chid=-1;
static volatile int g_stop=0;
static void onalarm(int s){(void)s; g_stop=1;}

int main(int argc,char**argv){
  static const char*upaths[3]={"/fs/usb0/dsi_client.txt","/fs/usb1/dsi_client.txt","/fs/usb/dsi_client.txt"};
  const char*NAME="KeyInput.SPHKeyInput";
  union SFNDInterfaceAttachArg a;
  struct MessageHeader h;
  u8 sbuf[256], rbuf[4096], minfo[64];
  int fd,rc,info,i,coid,chid,mypid;
  u16 sbmaj[4]={4,3,2,1};
  struct SFNDChannelInfo prov; struct SPartyID srvID, cliID; struct SFNDInterfaceVersion ifv;
  (void)argc;(void)argv;

  for(i=0;i<3;i++){ g_usb=open(upaths[i],O_WRONLY|O_CREAT|O_APPEND,0666); if(g_usb>=0)break; }
  wr("==== dsi_client: KeyInput.SPHKeyInput ====\n");
  wr("DCMD_ATTACH="); wx((u32)DCMD_FND_ATTACH_INTERFACE); wr("\n");
  wr("wire sizes hdr="); wd(sizeof(struct MessageHeader)); wr(" evt="); wd(sizeof(struct EventInfo));
  wr(" cri="); wd(sizeof(struct ConnectRequestInfo)); wr(" party="); wd(sizeof(struct SPartyID));
  wr("  (expect 40/16/8/8)\n");

  /* --- STAGE A: attach via servicebroker --- */
  fd=open("/srv/servicebroker",O_RDWR);
  wr("open /srv/servicebroker fd="); wd(fd); wr("\n");
  if(fd<0){ wr(">>> broker open FAILED\n"); goto done; }
  rc=-1;
  for(i=0;i<4;i++){
    zero(&a,sizeof a);
    a.i.sbVersion.majorVersion=sbmaj[i]; a.i.sbVersion.minorVersion=0;
    a.i.ifDescription.version.majorVersion=0; a.i.ifDescription.version.minorVersion=0;
    scopy(a.i.ifDescription.name,NAME);
    info=0; rc=devctl(fd,DCMD_FND_ATTACH_INTERFACE,&a,sizeof a,&info);
    wr("attach sbVer="); wd(sbmaj[i]); wr(" rc="); wd(rc); wr(" info="); wd(info); wr("\n");
    if(rc==0) break;
  }
  if(rc!=0){ wr(">>> ATTACH FAILED (provider not up?)\n"); goto done; }
  prov=a.o.channel; srvID=a.o.serverID; cliID=a.o.clientID; ifv=a.o.ifVersion;
  wr(">>> ATTACH OK  ifVer="); wd(ifv.majorVersion); wr("."); wd(ifv.minorVersion);
  wr("  provider nid="); wx(prov.nid); wr(" pid="); wd(prov.pid); wr(" chid="); wd(prov.chid); wr("\n");
  wr("    serverID="); wx((u32)srvID.s.localID); wr("/"); wx((u32)srvID.s.extendedID);
  wr("  clientID="); wx((u32)cliID.s.localID); wr("/"); wx((u32)cliID.s.extendedID); wr("\n");
  wr("    raw attach reply: "); dumpb((u8*)&a.o,sizeof(a.o));

  /* --- STAGE B: our receive channel + connect to provider --- */
  chid=ChannelCreate(0); g_chid=chid;
  wr("ChannelCreate chid="); wd(chid); wr("\n");
  if(chid<0){ wr(">>> ChannelCreate FAILED\n"); goto done; }
  coid=ConnectAttach(prov.nid, prov.pid, prov.chid, _NTO_SIDE_CHANNEL, 0); g_coid=coid;
  wr("ConnectAttach(nid="); wx(prov.nid); wr(") coid="); wd(coid); wr("\n");
  if(coid<0 && prov.nid!=0){ /* local providers often report nid=0 */
    coid=ConnectAttach(0, prov.pid, prov.chid, _NTO_SIDE_CHANNEL, 0); g_coid=coid;
    wr("ConnectAttach(nid=0) coid="); wd(coid); wr("\n");
  }
  if(coid<0){ wr(">>> ConnectAttach FAILED\n"); goto done; }
  mypid=getpid();

  /* --- STAGE C: ConnectRequest (announce our channel so notifications flow) --- */
  {
    zero(&h,sizeof h);
    h.type=DSI_HDR_TYPE; h.protoMajor=DSI_PROTO_MAJOR; h.protoMinor=DSI_PROTO_MINOR;
    h.serverID=srvID; h.clientID=cliID; h.cmd=DSI_CMD_CONNECT;
    h.packetLength=sizeof(struct ConnectRequestInfo);
    struct ConnectRequestInfo cri; cri.pid=(u32)mypid; cri.channel=(u32)chid;
    zero(sbuf,sizeof sbuf);
    for(i=0;i<(int)sizeof h;i++) sbuf[i]=((u8*)&h)[i];
    for(i=0;i<(int)sizeof cri;i++) sbuf[sizeof h+i]=((u8*)&cri)[i];
    int slen2=sizeof h+sizeof cri;
    zero(rbuf,64);
    rc=MsgSend(coid,sbuf,slen2,rbuf,sizeof rbuf);
    wr("ConnectRequest MsgSend rc="); wd(rc); wr("  (pid="); wd(mypid); wr(" chid="); wd(chid); wr(")\n");
    wr("    connect reply: "); dumpb(rbuf,64);
  }

  /* --- STAGE D: subscribe to candidate updateIds (both encodings) --- */
  {
    u32 cands[8]={0x2b,0x2c,0x2d,0x2e, 0xC000002b,0xC000002c,0xC000002d,0xC000002e};
    int k;
    for(k=0;k<8;k++){
      zero(&h,sizeof h);
      h.type=DSI_HDR_TYPE; h.protoMajor=DSI_PROTO_MAJOR; h.protoMinor=DSI_PROTO_MINOR;
      h.serverID=srvID; h.clientID=cliID; h.cmd=DSI_CMD_DATAREQ;
      h.packetLength=sizeof(struct EventInfo);
      struct EventInfo ei; zero(&ei,sizeof ei);
      ei.ifVersion=((u32)ifv.majorVersion<<16)|(u32)ifv.minorVersion;
      ei.requestType=DSI_REQUEST_NOTIFY; ei.requestID=cands[k]; ei.sequenceNumber=k+1;
      zero(sbuf,sizeof sbuf);
      for(i=0;i<(int)sizeof h;i++) sbuf[i]=((u8*)&h)[i];
      for(i=0;i<(int)sizeof ei;i++) sbuf[sizeof h+i]=((u8*)&ei)[i];
      zero(rbuf,32);
      rc=MsgSend(coid,sbuf,sizeof h+sizeof ei,rbuf,sizeof rbuf);
      wr("subscribe updateId="); wx(cands[k]); wr(" rc="); wd(rc); wr("  reply: "); dumpb(rbuf,16);
    }
  }

  /* --- STAGE E: receive loop -- dump every notification + decode candidates --- */
  wr("---- receive loop (25s; touch the screen + press hardkeys) ----\n");
  signal(SIGALRM,onalarm); alarm(25);
  while(!g_stop){
    zero(minfo,sizeof minfo);
    int rcvid=MsgReceive(chid, rbuf, sizeof rbuf, minfo);
    if(rcvid<0){ wr("MsgReceive rc<0 (timeout/eintr) -> stop\n"); break; }
    /* log raw */
    wr("MSG rcvid="); wd(rcvid); wr(" : ");
    dumpb(rbuf, 96);
    /* decode: header@0, EventInfo@40, payload@56 */
    if(1){
      struct MessageHeader*rh=(struct MessageHeader*)rbuf;
      wr("   cmd="); wd((int)rh->cmd); wr(" pktLen="); wd((int)rh->packetLength); wr("\n");
      struct EventInfo*rei=(struct EventInfo*)(rbuf+40);
      wr("   evt.reqID="); wx(rei->requestID); wr(" reqType="); wx(rei->requestType);
      wr(" seq="); wd(rei->sequenceNumber); wr("\n");
      /* candidate payload ints (touch x/y/type or key fields) */
      u8*pl=rbuf+56;
      u32*w=(u32*)pl; u16*hw=(u16*)pl;
      wr("   payload u32[0..5]="); { int j; for(j=0;j<6;j++){ wx(w[j]); wr(" "); } } wr("\n");
      wr("   payload u16[0..7]="); { int j; for(j=0;j<8;j++){ wd(hw[j]); wr(" "); } } wr("\n");
    }
    if(rcvid>0) MsgReply(rcvid,0,0,0);
  }

done:
  wr("---- teardown ----\n");
  if(g_coid>=0){
    /* best-effort DisconnectRequest */
    zero(&h,sizeof h); h.type=DSI_HDR_TYPE; h.protoMajor=DSI_PROTO_MAJOR; h.protoMinor=DSI_PROTO_MINOR;
    h.serverID=srvID; h.clientID=cliID; h.cmd=DSI_CMD_DISCONNECT; h.packetLength=0;
    zero(rbuf,16); MsgSend(g_coid,&h,sizeof h,rbuf,16);
    ConnectDetach(g_coid);
  }
  if(g_chid>=0) ChannelDestroy(g_chid);
  if(fd>=0) close(fd);
  wr("==== dsi_client done ====\n");
  if(g_usb>=0) close(g_usb);
  return 0;
}
