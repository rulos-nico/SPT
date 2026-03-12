#pragma once
/**
 * penetration_sensor.h
 * Measures sampler penetration depth using a quadrature rotary encoder.
 * A/B encoder channels are connected to two digital interrupt pins.
 * Pulses are converted to millimetres using the encoder resolution and
 * the mechanical coupling ratio (mm per encoder revolution).
 */

#include <Arduino.h>

// Default: 600 pulse/rev encoder, 2 mm/rev lead-screw coupling → 0.00333 mm/pulse
#define ENCODER_PPR            600
#define MM_PER_REV             2.0f
#define MM_PER_PULSE           (MM_PER_REV / (ENCODER_PPR))

class PenetrationSensor {
public:
    /**
     * @param pinA     Interrupt-capable pin for encoder channel A.
     * @param pinB     Pin for encoder channel B (direction sense).
     * @param mmPerPulse Mechanical calibration factor (mm per encoder pulse).
     */
    PenetrationSensor(uint8_t pinA,
                      uint8_t pinB,
                      float   mmPerPulse = MM_PER_PULSE);

    /** Attach interrupt and initialise state. */
    void begin();

    /** Current absolute depth in millimetres from the zero reference. */
    float getDepthMm() const;

    /** Increment since the last call to resetDelta(). */
    float getDeltaMm() const;

    /** Zero the absolute depth and incremental counters. */
    void zero();

    /** Reset only the incremental delta counter. */
    void resetDelta();

    /** Raw pulse count (can be negative for upward movement). */
    int32_t getPulseCount() const;

    // Called from the ISR – must be public but should not be used directly.
    void IRAM_ATTR handleInterrupt();

private:
    uint8_t   _pinA;
    uint8_t   _pinB;
    float     _mmPerPulse;
    volatile int32_t _pulseCount;
    int32_t   _deltaBaseline;
};
