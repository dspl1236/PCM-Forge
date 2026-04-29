# NDR devctl Constants — Extracted from NavigationNdrInfo

## Discovery Date: April 28, 2026
## Source: NavigationNdrInfo ELF binary (563KB, SH4, from PCM 3.1 Cayenne 958)

## DCMD Constants

All use QNX __DIOTF macro: `__DIOTF(class=0x05, number, size=4)`

| DCMD Value   | Number | Function        | Source Function                        |
|-------------|--------|-----------------|----------------------------------------|
| 0xC004050B  | 0x0B   | ndrOpen         | CLibResMgr::ndrOpen (set pid/tid)     |
| 0xC004050A  | 0x0A   | checkVersion    | CLibResMgr::checkVersion              |
| 0xC0040507  | 0x07   | ndrWrite        | CLibResMgr::ndrWrite (send telegram)  |
| 0xC0040508  | 0x08   | ndrRead         | CLibResMgr::ndrRead (recv telegram)   |

## Usage Pattern (from disassembly)

### ndrOpen (register client)
```c
// Set pid and tid for client registration
int pid = getpid();
int tid = pthread_self();
CValue pidVal(pid);   // 4 bytes, type INT
CValue tidVal(tid);   // 4 bytes, type INT
CTransTel tel(4, 0, pid, tidVal);  // function=4, index=0
// ... 
devctl(fd, 0xC004050B, &tel_data, tel_size, NULL);
```

### ndrRead
```c
CTransTel tel(4, 0, id, value);  // function=4, index=0
tel.resize(0x3EE4);  // buffer size = 16100 bytes!
// Loop with retry on EAGAIN/EINTR:
devctl(fd, 0xC0040508, &tel_data, tel_size, NULL);
```

### ndrWrite
```c
CTransTel tel(4, 1, id, index, value);  // function=4, class=1
// maxDataLength check against 0x3EE4 (16100 bytes)
devctl(fd, 0xC0040507, &tel_data, tel_size, NULL);
```

### checkVersion
```c
CValue val(0x3000000);  // version 3.0.0
CTransTel tel(...);
devctl(fd, 0xC004050A, &tel_data, tel_size, NULL);
```

## CTransTel (Telegram) Format

From the constructor `CTransTel(functionId, classId, ndrId, value)`:
- functionId: 4 = standard operation
- classId: 0 = read, 1 = write  
- ndrId: the NDR data item ID
- value: CValue containing the data payload

Buffer size: 0x3EE4 = 16,100 bytes maximum

## Key Insights

1. Class 0x05 is the NDR namespace — our devctl probe never tried it
2. All operations use DIOTF (bidirectional) with 4-byte initial data
3. CTransTel wraps the telegram with function/class/id/value structure
4. Maximum telegram size is 16,100 bytes (0x3EE4)
5. Retry on EAGAIN (errno 4) and EINTR (errno 11)
6. Version check expects 0x3000000 (v3.0.0)

## What This Means for Oil Service Reset

The CAN path is: devctl → /dev/ndr → dev-ipc → IOC → FPGA → V850 → CAN bus

To send a UDS command to the cluster (module 0x17):
1. Open /dev/ndr/cmd with open()
2. Register with 0xC004050B (pid/tid)
3. Check version with 0xC004050A
4. Send UDS telegram with 0xC0040507
5. Read response with 0xC0040508

The UDS command for oil service reset is RoutineControl (0x31) or
WriteDataByIdentifier (0x2E) targeting the cluster's service interval DIDs.

## Next Steps

- [ ] Build ndr_tool.c for QNX SH4 that implements the open/register/read/write flow
- [ ] Find the NDR IDs for CAN TP1 (UDS transport)
- [ ] Cross-reference with IOC service types from CAN architecture research
- [ ] Test with read-only devctl first (safe)
- [ ] Then test write (UDS diagnostic session) on live car
