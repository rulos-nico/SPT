/**
 * impact_sensor.cpp
 * Implementation of ImpactSensor.
 */

#include "impact_sensor.h"
#include <math.h>

ImpactSensor::ImpactSensor(int32_t sensorId, float threshold)
    : _adxl(sensorId),
      _threshold(threshold),
      _baselineG(1.0f),   // 1 g resting on gravity axis
      _blowCount(0),
      _lastImpactG(0.0f),
      _lastBlowTime(0)
{}

bool ImpactSensor::begin() {
    if (!_adxl.begin()) {
        return false;
    }
    _adxl.setRange(ADXL345_RANGE_16_G);
    calibrate();
    return true;
}

void ImpactSensor::calibrate() {
    float sum = 0.0f;
    for (int i = 0; i < BASELINE_SAMPLES; i++) {
        sensors_event_t event;
        _adxl.getEvent(&event);
        sum += _computeMagnitude(event);
        delay(10);
    }
    _baselineG = sum / BASELINE_SAMPLES;
}

bool ImpactSensor::update() {
    sensors_event_t event;
    _adxl.getEvent(&event);

    float magnitude = _computeMagnitude(event);
    float delta     = magnitude - _baselineG;

    if (delta < _threshold) {
        return false;
    }

    unsigned long now = millis();
    if ((now - _lastBlowTime) < BLOW_DEBOUNCE_MS) {
        return false;   // still in debounce window
    }

    // Valid new blow
    _blowCount++;
    _lastImpactG  = delta;
    _lastBlowTime = now;
    return true;
}

void ImpactSensor::reset() {
    _blowCount    = 0;
    _lastImpactG  = 0.0f;
    _lastBlowTime = 0;
    calibrate();
}

float ImpactSensor::_computeMagnitude(const sensors_event_t &event) const {
    float ax = event.acceleration.x;
    float ay = event.acceleration.y;
    float az = event.acceleration.z;
    // Convert m/s² to g-forces (1 g = 9.80665 m/s²)
    return sqrtf(ax * ax + ay * ay + az * az) / 9.80665f;
}
