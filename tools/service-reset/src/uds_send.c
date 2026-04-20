/*
 * uds_send.c — Send UDS diagnostic frames via NDR CAN bus
 *
 * Target:  QNX 6.3.2 / Renesas SH4A (SH7785)
 * Build:   sh4-linux-gnu-gcc-14 -c -O2 -fPIC -ffreestanding -nostdlib
 *              -o uds_send.o uds_send.c
 *          (link on target: /usr/bin/ld -o uds_send uds_send.o -lc)
 *
 * Usage:   uds_send <ecu_addr> <byte0> [byte1] [byte2] ...
 *
 * Examples:
 *   uds_send 0x17 0x10 0x03             -> Extended session to cluster
 *   uds_send 0x17 0x2E 0x01 0x56 0x00   -> WriteDID 0x0156 = reset ESI
 *   uds_send 0x17 0x2E 0x0D 0x17 0x00   -> WriteDID 0x0D17 = distance=0
 *   uds_send 0x17 0x2E 0x0D 0x18 0x00   -> WriteDID 0x0D18 = time=0
 *
 * Communication path:
 *   uds_send -> devctl(/dev/ndr/cmd) -> NDR -> IOC -> CAN -> ECU
 *
 * devctl interface reverse-engineered from PCM3Root CLibResMgr
 * and NDR resource manager binary via Ghidra:
 *   - NDR class = 0x20, cmd = 8
 *   - Write: __DIOT(0x20, 8, msg_size) = 0x8000_2008 | (size << 16)
 *   - Read:  __DIOF(0x20, 8, msg_size) = 0x4000_2008 | (size << 16)
 *   - Bidir: __DIOTF(0x20, 8, size)    = 0xC000_2008 | (size << 16)
 *
 * Part of PCM-Forge: github.com/dspl1236/PCM-Forge
 */

/* System calls — link against QNX libc on target */
extern int open(const char *path, int oflag, ...);
extern int close(int fd);
extern int write(int fd, const void *buf, unsigned nbytes);
extern int read(int fd, void *buf, unsigned nbytes);
extern int devctl(int fd, int dcmd, void *data, unsigned nbytes, int *info);
extern unsigned sleep(unsigned seconds);

/* QNX devctl macros (from <devctl.h>) — cast to unsigned for 32-bit */
#define __DION(c,cm)     (int)(((c)<<8)|(cm))
#define __DIOF(c,cm,sz)  (int)((1U<<30)|((sz)<<16)|((c)<<8)|(cm))
#define __DIOT(c,cm,sz)  (int)((2U<<30)|((sz)<<16)|((c)<<8)|(cm))
#define __DIOTF(c,cm,sz) (int)((3U<<30)|((sz)<<16)|((c)<<8)|(cm))

/* NDR devctl commands (from Ghidra RE of ndr binary + PCM3Root) */
#define NDR_CLASS  0x20
#define NDR_CMD    8
#define NDR_WRITE(sz)  __DIOT(NDR_CLASS, NDR_CMD, (sz))
#define NDR_READ(sz)   __DIOF(NDR_CLASS, NDR_CMD, (sz))
#define NDR_XFER(sz)   __DIOTF(NDR_CLASS, NDR_CMD, (sz))

#define O_RDWR 2

/*
 * NDR message structure for UDS/CAN transport.
 * Reconstructed from CLibResMgr and IOC string analysis.
 * The msg_type field selects the transport mode.
 * target_addr is the CAN arbitration ID.
 */
struct ndr_msg {
    unsigned short msg_type;    /* 0x0001 = diagnostic request */
    unsigned short target_addr; /* CAN ID (0x714 for cluster request) */
    unsigned short data_len;    /* UDS payload byte count */
    unsigned char  data[64];    /* UDS payload */
};

static int hex(const char *s)
{
    int v = 0;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X'))
        s += 2;
    while (*s) {
        v <<= 4;
        if (*s >= '0' && *s <= '9')      v |= *s - '0';
        else if (*s >= 'a' && *s <= 'f')  v |= *s - 'a' + 10;
        else if (*s >= 'A' && *s <= 'F')  v |= *s - 'A' + 10;
        s++;
    }
    return v;
}

static void out(const char *s)
{
    int n = 0;
    while (s[n]) n++;
    write(1, s, n);
}

static void err(const char *s)
{
    int n = 0;
    while (s[n]) n++;
    write(2, s, n);
}

static void hex2(unsigned char b)
{
    char h[2];
    h[0] = "0123456789ABCDEF"[(b >> 4) & 0xF];
    h[1] = "0123456789ABCDEF"[b & 0xF];
    write(1, h, 2);
}

int main(int argc, char **argv)
{
    struct ndr_msg msg;
    struct ndr_msg resp;
    int fd, ret, i, ecu_addr, msg_size;

    if (argc < 3) {
        out("uds_send - PCM-Forge UDS diagnostic tool\n");
        out("Usage: uds_send <ecu> <byte0> [byte1...]\n\n");
        out("Oil service reset:\n");
        out("  uds_send 0x17 0x10 0x03\n");
        out("  uds_send 0x17 0x2E 0x01 0x56 0x00\n");
        out("Distance reset:\n");
        out("  uds_send 0x17 0x2E 0x0D 0x17 0x00 0x00\n");
        out("Time reset:\n");
        out("  uds_send 0x17 0x2E 0x0D 0x18 0x00 0x00\n");
        return 1;
    }

    ecu_addr = hex(argv[1]);

    /* Build message */
    msg.msg_type    = 0x0001;
    msg.target_addr = 0x0700 + (ecu_addr & 0xFF);
    msg.data_len    = 0;

    for (i = 2; i < argc && msg.data_len < 64; i++)
        msg.data[msg.data_len++] = (unsigned char)hex(argv[i]);

    for (i = msg.data_len; i < 64; i++)
        msg.data[i] = 0;

    msg_size = 6 + msg.data_len;

    /* Open NDR */
    fd = open("/dev/ndr/cmd", O_RDWR, 0);
    if (fd < 0) {
        err("ERR: open /dev/ndr/cmd failed\n");
        return 2;
    }

    /* Log frame */
    out("-> ");
    for (i = 0; i < (int)msg.data_len; i++) {
        hex2(msg.data[i]);
        out(" ");
    }
    out("@ CAN ");
    hex2((msg.target_addr >> 8) & 0xFF);
    hex2(msg.target_addr & 0xFF);
    out("\n");

    /* Try DIOT (write to device) — primary CLibResMgr::ndrWrite path */
    ret = devctl(fd, NDR_WRITE(msg_size), &msg, msg_size, 0);
    if (ret == 0) {
        out("OK (DIOT)\n");
        close(fd);
        return 0;
    }

    /* Try DIOTF (bidirectional) */
    for (i = 0; i < (int)sizeof(resp); i++)
        ((unsigned char*)&resp)[i] = ((unsigned char*)&msg)[i < msg_size ? i : 0];

    ret = devctl(fd, NDR_XFER(sizeof(resp)), &resp, sizeof(resp), 0);
    if (ret == 0) {
        out("OK (DIOTF)\n");
        if (resp.data_len > 0 && resp.data_len < 32) {
            out("<- ");
            for (i = 0; i < (int)resp.data_len; i++) {
                hex2(resp.data[i]);
                out(" ");
            }
            out("\n");
            if (resp.data[0] == 0x7F) {
                err("NRC: 0x");
                hex2(resp.data[2]);
                err("\n");
            }
        }
        close(fd);
        return 0;
    }

    /* Try simple DION (no data direction, just command) */
    ret = devctl(fd, __DION(NDR_CLASS, NDR_CMD), &msg, msg_size, 0);
    if (ret == 0) {
        out("OK (DION)\n");
        close(fd);
        return 0;
    }

    err("ERR: All devctl modes failed\n");
    close(fd);
    return ret;
}
