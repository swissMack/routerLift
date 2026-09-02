#include "Homing.h"
#include "MotorControl.h"
#include "IOExpander.h"
#include "config.h"

Homing Home;

void Homing::start() {
    if (isActive()) return;
    savedSpeed_ = Motor.maxSpeedMmPerSec();
    savedAccel_ = Motor.accelMmPerSec2();
    Motor.setMaxSpeedMmPerSec(Mech::DEFAULT_HOMING_SPEED_MM_S);
    Motor.enable(true);
    Motor.jog(-Mech::DEFAULT_HOMING_SPEED_MM_S); // drive toward bottom endstop
    state_      = State::SEEK_FAST;
    startedMs_  = millis();
    homed_      = false;
}

void Homing::cancel() {
    Motor.stop();
    Motor.setMaxSpeedMmPerSec(savedSpeed_);
    Motor.setAccelMmPerSec2(savedAccel_);
    state_ = State::IDLE;
}

void Homing::update() {
    if (!isActive()) return;

    // Hard timeout - something is wrong if homing takes this long.
    if ((millis() - startedMs_) > Safety::HOMING_TIMEOUT_MS) {
        Motor.emergencyStop();
        state_ = State::FAILED;
        return;
    }

    switch (state_) {

    case State::SEEK_FAST:
        if (IO.readEndstopBottom()) {
            Motor.stop();
            // Back off so we can re-approach slowly for accuracy.
            // Use a brief delay via state; FastAccelStepper stops with ramp,
            // so we set up the next move once it's truly stopped.
            state_ = State::BACKOFF;
        }
        break;

    case State::BACKOFF:
        if (!Motor.isMoving()) {
            Motor.setMaxSpeedMmPerSec(Mech::DEFAULT_HOMING_SPEED_MM_S);
            Motor.setCurrentPositionMm(Motor.softMinMm()); // provisional
            Motor.moveRelativeMm(+2.0);                    // back off 2 mm
            state_ = State::SEEK_SLOW;
        }
        break;

    case State::SEEK_SLOW:
        if (!Motor.isMoving()) {
            // Slow re-approach for precision trigger.
            Motor.setMaxSpeedMmPerSec(Mech::DEFAULT_HOMING_SPEED_MM_S * 0.25f);
            Motor.jog(-Mech::DEFAULT_HOMING_SPEED_MM_S * 0.25f);
        }
        if (IO.readEndstopBottom()) {
            Motor.stop();
            Motor.setCurrentPositionMm(Motor.softMinMm());
            // Restore motion profile.
            Motor.setMaxSpeedMmPerSec(savedSpeed_);
            Motor.setAccelMmPerSec2(savedAccel_);
            homed_ = true;
            state_ = State::DONE;
            // Park.
            Motor.moveToMm(Mech::DEFAULT_PARK_MM);
        }
        break;

    default: break;
    }
}

const char* Homing::stateName() const {
    switch (state_) {
        case State::IDLE:      return "IDLE";
        case State::SEEK_FAST: return "SEEK FAST";
        case State::BACKOFF:   return "BACKOFF";
        case State::SEEK_SLOW: return "SEEK SLOW";
        case State::DONE:      return "DONE";
        case State::FAILED:    return "FAILED";
    }
    return "?";
}
