#pragma once
/**
 * impact_sensor.h
 * Detects SPT hammer impacts using an ADXL345 accelerometer.
 * Applies a threshold and de-bounce logic to count valid blows.
 */

#include <Arduino.h>
#include <Adafruit_ADXL345_U.h>

// Default detection threshold in g-forces
#define IMPACT_THRESHOLD_G     5.0f
// Minimum time between two consecutive valid blows (ms)
#define BLOW_DEBOUNCE_MS       200
// Number of samples averaged for baseline noise estimation
#define BASELINE_SAMPLES       50

class ImpactSensor {
public:
    /**
     * @param sensorId  Unique sensor identifier for Adafruit unified library.
     * @param threshold Impact threshold in g-forces (default IMPACT_THRESHOLD_G).
     */
    explicit ImpactSensor(int32_t sensorId = 12345,
                          float   threshold = IMPACT_THRESHOLD_G);

    /** Initialise the ADXL345.  Returns false on communication error. */
    bool begin();

    /**
     * Poll the accelerometer.
     * @return true when a new valid blow is detected in this call.
     */
    bool update();

    /** Total blow count since last reset. */
    uint16_t getBlowCount() const { return _blowCount; }

    /** Magnitude of the last detected impact in g-forces. */
    float getLastImpactG() const { return _lastImpactG; }

    /** Timestamp (millis()) of the last detected blow. */
    unsigned long getLastBlowTime() const { return _lastBlowTime; }

    /** Reset blow counter and baseline. */
    void reset();

    /** Calibrate baseline noise over BASELINE_SAMPLES reads. */
    void calibrate();

private:
    Adafruit_ADXL345_Unified _adxl;
    float         _threshold;
    float         _baselineG;
    uint16_t      _blowCount;
    float         _lastImpactG;
    unsigned long _lastBlowTime;

    float _computeMagnitude(const sensors_event_t &event) const;
};
