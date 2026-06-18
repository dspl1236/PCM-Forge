/*
 * PCM-Forge Bench Dongle v0.1.0
 * Arduino Nano + MCP2515 CAN controller
 * 
 * Wakes a Porsche PCM 3.1 on the bench by sending periodic CAN frames.
 * The V850 IOC monitors the infotainment CAN bus for activity before
 * powering on the SH4 main board.
 *
 * Hardware:
 *   Arduino Nano
 *   MCP2515 CAN module (with TJA1050 transceiver)
 *   120Ω termination resistor across CAN-H / CAN-L
 *   12V bench power supply
 *
 * Wiring (Nano → MCP2515):
 *   D10 → CS        D11 → MOSI (SI)
 *   D12 → MISO (SO) D13 → SCK
 *   D2  → INT        5V → VCC
 *   GND → GND
 *
 * Wiring (MCP2515 → PCM Quadlock):
 *   CAN-H → Pin 9    CAN-L → Pin 11
 *   (+120Ω resistor between CAN-H and CAN-L)
 *
 * PCM Power (bench supply → Quadlock):
 *   +12V → Pin 4     GND → Pin 8
 *
 * Serial monitor: 115200 baud for debug output
 *
 * https://github.com/dspl1236/PCM-Forge
 */

#include <mcp_can.h>
#include <SPI.h>

// ============================================================
// Configuration — edit these for your setup
// ============================================================

// CAN bus speed: infotainment CAN is likely 100kbps.
// If PCM doesn't wake, try CAN_500KBPS.
#define CAN_SPEED       CAN_100KBPS

// MCP2515 crystal frequency: check your board!
// Common modules: 8MHz (MCP_8MHZ) or 16MHz (MCP_16MHZ)
#define CAN_CRYSTAL     MCP_8MHZ

// CS pin for MCP2515
#define CAN_CS_PIN      10

// INT pin from MCP2515 (for receiving)
#define CAN_INT_PIN     2

// Wake frame interval (ms)
#define WAKE_INTERVAL   1000

// Gateway CAN ID (used for wake frame)
#define CAN_ID_GATEWAY  0x710

// Enable VIN spoof — sends a fake gateway VIN on CAN
// Set to 1 and edit SPOOF_VIN below to enable
#define ENABLE_VIN_SPOOF  0
#define SPOOF_VIN         "WP0AA2A70BL000000"

// Enable CAN sniffer — prints all received frames to serial
#define ENABLE_SNIFFER    1

// Status LED (use D9 since D13 is SPI SCK on Nano)
#define STATUS_LED        9

// ============================================================
// Globals
// ============================================================

MCP_CAN CAN(CAN_CS_PIN);

unsigned long lastWake = 0;
unsigned long lastBlink = 0;
unsigned long frameCount = 0;
unsigned long rxCount = 0;
bool ledState = false;

// ============================================================
// Setup
// ============================================================

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000);  // Wait for serial (max 3s)

    Serial.println(F("================================="));
    Serial.println(F("  PCM-Forge Bench Dongle v0.1.0"));
    Serial.println(F("================================="));

    pinMode(STATUS_LED, OUTPUT);
    pinMode(CAN_INT_PIN, INPUT);

    // Initialize MCP2515
    Serial.print(F("Init MCP2515... "));
    if (CAN.begin(MCP_ANY, CAN_SPEED, CAN_CRYSTAL) == CAN_OK) {
        Serial.println(F("OK"));
    } else {
        Serial.println(F("FAILED! Check wiring and crystal."));
        errorBlink();
    }

    CAN.setMode(MCP_NORMAL);

    Serial.print(F("CAN speed: "));
    #if CAN_SPEED == CAN_100KBPS
        Serial.println(F("100 kbps"));
    #elif CAN_SPEED == CAN_500KBPS
        Serial.println(F("500 kbps"));
    #else
        Serial.println(F("custom"));
    #endif

    Serial.print(F("VIN spoof: "));
    #if ENABLE_VIN_SPOOF
        Serial.println(SPOOF_VIN);
    #else
        Serial.println(F("disabled"));
    #endif

    Serial.print(F("Sniffer: "));
    #if ENABLE_SNIFFER
        Serial.println(F("enabled"));
    #else
        Serial.println(F("disabled"));
    #endif

    Serial.println(F(""));
    Serial.println(F("Sending wake frames..."));
    Serial.println(F(""));
}

// ============================================================
// Main loop
// ============================================================

void loop() {
    unsigned long now = millis();

    // --- Send periodic wake frame ---
    if (now - lastWake >= WAKE_INTERVAL) {
        lastWake = now;
        sendWakeFrame();
        frameCount++;

        // Blink status LED on each wake frame
        ledState = !ledState;
        digitalWrite(STATUS_LED, ledState);

        // Periodic status every 10 frames
        if (frameCount % 10 == 0) {
            Serial.print(F("[status] TX: "));
            Serial.print(frameCount);
            Serial.print(F("  RX: "));
            Serial.println(rxCount);
        }
    }

    // --- Send VIN spoof if enabled ---
    #if ENABLE_VIN_SPOOF
    if (frameCount > 0 && frameCount % 5 == 0 && now - lastWake < 50) {
        sendVinSpoof();
    }
    #endif

    // --- Receive and print CAN frames ---
    #if ENABLE_SNIFFER
    if (!digitalRead(CAN_INT_PIN)) {
        receiveCAN();
    }
    #endif
}

// ============================================================
// Wake frame
// ============================================================

void sendWakeFrame() {
    // Send a generic frame on the gateway CAN ID
    // The V850 IOC just needs to see valid CAN traffic to wake up
    byte data[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

    byte result = CAN.sendMsgBuf(CAN_ID_GATEWAY, 0, 8, data);
    if (result != CAN_OK) {
        Serial.print(F("[wake] TX failed: "));
        Serial.println(result);
    }
}

// ============================================================
// VIN spoof (optional)
// ============================================================

#if ENABLE_VIN_SPOOF
void sendVinSpoof() {
    // Simulate gateway VIN broadcast
    // CAN ID 0x65F is used on some VAG platforms for VIN broadcast
    // The VIN is 17 chars, sent across 3 CAN frames (ISO-TP)
    const char* vin = SPOOF_VIN;

    // Frame 1: First Flow (10) + length + first 6 bytes of VIN
    byte f1[8] = {0x10, 0x11};  // multi-frame, 17 bytes total
    for (int i = 0; i < 6; i++) f1[2 + i] = vin[i];
    CAN.sendMsgBuf(CAN_ID_GATEWAY, 0, 8, f1);

    delay(5);

    // Frame 2: Consecutive (21) + next 7 bytes
    byte f2[8] = {0x21};
    for (int i = 0; i < 7; i++) f2[1 + i] = vin[6 + i];
    CAN.sendMsgBuf(CAN_ID_GATEWAY, 0, 8, f2);

    delay(5);

    // Frame 3: Consecutive (22) + last 4 bytes + padding
    byte f3[8] = {0x22};
    for (int i = 0; i < 4; i++) f3[1 + i] = vin[13 + i];
    f3[5] = 0x00; f3[6] = 0x00; f3[7] = 0x00;
    CAN.sendMsgBuf(CAN_ID_GATEWAY, 0, 8, f3);

    Serial.println(F("[vin] VIN spoof sent"));
}
#endif

// ============================================================
// CAN sniffer
// ============================================================

#if ENABLE_SNIFFER
void receiveCAN() {
    unsigned long canId;
    byte len = 0;
    byte buf[8];

    if (CAN.readMsgBuf(&canId, &len, buf) == CAN_OK) {
        rxCount++;

        // Skip TX echo (bit 30 set = extended frame, not what we want)
        // Print received frame
        Serial.print(F("[rx] 0x"));
        if (canId < 0x100) Serial.print(F("0"));
        if (canId < 0x10)  Serial.print(F("0"));
        Serial.print(canId, HEX);
        Serial.print(F(" ["));
        Serial.print(len);
        Serial.print(F("] "));

        for (int i = 0; i < len; i++) {
            if (buf[i] < 0x10) Serial.print(F("0"));
            Serial.print(buf[i], HEX);
            if (i < len - 1) Serial.print(F(" "));
        }
        Serial.println();
    }
}
#endif

// ============================================================
// Error handler
// ============================================================

void errorBlink() {
    // Rapid blink forever on init failure
    while (1) {
        digitalWrite(STATUS_LED, HIGH);
        delay(100);
        digitalWrite(STATUS_LED, LOW);
        delay(100);
    }
}
