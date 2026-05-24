#pragma once
#include <Arduino.h>

// Controls router power via SSR/relay. Enforces a configurable startup delay
// so the spindle reaches full speed before any motion is permitted.

class Relay {
public:
    bool begin();
    void turnOn();
    void turnOff();
    bool isOn() const         { return on_; }
    bool isReady() const;            // true once startup delay elapsed
    void setStartupDelayMs(uint16_t ms) { startupDelayMs_ = ms; }
    uint16_t startupDelayMs() const     { return startupDelayMs_; }

    uint32_t msSincePowerOn() const;

private:
    bool     on_              = false;
    uint32_t onAtMs_          = 0;
    uint16_t startupDelayMs_  = 2500;
};

extern Relay RouterRelay;
