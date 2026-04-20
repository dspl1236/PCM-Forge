/*
 * uds_send.c — Send UDS frames to ECU via PCM 3.1 IOC CAN bus
 * Target: QNX 6.3.2, SH4A (SH7785)
 * Part of PCM-Forge: github.com/dspl1236/PCM-Forge
 *
 * Usage: uds_send <module> <service> [data bytes...]
 *   uds_send 0x17 0x10 0x03           → ExtendedDiagSession to cluster
 *   uds_send 0x17 0x2E 0xAB 0xCD 0x00 → WriteDID 0xABCD=0x00 to cluster
 *
 * Path: uds_send → devctl(/dev/ndr/cmd) → NDR → IOC → CAN → ECU
 *
 * TODO: devctl() cmd codes are PLACEHOLDERS from RE analysis.
 *       Must validate against Ghidra output of CLibResMgr.
 *       Wrong codes = harmless EINVAL, not car damage.
 *
 * Build:
 *   sh4-linux-gnu-gcc-14 -c -fPIC -O2 -ffreestanding -o uds_send.o uds_send.c
 *   # Transfer .o to PCM via telnet, link on target:
 *   /usr/bin/ld -o uds_send uds_send.o -lc
 */

extern int open(const char *, int, ...);
extern int close(int);
extern int write(int, const void *, unsigned);
extern int devctl(int, int, void *, unsigned, int *);

#define IPC_MAGIC   0xFADE
#define IOC_CAN_TP1 0x03
#define DCMD_NDR_WRITE 0x0D03  /* placeholder — needs Ghidra confirmation */

struct ndr_can_msg {
    unsigned short magic;
    unsigned short seq;
    unsigned char  svc_type;
    unsigned char  target;
    unsigned char  len;
    unsigned char  data[8];
};

static int hex(const char *s) {
    int v = 0;
    if (s[0]=='0' && (s[1]=='x'||s[1]=='X')) s+=2;
    for (; *s; s++) {
        v <<= 4;
        if (*s>='0'&&*s<='9') v|=*s-'0';
        else if (*s>='a'&&*s<='f') v|=*s-'a'+10;
        else if (*s>='A'&&*s<='F') v|=*s-'A'+10;
    }
    return v;
}

int main(int argc, char **argv) {
    struct ndr_can_msg msg = {0};
    int fd, ret, i;

    if (argc < 3) {
        write(1, "uds_send <module> <svc> [data...]\n", 34);
        return 1;
    }

    msg.magic = IPC_MAGIC;
    msg.seq = 1;
    msg.svc_type = IOC_CAN_TP1;
    msg.target = hex(argv[1]);
    msg.len = 0;

    for (i = 2; i < argc && msg.len < 8; i++)
        msg.data[msg.len++] = hex(argv[i]);

    fd = open("/dev/ndr/cmd", 2, 0);
    if (fd < 0) { write(1, "ERR: open ndr/cmd\n", 18); return 2; }

    ret = devctl(fd, DCMD_NDR_WRITE, &msg, sizeof(msg), 0);
    close(fd);

    if (ret == 0) write(1, "OK\n", 3);
    else write(1, "ERR: devctl failed\n", 19);

    return ret;
}
