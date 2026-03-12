/**
 * penetration_sensor.cpp
 * Implementation of PenetrationSensor.
 */

#include "penetration_sensor.h"

// Single global pointer so the static ISR wrapper can reach the instance.
// For multi-sensor designs replace with an array.
static PenetrationSensor *g_instance = nullptr;

static void IRAM_ATTR encoderISR() {
    if (g_instance) {
        g_instance->handleInterrupt();
    }
}

PenetrationSensor::PenetrationSensor(uint8_t pinA, uint8_t pinB, float mmPerPulse)
    : _pinA(pinA),
      _pinB(pinB),
      _mmPerPulse(mmPerPulse),
      _pulseCount(0),
      _deltaBaseline(0)
{}

void PenetrationSensor::begin() {
    pinMode(_pinA, INPUT_PULLUP);
    pinMode(_pinB, INPUT_PULLUP);
    g_instance = this;
    attachInterrupt(digitalPinToInterrupt(_pinA), encoderISR, CHANGE);
}

void IRAM_ATTR PenetrationSensor::handleInterrupt() {
    bool a = digitalRead(_pinA);
    bool b = digitalRead(_pinB);
    // Standard X1 quadrature decoding: direction determined by B state at A edge
    if (a == b) {
        _pulseCount++;
    } else {
        _pulseCount--;
    }
}

float PenetrationSensor::getDepthMm() const {
    return static_cast<float>(_pulseCount) * _mmPerPulse;
}

float PenetrationSensor::getDeltaMm() const {
    return static_cast<float>(_pulseCount - _deltaBaseline) * _mmPerPulse;
}

void PenetrationSensor::zero() {
    noInterrupts();
    _pulseCount    = 0;
    _deltaBaseline = 0;
    interrupts();
}

void PenetrationSensor::resetDelta() {
    noInterrupts();
    _deltaBaseline = _pulseCount;
    interrupts();
}

int32_t PenetrationSensor::getPulseCount() const {
    return _pulseCount;
}
