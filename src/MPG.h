#pragma once
#include <Arduino.h>

// Manual pulse generator (CNC-style MPG) input.
// - 100 PPR continuous quadrature, no detents.
// - Step size = baseStep (from RateSwitch) * velocityScale (1.0 .. VELOCITY_SCALE_MAX)
// - No button; menu navigation is via touch.

class MPG {
public:
    bool begin();
    void update();   // Call from loop().

    // Pulses (signed) accumulated since last call.
    int32_t consumePulses();

    // Current effective mm per pulse (band * velocity scaling).
    float currentStepMm() const   { return stepMm_; }

    // For display / diagnostics.
    float pulsesPerSecond() const { return pulsesPerSec_; }

private:
    int64_t  lastCount_     = 0;
    int32_t  pendingPulses_ = 0;
    uint32_t lastPulseMs_   = 0;
    float    pulsesPerSec_  = 0;
    float    stepMm_        = 0.001;

    void updateScaling_(int32_t pulses);
};

extern MPG Wheel;
