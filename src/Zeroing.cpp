#include "Zeroing.h"
#include "MotorControl.h"
#include "IOExpander.h"
#include "config.h"

Zeroing Zero;

void Zeroing::start() {
    if (isActive()) return;
    savedSpeed_ = Motor.maxSpeedMmPerSec();
    Motor.setMaxSpeedMmPerSec(Mech::DEFAULT_ZERO_SPEED_MM_S);
    Motor.enable(true);
    Motor.jog(-Mech::DEFAULT_ZERO_SPEED_MM_S);
    state_     = State::SEEK;
    startedMs_ = millis();
}

void Zeroing::cancel() {
    Motor.stop();
    Motor.setMaxSpeedMmPerSec(savedSpeed_);
    state_ = State::IDLE;
}

void Zeroing::update() {
    if (!isActive()) return;

    if ((millis() - startedMs_) > Safety::HOMING_TIMEOUT_MS) {
        Motor.emergencyStop();
        Motor.setMaxSpeedMmPerSec(savedSpeed_);
        state_ = State::FAILED;
        return;
    }

    switch (state_) {

    case State::SEEK:
        if (IO.readBrassStamp()) {
            Motor.stop();
            state_ = State::FINE_SEEK;
        }
        break;

    case State::FINE_SEEK:
        if (!Motor.isMoving()) {
            // Back off 1 mm then re-approach at quarter speed for accuracy.
            Motor.moveRelativeMm(+1.0);
        }
        if (!Motor.isMoving() && !IO.readBrassStamp()) {
            Motor.setMaxSpeedMmPerSec(Mech::DEFAULT_ZERO_SPEED_MM_S * 0.25f);
            Motor.jog(-Mech::DEFAULT_ZERO_SPEED_MM_S * 0.25f);
        }
        if (IO.readBrassStamp() && Motor.isMoving()) {
            Motor.stop();
            // Trigger height is stampOffsetMm above true zero.
            Motor.setCurrentPositionMm(stampOffsetMm_);
            Motor.setMaxSpeedMmPerSec(savedSpeed_);
            state_ = State::DONE;
            // Move to Park to clear the stamp.
            Motor.moveToMm(Mech::DEFAULT_PARK_MM);
        }
        break;

    default: break;
    }
}
