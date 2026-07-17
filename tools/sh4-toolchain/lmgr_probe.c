/* ============================================================================
 * lmgr_probe.c  --  minimal PCM 3.1 layermanager probe (QNX SH4)
 * Reimplements the cooperative connect + register-displayable path as RAW devctl
 * (reverse-engineered from PCM3Browser's lmgr client):
 *   open("/dev/layermanager")
 *   devctl(fd, 0xc00c0506, msg12, 12)   Connect;  reply[0],[1]==1,1 => connected
 *   devctl(fd, 0xc0140500, msg20, 20)   Register; msg[4]!=0 => LAYER GRANTED
 * No libc heap/stdio/TLS, only syscall wrappers, so it can run on a bare crt.
 * Answers on real hardware: does our cross-build RUN, and is a 2nd layer FREE?
 * ==========================================================================*/
extern int  open(const char *path, int oflag, ...);
extern int  devctl(int fd, int dcmd, void *data, unsigned nbytes, int *info);
extern int  write(int fd, const void *buf, int n);
extern int  close(int fd);

#define O_RDWR        2
#define LMGR_CONNECT  0xc00c0506u   /* class 5, code 6, 12-byte, TOFROM */
#define LMGR_REGISTER 0xc0140500u   /* class 5, code 0, 20-byte, TOFROM */
#define LMGR_GETVFB   0xc0100503u   /* class 5, code 3, 16-byte, TOFROM */

static void put(const char *s){ int n=0; while(s[n])n++; write(1,s,n); }
static void hex(unsigned v){
    char b[11]; const char *h="0123456789abcdef"; int i;
    b[0]='0'; b[1]='x'; for(i=0;i<8;i++) b[2+i]=h[(v>>((7-i)*4))&0xf]; b[10]=0;
    write(1,b,10);
}

int main(int argc, char **argv)
{
    unsigned cmsg[3];               /* connect  msg (12 bytes) */
    unsigned rmsg[5];               /* register msg (20 bytes) */
    unsigned gmsg[4];               /* getvfb   msg (16 bytes): {cid, sid, ?, ?} */
    int fd, rc;

    put("== lmgr_probe: cross-build RAN ==\n");   /* if you see this, the crt works */

    fd = open("/dev/layermanager", O_RDWR);
    put("open /dev/layermanager fd="); hex((unsigned)fd); put("\n");
    if (fd < 0) { put("OPEN FAILED (device missing or busy)\n"); return 1; }

    cmsg[0]=0; cmsg[1]=0; cmsg[2]=0;
    rc = devctl(fd, LMGR_CONNECT, cmsg, sizeof cmsg, 0);
    put("connect devctl rc="); hex((unsigned)rc);
    put(" reply=["); hex(cmsg[0]); put(" "); hex(cmsg[1]); put("]\n");

    rmsg[0]=0x5000; rmsg[1]=480; rmsg[2]=240; rmsg[3]=0; rmsg[4]=0;  /* cid,w,h,flags,result */
    rc = devctl(fd, LMGR_REGISTER, rmsg, sizeof rmsg, 0);
    put("register devctl rc="); hex((unsigned)rc);
    put(" result="); hex(rmsg[4]); put("\n");

    if (rc==0 && rmsg[4]!=0) {
        put(">>> LAYER GRANTED — cooperative GUI is FEASIBLE\n");
        /* one more rung: grab the virtual framebuffer surface (last step before pixels) */
        gmsg[0]=0x5000; gmsg[1]=0; gmsg[2]=0; gmsg[3]=0;      /* {cid, out0, out1, out2} */
        rc = devctl(fd, LMGR_GETVFB, gmsg, sizeof gmsg, 0);
        put("getvfb devctl rc="); hex((unsigned)rc);
        put(" sid="); hex(gmsg[1]); put(" ["); hex(gmsg[2]); put(" "); hex(gmsg[3]); put("]\n");
        if (rc==0 && gmsg[1]!=0) put(">>> GOT FRAMEBUFFER (sid) — ready to draw pixels\n");
    }
    else if (rc==0)          put(">>> NO FREE LAYER — both held (result=0)\n");
    else                     put(">>> devctl error (connect/register rejected)\n");

    close(fd);
    put("== probe done ==\n");
    return 0;
}
