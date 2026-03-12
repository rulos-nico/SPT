/**
 * main.cpp  –  SPT Measurement System Firmware
 *
 * Hardware connections (ESP32 DevKit):
 *   ADXL345 (I²C)  SDA → GPIO 21,  SCL → GPIO 22
 *   Encoder A       → GPIO 34  (interrupt)
 *   Encoder B       → GPIO 35
 *   RTC DS3231      SDA → GPIO 21,  SCL → GPIO 22  (shared I²C bus)
 *   SD card CS      → GPIO 5
 *   Status LED      → GPIO 2
 *   Buzzer          → GPIO 4
 *
 * Serial protocol: 115200 baud, JSON lines to/from USB-UART.
 */

#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <RTClib.h>

#include "sensors/impact_sensor.h"
#include "sensors/penetration_sensor.h"
#include "data/storage.h"
#include "comm/protocol.h"

// ── Pin assignments ──────────────────────────────────────────────────────────
static constexpr uint8_t PIN_ENCODER_A = 34;
static constexpr uint8_t PIN_ENCODER_B = 35;
static constexpr uint8_t PIN_LED       = 2;
static constexpr uint8_t PIN_BUZZER    = 4;

// ── Timing constants ─────────────────────────────────────────────────────────
static constexpr uint32_t DEPTH_REPORT_MS  = 500;   // depth update interval
static constexpr uint32_t STATUS_REPORT_MS = 5000;  // heartbeat interval
static constexpr uint32_t LED_BLINK_MS     = 50;    // blow indication blink

// ── Module instances ─────────────────────────────────────────────────────────
static ImpactSensor      impact;
static PenetrationSensor depth(PIN_ENCODER_A, PIN_ENCODER_B);
static Storage           storage;
static RTC_DS3231        rtc;

// ── State ────────────────────────────────────────────────────────────────────
static bool     testRunning   = false;
static uint32_t sessionId     = 0;
static uint32_t lastDepthMs   = 0;
static uint32_t lastStatusMs  = 0;
static uint32_t ledOffMs      = 0;

// ── Helpers ──────────────────────────────────────────────────────────────────
static uint32_t now_unix() {
    DateTime dt = rtc.now();
    return dt.unixtime();
}

static void blinkLed() {
    digitalWrite(PIN_LED, HIGH);
    ledOffMs = millis() + LED_BLINK_MS;
}

static void buzzShort() {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(30);
    digitalWrite(PIN_BUZZER, LOW);
}

static void handleCommand(const String &line) {
    StaticJsonDocument<Protocol::JSON_BUFFER_SIZE> doc;
    String cmd = Protocol::parseCommand(line, doc);

    if (cmd == "start") {
        if (!testRunning) {
            sessionId = now_unix();
            storage.openSession(sessionId);
            impact.reset();
            depth.zero();
            testRunning = true;
        }
        Protocol::sendAck(Serial, "start", true);

    } else if (cmd == "stop") {
        if (testRunning) {
            storage.closeSession();
            testRunning = false;
        }
        Protocol::sendAck(Serial, "stop", true);

    } else if (cmd == "reset") {
        impact.reset();
        depth.zero();
        Protocol::sendAck(Serial, "reset", true);

    } else if (cmd == "zero") {
        depth.zero();
        Protocol::sendAck(Serial, "zero", true);

    } else if (cmd == "config") {
        // Future: accept threshold / calibration updates
        Protocol::sendAck(Serial, "config", true);

    } else {
        Protocol::sendAck(Serial, cmd.c_str(), false);
    }
}

// ── Arduino setup ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(PROTOCOL_BAUD);
    Wire.begin();

    pinMode(PIN_LED,    OUTPUT);
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_LED,    LOW);
    digitalWrite(PIN_BUZZER, LOW);

    // RTC
    if (!rtc.begin()) {
        Serial.println(F("{\"type\":\"error\",\"msg\":\"RTC not found\"}"));
    }
    if (rtc.lostPower()) {
        // Set to compile time as fallback
        rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }

    // Impact sensor
    if (!impact.begin()) {
        Serial.println(F("{\"type\":\"error\",\"msg\":\"ADXL345 not found\"}"));
    }

    // Depth encoder
    depth.begin();

    // SD storage
    if (!storage.begin()) {
        Serial.println(F("{\"type\":\"error\",\"msg\":\"SD card not found\"}"));
    }

    // Ready signal
    Serial.println(F("{\"type\":\"ready\",\"fw\":\"1.0.0\"}"));
}

// ── Arduino loop ──────────────────────────────────────────────────────────────
void loop() {
    uint32_t nowMs = millis();

    // ── Turn off LED when blink period expires ────────────────────────────
    if (ledOffMs && nowMs >= ledOffMs) {
        digitalWrite(PIN_LED, LOW);
        ledOffMs = 0;
    }

    // ── Check for incoming commands from host ─────────────────────────────
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) {
            handleCommand(line);
        }
    }

    // ── Impact detection ─────────────────────────────────────────────────
    if (impact.update()) {
        uint32_t ts     = now_unix();
        uint16_t blowNo = impact.getBlowCount();
        float    dep    = depth.getDepthMm();
        float    impG   = impact.getLastImpactG();

        Protocol::sendBlow(Serial, ts, blowNo, dep, impG);

        if (testRunning && storage.isOpen()) {
            // Build JSON string for SD card storage
            StaticJsonDocument<Protocol::JSON_BUFFER_SIZE> doc;
            doc["type"]     = "blow";
            doc["ts"]       = ts;
            doc["blow"]     = blowNo;
            doc["depth_mm"] = dep;
            doc["impact_g"] = impG;
            String line;
            serializeJson(doc, line);
            storage.writeLine(line);
        }

        blinkLed();
        buzzShort();
    }

    // ── Periodic depth report ─────────────────────────────────────────────
    if (testRunning && (nowMs - lastDepthMs) >= DEPTH_REPORT_MS) {
        lastDepthMs = nowMs;
        Protocol::sendDepth(Serial, now_unix(), depth.getDepthMm());
    }

    // ── Periodic status heartbeat ─────────────────────────────────────────
    if ((nowMs - lastStatusMs) >= STATUS_REPORT_MS) {
        lastStatusMs = nowMs;
        // Battery % and free memory are platform-specific; use placeholders.
        Protocol::sendStatus(Serial, now_unix(), 100, 0);
    }
}
