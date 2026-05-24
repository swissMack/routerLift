#include "RateSwitch.h"
#include "IOExpander.h"
#include "config.h"

RateSwitch Rate;

void RateSwitch::update() {
    uint32_t now = millis();
    if ((now - lastReadMs_) < 50) return;   // Poll at ~20 Hz
    lastReadMs_ = now;

    uint8_t m = IO.readRateMultiplier();
    switch (m) {
        case 1:   band_ = Band::X1;   break;
        case 10:  band_ = Band::X10;  break;
        case 100: band_ = Band::X100; break;
        default:  /* keep last known */ break;
    }
}

const char* RateSwitch::label() const {
    switch (band_) {
        case Band::X1:   return "x1";
        case Band::X10:  return "x10";
        case Band::X100: return "x100";
    }
    return "?";
}

float RateSwitch::baseStepMm() const {
    switch (band_) {
        case Band::X1:   return ::MPG::STEP_X1_MM;
        case Band::X10:  return ::MPG::STEP_X10_MM;
        case Band::X100: return ::MPG::STEP_X100_MM;
    }
    return ::MPG::STEP_X1_MM;
}
