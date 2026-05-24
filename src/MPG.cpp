#include "MPG.h"
#include "config.h"
#include "RateSwitch.h"
#include <ESP32Encoder.h>

// MPG signals come through 74HCT14 or PC817 opto-isolators. Opto inverts the
// signal; we accommodate this via MPG::SIGNALS_INVERTED in config.h.
//
// PCNT (pulse counter) on ESP32 handles the high pulse rate of a 100 PPR
// wheel spun briskly with no risk of missed counts.

static ESP32Encoder mpg;

MPG Wheel;

bool MPG::begin() {
    ESP32Encoder::useInternalWeakPullResistors = puType::up;
    // Full quadrature: 4 transitions per MPG pulse. We divide by 4 in update().
    mpg.attachFullQuad(Pins::MPG_A, Pins::MPG_B);
    mpg.clearCount();
    return true;
}

void MPG::update() {
    int64_t now = mpg.getCount();
    int32_t raw = (int32_t)(now - lastCount_);
    lastCount_ = now;

    // Full-quad gives 4 counts per detent/pulse. Inverted signals reverse direction.
    int32_t pulses = raw / 4;
    if (MPGCfg::SIGNALS_INVERTED) pulses = -pulses;

    if (pulses != 0) {
        pendingPulses_ += pulses;
        updateScaling_(pulses);
    } else {
        // Decay velocity when no pulses arrive.
        uint32_t since = millis() - lastPulseMs_;
        if (since > 120) {
            pulsesPerSec_ *= 0.85f;
            if (pulsesPerSec_ < 0.5f) pulsesPerSec_ = 0;
            stepMm_ = Rate.baseStepMm();   // collapse to base step
        }
    }
}

void MPG::updateScaling_(int32_t pulses) {
    uint32_t now = millis();
    uint32_t dt  = now - lastPulseMs_;
    lastPulseMs_ = now;
    if (dt == 0) dt = 1;

    float instHz = (1000.0f * fabsf((float)pulses)) / (float)dt;
    pulsesPerSec_ = 0.6f * pulsesPerSec_ + 0.4f * instHz;

    // Map pulses/sec to a scale factor between 1.0 and VELOCITY_SCALE_MAX.
    float scale;
    if (pulsesPerSec_ <= MPGCfg::VEL_PPS_LOW) {
        scale = 1.0f;
    } else if (pulsesPerSec_ >= MPGCfg::VEL_PPS_HIGH) {
        scale = MPGCfg::VELOCITY_SCALE_MAX;
    } else {
        float t = (pulsesPerSec_ - MPGCfg::VEL_PPS_LOW) /
                  (MPGCfg::VEL_PPS_HIGH - MPGCfg::VEL_PPS_LOW);
        scale = 1.0f + t * (MPGCfg::VELOCITY_SCALE_MAX - 1.0f);
    }
    stepMm_ = Rate.baseStepMm() * scale;
}

int32_t MPG::consumePulses() {
    int32_t p = pendingPulses_;
    pendingPulses_ = 0;
    return p;
}
