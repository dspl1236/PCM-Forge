/*
 * PCM-Forge Bench Dongle v2.0.0
 * Arduino Nano + MCP2515 -- a CAN bench instrument for the PCM 3.1
 *
 * v1 put everything behind #defines, which meant a reflash for every
 * experiment: change bitrate, reflash; try listen-only, reflash; send a
 * different frame, reflash. On a bench where the bitrate is not yet known and
 * the interesting work is "does this frame change the unit's behaviour", that
 * loop is the whole cost. Everything here is a runtime command instead.
 *
 * The two settings people get wrong, and why they are commands now:
 *
 *   CRYSTAL. Modules ship with 8 MHz or 16 MHz and look identical. Get it
 *   wrong and every bitrate is wrong by 2x -- which presents as "CAN is dead",
 *   not as a clock error. If nothing is heard, try the other one before
 *   suspecting wiring.
 *
 *   LISTEN-ONLY. A wrong bitrate in normal mode floods the bus with error
 *   frames and can stop a working node from transmitting. Silent mode cannot,
 *   so discovery always starts there. But note the converse: a lone
 *   transmitter with nobody to ACK retries forever and goes error-passive, so
 *   if you want the PCM to talk, something has to answer it -- leave
 *   listen-only once the bitrate is confirmed.
 *
 * Hardware
 *   Nano D10 CS, D11 MOSI, D12 MISO, D13 SCK, D2 INT, 5V, GND
 *   MCP2515 CAN-H -> Quadlock pin 9, CAN-L -> pin 11
 *   120 ohm across CAN-H/CAN-L. On a two-node bench you usually need to add
 *   this yourself; an under-terminated bus fails intermittently and looks
 *   like a software problem.
 *   PCM power: +12V -> Quadlock pin 4, GND -> pin 8
 *
 * Serial 115200. Send "?" for help.
 *
 * Frame output is one line per frame, easy to parse:
 *   R <millis> <id-hex> <len> <data-hex>
 *
 * https://github.com/dspl1236/PCM-Forge
 */

#include <SPI.h>
#include <mcp_can.h>

#define CS_PIN     10
#define INT_PIN     2
#define LED_PIN     9        // D13 is SCK on a Nano, so status LED lives here

MCP_CAN CAN(CS_PIN);

// ---- runtime configuration -------------------------------------------
// Names are the library's, which are not the obvious ones -- there is no
// CAN_83K3BPS or CAN_33KBPS; check mcp_can_dfs.h before adding a rate.
const uint8_t  BITRATES[]   = {CAN_100KBPS, CAN_125KBPS, CAN_250KBPS,
                               CAN_500KBPS, CAN_1000KBPS, CAN_50KBPS,
                               CAN_80KBPS, CAN_33K3BPS};
const uint16_t BITRATE_KBPS[] = {100, 125, 250, 500, 1000, 50, 80, 33};
#define N_BITRATES (sizeof(BITRATES) / sizeof(BITRATES[0]))

uint8_t  cfgRate    = 3;      // default 500k -- VAG infotainment is usually this
uint8_t  cfgCrystal = 8;      // 8 or 16 MHz
// 0 = normal, 1 = listen-only, 2 = loopback (internal, transceiver not used)
uint8_t  cfgMode    = 1;      // start silent: cannot disturb a live bus
bool     opened     = false;
bool     echoFrames = true;

// ---- periodic transmit slots -----------------------------------------
#define MAX_REPEAT 4
struct Repeat {
  unsigned long id;
  uint8_t  len, data[8];
  uint16_t period;
  unsigned long last;
  bool     active;
} repeats[MAX_REPEAT];

// ---- seen-ID map (bounded: the Nano has 2 KB of RAM) ------------------
#define MAX_IDS 40
unsigned long seenId[MAX_IDS];
uint16_t      seenCount[MAX_IDS];
uint8_t       seenLen[MAX_IDS];
uint8_t       nSeen = 0;

unsigned long rxTotal = 0, txTotal = 0;
char line[64];
uint8_t lineLen = 0;

// ======================================================================

const __FlashStringHelper *modeName() {
  return cfgMode == 1 ? F("listen-only")
       : cfgMode == 2 ? F("LOOPBACK (internal -- bus not used)")
                      : F("normal");
}

void applyConfig() {
  uint8_t xtal = (cfgCrystal == 16) ? MCP_16MHZ : MCP_8MHZ;
  Serial.print(F("# open "));
  Serial.print(BITRATE_KBPS[cfgRate]);
  Serial.print(F("k xtal="));
  Serial.print(cfgCrystal);
  Serial.print(F("MHz mode="));
  Serial.println(modeName());

  if (CAN.begin(MCP_ANY, BITRATES[cfgRate], xtal) == CAN_OK) {
    CAN.setMode(cfgMode == 1 ? MCP_LISTENONLY
              : cfgMode == 2 ? MCP_LOOPBACK
                             : MCP_NORMAL);
    opened = true;
    Serial.println(F("# ok"));
  } else {
    opened = false;
    Serial.println(F("# FAILED -- check wiring, and try the other crystal (x 8 / x 16)"));
  }
}

void noteId(unsigned long id, uint8_t len) {
  for (uint8_t i = 0; i < nSeen; i++) {
    if (seenId[i] == id) { if (seenCount[i] < 65535) seenCount[i]++; return; }
  }
  if (nSeen < MAX_IDS) {
    seenId[nSeen] = id; seenCount[nSeen] = 1; seenLen[nSeen] = len; nSeen++;
  }
}

void printMap() {
  Serial.print(F("# ids seen: ")); Serial.println(nSeen);
  for (uint8_t i = 0; i < nSeen; i++) {
    Serial.print(F("M "));
    Serial.print(seenId[i], HEX);
    Serial.print(' '); Serial.print(seenLen[i]);
    Serial.print(' '); Serial.println(seenCount[i]);
  }
  if (nSeen >= MAX_IDS) Serial.println(F("# (id table full -- more may exist)"));
}

/* Listen on each bitrate in turn and count frames. The right one is the one
 * that yields frames at all; a wrong one yields none or a trickle of errors.
 * Silent throughout, so a live bus is never disturbed by the guessing. */
void scanBitrates(uint16_t dwellMs) {
  uint8_t wasMode = cfgMode;
  cfgMode = 1;
  Serial.println(F("# scanning bitrates, listen-only"));
  for (uint8_t i = 0; i < N_BITRATES; i++) {
    cfgRate = i;
    applyConfig();
    if (!opened) continue;
    unsigned long t0 = millis(); unsigned long n = 0;
    unsigned long id; uint8_t len; uint8_t buf[8];
    while (millis() - t0 < dwellMs) {
      if (CAN.checkReceive() == CAN_MSGAVAIL) {
        CAN.readMsgBuf(&id, &len, buf);
        n++;
      }
    }
    Serial.print(F("S ")); Serial.print(BITRATE_KBPS[i]);
    Serial.print(F("k frames=")); Serial.println(n);
  }
  cfgMode = wasMode;
  Serial.println(F("# scan done -- pick with 'b <index>' then 'o'"));
}

uint8_t hexNyb(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return 0xFF;
}

/* "t 710 0102ab" -> id 0x710, 3 bytes. Returns len, or 255 on parse error. */
uint8_t parseFrame(char *s, unsigned long *id, uint8_t *data) {
  while (*s == ' ') s++;
  *id = strtoul(s, &s, 16);
  while (*s == ' ') s++;
  uint8_t n = 0;
  while (*s && n < 8) {
    uint8_t hi = hexNyb(*s++);
    if (hi == 0xFF) break;
    uint8_t lo = hexNyb(*s++);
    if (lo == 0xFF) return 255;
    data[n++] = (hi << 4) | lo;
  }
  return n;
}

void sendFrame(unsigned long id, uint8_t len, uint8_t *data) {
  if (!opened) { Serial.println(F("# not open (use 'o')")); return; }
  if (cfgMode == 1) {
    Serial.println(F("# listen-only: nothing sent. 'l 0' to enable transmit"));
    return;
  }
  byte r = CAN.sendMsgBuf(id, 0, len, data);
  if (r == CAN_OK) txTotal++;          // count successes, not attempts
  Serial.print(r == CAN_OK ? F("T ok ") : F("T ERR "));
  Serial.println(id, HEX);
}

/* Dump the MCP2515 error state. This is how we tell "nobody is out there"
   apart from "our transceiver is not driving the bus":

     TEC climbing to 128 then sitting there   -> ACK errors. We transmit, the
        bits go out fine, nothing answers. Bus wiring is good; the PCM is
        absent or silent.
     TEC racing past 128 to bus-off (TXBO)    -> bit errors. We drive dominant
        and read back recessive, meaning the transceiver is dead, unpowered,
        or its ground is not the bus ground.                                  */
void printFaults() {
  uint8_t eflg = CAN.getError();
  Serial.print(F("F eflg=0x")); Serial.print(eflg, HEX);
  Serial.print(F(" tec=")); Serial.print(CAN.errorCountTX());
  Serial.print(F(" rec=")); Serial.print(CAN.errorCountRX());
  Serial.print(F(" ["));
  if (eflg & 0x01) Serial.print(F("EWARN "));
  if (eflg & 0x02) Serial.print(F("RXWAR "));
  if (eflg & 0x04) Serial.print(F("TXWAR "));
  if (eflg & 0x08) Serial.print(F("RXEP "));
  if (eflg & 0x10) Serial.print(F("TXEP "));
  if (eflg & 0x20) Serial.print(F("TXBO "));
  if (eflg & 0xC0) Serial.print(F("RXOVR "));
  Serial.println(F("]"));
}

void help() {
  Serial.println(F("# PCM-Forge bench dongle v2"));
  Serial.println(F("#  ?            this help + status"));
  Serial.println(F("#  s [ms]       scan bitrates, listen-only (default 1500ms each)"));
  Serial.println(F("#  b <0-7>      bitrate: 0=100k 1=125k 2=250k 3=500k 4=1M 5=50k 6=83k 7=33k"));
  Serial.println(F("#  x <8|16>     MCP2515 crystal MHz -- wrong value = every rate wrong"));
  Serial.println(F("#  l <0|1|2>    mode: 0 normal, 1 listen-only, 2 loopback"));
  Serial.println(F("#               loopback is internal to the MCP2515 -- it"));
  Serial.println(F("#               proves SPI and the controller work without"));
  Serial.println(F("#               involving the transceiver, wiring, or bus."));
  Serial.println(F("#  o            (re)open with current settings"));
  Serial.println(F("#  e <0|1>      echo received frames"));
  Serial.println(F("#  m            print the seen-ID map"));
  Serial.println(F("#  f            error counters: ACK errors vs bit errors"));
  Serial.println(F("#  z            zero counters and the ID map"));
  Serial.println(F("#  t <id> <hex> transmit once,  e.g. t 710 0102030405060708"));
  Serial.println(F("#  r <slot> <ms> <id> <hex>   repeat every ms (slot 0-3)"));
  Serial.println(F("#  q            stop all repeats"));
  Serial.print(F("# state: "));
  Serial.print(opened ? F("open ") : F("closed "));
  Serial.print(BITRATE_KBPS[cfgRate]); Serial.print(F("k xtal="));
  Serial.print(cfgCrystal); Serial.print(F(" "));
  Serial.print(modeName());
  Serial.print(F(" rx=")); Serial.print(rxTotal);
  Serial.print(F(" tx=")); Serial.println(txTotal);
}

void handle(char *s) {
  while (*s == ' ') s++;
  char c = *s++;
  switch (c) {
    case '?': case 'h': help(); break;
    case 's': scanBitrates(atoi(s) > 0 ? atoi(s) : 1500); break;
    case 'b': { int v = atoi(s); if (v >= 0 && v < (int)N_BITRATES) { cfgRate = v;
                Serial.print(F("# bitrate ")); Serial.print(BITRATE_KBPS[v]);
                Serial.println(F("k (use 'o' to apply)")); }
                else Serial.println(F("# range 0-7")); } break;
    case 'x': { int v = atoi(s); if (v == 8 || v == 16) { cfgCrystal = v;
                Serial.println(F("# crystal set (use 'o' to apply)")); }
                else Serial.println(F("# 8 or 16")); } break;
    case 'l': { int v = atoi(s); cfgMode = (v >= 0 && v <= 2) ? (uint8_t)v : 1;
                Serial.print(F("# mode ")); Serial.print(modeName());
                Serial.println(F(" (use 'o' to apply)")); } break;
    case 'o': applyConfig(); break;
    case 'e': echoFrames = (atoi(s) != 0); Serial.println(F("# ok")); break;
    case 'm': printMap(); break;
    case 'f': printFaults(); break;
    case 'z': nSeen = 0; rxTotal = txTotal = 0; Serial.println(F("# cleared")); break;
    case 't': { unsigned long id; uint8_t d[8];
                uint8_t n = parseFrame(s, &id, d);
                if (n == 255) Serial.println(F("# bad hex"));
                else sendFrame(id, n, d); } break;
    case 'r': { int slot = atoi(s);
                while (*s == ' ') s++; while (*s && *s != ' ') s++;
                int ms = atoi(s);
                while (*s == ' ') s++; while (*s && *s != ' ') s++;
                unsigned long id; uint8_t d[8];
                uint8_t n = parseFrame(s, &id, d);
                if (slot < 0 || slot >= MAX_REPEAT || ms <= 0 || n == 255) {
                  Serial.println(F("# usage: r <slot 0-3> <ms> <id> <hex>"));
                } else {
                  repeats[slot].id = id; repeats[slot].len = n;
                  memcpy(repeats[slot].data, d, n);
                  repeats[slot].period = ms; repeats[slot].last = 0;
                  repeats[slot].active = true;
                  Serial.print(F("# slot ")); Serial.print(slot);
                  Serial.print(F(" every ")); Serial.print(ms);
                  Serial.println(F("ms"));
                } } break;
    case 'q': for (uint8_t i = 0; i < MAX_REPEAT; i++) repeats[i].active = false;
              Serial.println(F("# repeats stopped")); break;
    case 0: break;
    default: Serial.println(F("# unknown -- '?' for help"));
  }
}

// ======================================================================

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);
  pinMode(LED_PIN, OUTPUT);
  pinMode(INT_PIN, INPUT);
  for (uint8_t i = 0; i < MAX_REPEAT; i++) repeats[i].active = false;

  Serial.println(F("# PCM-Forge bench dongle v2.0.0"));
  Serial.println(F("# starts LISTEN-ONLY so it cannot disturb a live bus."));
  Serial.println(F("# 's' scans bitrates. '?' for help."));
  applyConfig();
}

void loop() {
  // receive
  if (opened && CAN.checkReceive() == CAN_MSGAVAIL) {
    unsigned long id; uint8_t len; uint8_t buf[8];
    CAN.readMsgBuf(&id, &len, buf);
    rxTotal++;
    noteId(id, len);
    digitalWrite(LED_PIN, (rxTotal & 1) ? HIGH : LOW);
    if (echoFrames) {
      Serial.print(F("R ")); Serial.print(millis());
      Serial.print(' '); Serial.print(id, HEX);
      Serial.print(' '); Serial.print(len);
      Serial.print(' ');
      for (uint8_t i = 0; i < len; i++) {
        if (buf[i] < 0x10) Serial.print('0');
        Serial.print(buf[i], HEX);
      }
      Serial.println();
    }
  }

  // periodic transmits
  unsigned long now = millis();
  for (uint8_t i = 0; i < MAX_REPEAT; i++) {
    if (repeats[i].active && now - repeats[i].last >= repeats[i].period) {
      repeats[i].last = now;
      if (opened && cfgMode != 1) {
        if (CAN.sendMsgBuf(repeats[i].id, 0, repeats[i].len,
                           repeats[i].data) == CAN_OK) txTotal++;
      }
    }
  }

  // serial commands
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen) { line[lineLen] = 0; handle(line); lineLen = 0; }
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = c;
    }
  }
}
