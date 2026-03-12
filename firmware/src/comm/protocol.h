#pragma once
/**
 * protocol.h
 * Defines the serial JSON communication protocol between the embedded
 * device and the host PC software.
 *
 * All messages are newline-terminated JSON objects.
 *
 * Message types sent by the device:
 *   "blow"   – a hammer blow was detected
 *   "depth"  – periodic penetration depth update
 *   "status" – device heartbeat with battery / memory info
 *   "ack"    – acknowledgement of a command from the host
 *
 * Commands sent by the host:
 *   "start"  – begin a new test interval
 *   "stop"   – end the current test interval
 *   "reset"  – reset all counters
 *   "zero"   – zero the depth reference
 *   "config" – update threshold / calibration parameters
 */

#include <Arduino.h>
#include <ArduinoJson.h>

#define PROTOCOL_BAUD       115200
#define JSON_BUFFER_SIZE    256

namespace Protocol {

/** Send a blow-detected event to the host. */
void sendBlow(HardwareSerial &port,
              uint32_t  timestamp,
              uint16_t  blowNumber,
              float     depthMm,
              float     impactG);

/** Send a periodic depth update. */
void sendDepth(HardwareSerial &port,
               uint32_t timestamp,
               float    depthMm);

/** Send device status / heartbeat. */
void sendStatus(HardwareSerial &port,
                uint32_t  timestamp,
                uint8_t   batteryPct,
                uint16_t  freeMemKb);

/** Send an acknowledgement for a received command. */
void sendAck(HardwareSerial &port,
             const char *command,
             bool        success);

/** Parse an incoming JSON command line.
 *  Returns the "cmd" field value or empty string on parse error.
 */
String parseCommand(const String &jsonLine,
                    StaticJsonDocument<JSON_BUFFER_SIZE> &doc);

}  // namespace Protocol
