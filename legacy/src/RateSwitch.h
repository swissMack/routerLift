#pragma once
#include <Arduino.h>

// 3-position hardware rotary switch sets the base step-size band for the MPG.
// Polled (not interrupt-driven) since position changes are infrequent.

class RateSwitch {
public:
    enum class Band : uint8_t { X1 = 1, X10 = 10, X100 = 100 };

    void update();   // Call from loop().

    Band  band() const         { return band_; }
    float multiplier() const   { return (float)(uint8_t)band_; }
    const char* label() const;

    // Base step (mm per MPG pulse) at slow turn rate for the current band.
    float baseStepMm() const;

private:
    Band     band_       = Band::X1;       // safe default if switch missing
    uint32_t lastReadMs_ = 0;
};

extern RateSwitch Rate;
