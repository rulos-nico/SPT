/**
 * protocol.cpp
 * Implementation of the serial JSON protocol.
 */

#include "protocol.h"

namespace Protocol {

void sendBlow(HardwareSerial &port,
              uint32_t  timestamp,
              uint16_t  blowNumber,
              float     depthMm,
              float     impactG) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"]       = "blow";
    doc["ts"]         = timestamp;
    doc["blow"]       = blowNumber;
    doc["depth_mm"]   = serialized(String(depthMm, 1));
    doc["impact_g"]   = serialized(String(impactG, 2));
    serializeJson(doc, port);
    port.println();
}

void sendDepth(HardwareSerial &port,
               uint32_t timestamp,
               float    depthMm) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"]     = "depth";
    doc["ts"]       = timestamp;
    doc["depth_mm"] = serialized(String(depthMm, 1));
    serializeJson(doc, port);
    port.println();
}

void sendStatus(HardwareSerial &port,
                uint32_t  timestamp,
                uint8_t   batteryPct,
                uint16_t  freeMemKb) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"]        = "status";
    doc["ts"]          = timestamp;
    doc["battery_pct"] = batteryPct;
    doc["free_mem_kb"] = freeMemKb;
    serializeJson(doc, port);
    port.println();
}

void sendAck(HardwareSerial &port,
             const char *command,
             bool        success) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"]    = "ack";
    doc["cmd"]     = command;
    doc["ok"]      = success;
    serializeJson(doc, port);
    port.println();
}

String parseCommand(const String &jsonLine,
                    StaticJsonDocument<JSON_BUFFER_SIZE> &doc) {
    DeserializationError err = deserializeJson(doc, jsonLine);
    if (err) {
        return String("");
    }
    const char *cmd = doc["cmd"] | "";
    return String(cmd);
}

}  // namespace Protocol
