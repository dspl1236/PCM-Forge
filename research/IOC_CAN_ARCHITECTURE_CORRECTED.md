# CAN Bus Architecture — CORRECTED

## Date: May 4, 2026
## Previous Error: NDR was the wrong target

### What We Got Wrong

All previous versions of `uds_send` (v1-v5) targeted `/dev/ndr/cmd` for CAN
communication. **NDR is the Navigation Data Router** — it handles GPS, gyro,
and sensor data from `/dev/ipc/ioc/ch5`. It has nothing to do with CAN bus
messaging. This is why every version crashed.

### Correct Architecture (from PCM3Root binary analysis)

```
PCM3Root (SH4 application)
│
├── CGCANConnectionImpl            ← CAN bus interface
│   ├── ENCODER_BLOCK_IDs          ← send data TO CAN bus
│   ├── DECODER_BLOCK_IDs          ← receive data FROM CAN bus
│   └── CHBIpcProtocol             ← 0xFADE framing protocol
│       ├── /dev/ipc/ioc/ch2       ← CAN channel (world-writable)
│       ├── /dev/ipc/ioc/ch6       ← CAN channel (world-writable)
│       └── /dev/ipc/ioc/ch8       ← CAN channel (world-writable)
│
├── NDR (Navigation Data Router)   ← SENSOR data only
│   └── /dev/ipc/ioc/ch5           ← GPS/gyro/accel data
│       ├── /dev/ndr/cmd            ← NDR command interface
│       └── /dev/ndr/notify         ← NDR notifications
│
└── IPCD (MOST network)            ← Audio/media over fiber optic
    └── /dev/ipc/ioc/ch*            ← MOST channels
```

### IOC Channel Map (confirmed from firmware)

| Channel | Used By | Purpose |
|---------|---------|---------|
| ch2 | CGCANConnectionImpl | CAN bus messages |
| ch5 | NDR | Navigation sensor data |
| ch6 | CGCANConnectionImpl | CAN bus messages |
| ch8 | CGCANConnectionImpl | CAN bus messages |
| debug | monitoring | Traffic sniffing |
| onoff | OnOffPresCtrl | Power state control |
| watchdog | system | Watchdog timer |

### CAN Encoder Blocks (PCM can SEND to CAN)

| Block ID | Purpose |
|----------|---------|
| RESETBC_ENCODER_BLOCK_ID | Trip computer reset |
| SET_TIME_ENCODER_BLOCK_ID | Set clock |
| BC_INIT_ENCODER_BLOCK_ID | Board computer init |
| PERSISTENCE_SETTING_ENCODER_BLOCK_ID | Write persistence |
| FRAME_REQUEST_ENCODER_BLOCK_ID | Request CAN frames |
| RVC_SETTINGS_ENCODER_BLOCK_ID | Rear view camera |
| PDC_ENCODER_BLOCK_ID | Park distance control |
| COMPASS_ENCODER_BLOCK_ID | Compass data |
| INDIVIDUALMEMORY_ENCODER_BLOCK_ID | Seat/mirror memory |
| SENSOR_FAKTOREN_ENCODER_BLOCK_ID | Sensor factors |
| DAMPER_PARAM_ENCODER_BLOCK_ID | Damper parameters |
| BRIGHTNESS_SETTING_ENCODER_BLOCK_ID | Display brightness |
| DIMMING_PARAM_REQ_ENCODER_BLOCK_ID | Dimming request |
| RAW_UNIX_TIME_ENCODER_BLOCK_ID | Unix timestamp |
| ZEITZONE_INFO_ENCODER_BLOCK_ID | Timezone info |
| CURVE_PARAM_ENCODER_BLOCK_ID | Curve parameters |
| REALTOPVIEW_ENCODER_BLOCK_ID | TopView camera |
| SPORTCHRONO encoders | Sport Chrono system |

**NOTE: No SERVICE_RESET or OIL_RESET encoder block exists.**
Porsche deliberately excluded this from PCM3Root.

### CAN Decoder Blocks (PCM RECEIVES from CAN)

| Block ID | Data |
|----------|------|
| VEHICLE1_DECODER_BLOCK_ID | Speed, RPM, temp, gear, handbrake, key ID |
| TRIP1/TRIP2_DECODER_BLOCK_ID | Trip computer data |
| CONSUMPTION_DECODER_BLOCK_ID | Fuel consumption |
| HYBRID_*_DECODER_BLOCK_ID | E-Hybrid battery/charge |
| DOOR_STATE_DECODER_BLOCK_ID | Door open/close |
| PERSISTENCE_DECODER_BLOCK_ID | Persistence from CAN |
| VARIANTCODING_DECODER_BLOCK_ID | Variant coding |
| DATE/TIME_DECODER_BLOCK_ID | Date and time |
| STATICDATA_DECODER_BLOCK_ID | Static vehicle data |
| SPORTCHRONO decoders | Lap/stopwatch data |
| STEERING_ANGLE_DECODER_BLOCK_ID | Steering angle |
| CROSS/LONGITUDINAL_ACCELERATION | G-force data |
| SPEEDLIMIT_BLOCK_ID | Speed limit info |
| MOTORSTARTSTOP_DECODER_BLOCK_ID | Start/stop system |
| E_RANGE_DECODER_BLOCK_ID | Electric range |

### CHBIpcProtocol Wire Format

```
0xFA 0xDE          — magic header (2 bytes)
frame_counter      — incrementing sequence number
telegram_data      — CAN message payload
[checksum?]        — possibly CRC
```

Validation from PCM3Root strings:
- "0xFADE expected but not received" — strict magic check
- "wrong frame cnt (rcv: %u, exp: %u)" — sequence validation
- "store incompleted telegram failed" — telegram integrity check
- "error in writting to IPC driver" — write error handling

### IOC Service Types (19 confirmed)

```
IOC_CAN_DRIVER     — Low-level CAN driver
IOC_CAN_MATRIX     — CAN signal/message matrix
IOC_CAN_TP1        — CAN Transport Protocol (UDS diagnostics)
IOC_DIAGX          — Extended diagnostics
IOC_DIAG_SWNO      — Diagnostic SW number
IOC_MOST_NETSVCREV — MOST service revision
IOC_MOST_NETSVCVER — MOST service version
IOC_MOST_TRANSX    — MOST transport
IOC_GW_CFGVER      — Gateway config version
IOC_GW_POOL        — Gateway message pool
IOC_GW_eRTAB       — Gateway external routing table
IOC_GW_eRTABDATE   — Gateway routing table date
IOC_GW_iRTAB       — Gateway internal routing table
IOC_BOLO           — Boot loader
IOC_FRONT          — Front electronics
IOC_POWERCONTROL   — Power management
IOC_SWVERSION      — Software version
IOC_SWRevision     — Software revision
IOC_PC_FUSEBYTES   — Fuse bytes
```

### Path Forward for Oil Service Reset

Since PCM3Root has no service reset encoder block, sending UDS commands
to the instrument cluster requires bypassing PCM3Root entirely and
writing directly to IOC CAN channels using CHBIpcProtocol format.

**Phase 1: IOC Probe (read-only, safe)**
- Capture raw data from ch2/ch6/ch8
- Reverse engineer 0xFADE frame format from captured data
- Map which channel carries which CAN traffic

**Phase 2: IOC Writer (careful testing)**
- Implement 0xFADE framing
- Send IOC_CAN_TP1 UDS request
- Start with safest command: DiagnosticSessionControl (0x10 0x01)
- Then: ReadDataByIdentifier to read service data
- Finally: WriteDataByIdentifier for service reset

**Alternative: External OBD-II**
- VNCI 6154a + ODIS E17 (Touareg 7P platform)
- ESP32 + MCP2515 CAN transceiver
- These bypass the PCM entirely via the OBD-II port

### Files Analyzed

| File | Size | Source |
|------|------|--------|
| PCM3Root | 6.6MB | PCM3_IFS1.ifs (LZO decompressed) |
| dev-ipc | 75KB | IFS1 /proc/boot/ |
| ndr | 458KB | IFS1 /proc/boot/ |
| 63,127 strings extracted from PCM3Root |
