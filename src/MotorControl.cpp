#include "MotorControl.h"
#include "config.h"
#include <FastAccelStepper.h>

// FastAccelStepper uses ESP32 hardware timers (RMT/MCPWM) for step generation.
// This gives us smooth ramps without CPU jitter, even while the main loop
// services the encoder, display, and I2C bus.

static FastAccelStepperEngine engine;
static FastAccelStepper *stepper = nullptr;

MotorControl Motor;

bool MotorControl::begin() {
    pinMode(Pins::STEPPER_ENABLE, OUTPUT);
    digitalWrite(Pins::STEPPER_ENABLE, HIGH); // DM542: HIGH = disabled

    engine.init();
    stepper = engine.stepperConnectToPin(Pins::STEPPER_STEP);
    if (!stepper) return false;

    stepper->setDirectionPin(Pins::STEPPER_DIR, dirInverted_);
    stepper->setEnablePin(Pins::STEPPER_ENABLE, /*low_active=*/true);
    stepper->setAutoEnable(false); // We control enable explicitly.

    applyProfile_();
    return true;
}

void MotorControl::applyProfile_() {
    if (!stepper) return;
    // FastAccelStepper wants steps/s and steps/s^2.
    uint32_t speedSps  = (uint32_t)(maxSpeedMmS_ * stepsPerRev_ / spindlePitchMm_);
    uint32_t accelSps2 = (uint32_t)(accelMmS2_   * stepsPerRev_ / spindlePitchMm_);
    if (speedSps  < 1) speedSps  = 1;
    if (accelSps2 < 1) accelSps2 = 1;
    stepper->setSpeedInHz(speedSps);
    stepper->setAcceleration(accelSps2);
}

// ---------- Calibration setters ----------
void MotorControl::setStepsPerRev(uint16_t s)   { stepsPerRev_ = s ? s : 1; applyProfile_(); }
void MotorControl::setSpindlePitchMm(float p)   { spindlePitchMm_ = p > 0.001f ? p : 0.001f; applyProfile_(); }
void MotorControl::setDirectionInverted(bool i) {
    dirInverted_ = i;
    if (stepper) stepper->setDirectionPin(Pins::STEPPER_DIR, dirInverted_);
}
void MotorControl::setMaxSpeedMmPerSec(float v) { maxSpeedMmS_ = v > 0 ? v : 1; applyProfile_(); }
void MotorControl::setAccelMmPerSec2(float a)   { accelMmS2_   = a > 0 ? a : 1; applyProfile_(); }
void MotorControl::setSoftLimits(float lo, float hi) {
    if (lo < hi) { softMinMm_ = lo; softMaxMm_ = hi; }
}

// ---------- Conversion ----------
int32_t MotorControl::mmToSteps(float mm) const {
    return (int32_t)lroundf(mm * (float)stepsPerRev_ / spindlePitchMm_);
}
float MotorControl::stepsToMm(int32_t steps) const {
    return (float)steps * spindlePitchMm_ / (float)stepsPerRev_;
}

// ---------- Motion ----------
bool MotorControl::withinLimits_(float mm) const {
    return mm >= softMinMm_ - 0.0001f && mm <= softMaxMm_ + 0.0001f;
}

bool MotorControl::moveToMm(float targetMm) {
    if (!stepper) return false;
    if (!withinLimits_(targetMm)) return false;
    enable(true);
    stepper->moveTo(mmToSteps(targetMm));
    return true;
}

bool MotorControl::moveRelativeMm(float deltaMm) {
    return moveToMm(currentPositionMm() + deltaMm);
}

void MotorControl::stop() {
    if (stepper) stepper->stopMove();
}

void MotorControl::emergencyStop() {
    if (stepper) stepper->forceStop();
    enable(false);
}

void MotorControl::jog(float mmPerSec) {
    if (!stepper) return;
    if (fabsf(mmPerSec) < 0.001f) { stepper->stopMove(); return; }

    // Clamp to max speed.
    if (mmPerSec >  maxSpeedMmS_) mmPerSec =  maxSpeedMmS_;
    if (mmPerSec < -maxSpeedMmS_) mmPerSec = -maxSpeedMmS_;

    // Respect soft limits: drive only toward valid range.
    float pos = currentPositionMm();
    if (mmPerSec > 0 && pos >= softMaxMm_) { stepper->stopMove(); return; }
    if (mmPerSec < 0 && pos <= softMinMm_) { stepper->stopMove(); return; }

    enable(true);
    uint32_t sps = (uint32_t)(fabsf(mmPerSec) * stepsPerRev_ / spindlePitchMm_);
    if (sps < 1) sps = 1;
    stepper->setSpeedInHz(sps);
    // runForward()/runBackward() makes the stepper run until stopped.
    if (mmPerSec > 0) stepper->runForward();
    else              stepper->runBackward();
}

// ---------- State ----------
float MotorControl::currentPositionMm() const {
    if (!stepper) return 0;
    return stepsToMm(stepper->getCurrentPosition());
}
int32_t MotorControl::currentPositionSteps() const {
    return stepper ? stepper->getCurrentPosition() : 0;
}
bool MotorControl::isMoving() const {
    return stepper && stepper->isRunning();
}
void MotorControl::setCurrentPositionMm(float mm) {
    if (stepper) stepper->setCurrentPosition(mmToSteps(mm));
}
void MotorControl::enable(bool on) {
    enabled_ = on;
    // DM542 enable is active-LOW. setEnablePin(..., true) inverts it for us.
    if (on) digitalWrite(Pins::STEPPER_ENABLE, LOW);
    else    digitalWrite(Pins::STEPPER_ENABLE, HIGH);
}
