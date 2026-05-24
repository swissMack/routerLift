#pragma once
#include <Arduino.h>

// Homing drives the lift downward until the bottom endstop triggers, then
// backs off a small distance and re-approaches slowly for accuracy.
// On success the motor's logical position is set to softMinMm.

class Homing {
public:
    enum class State : uint8_t {
        IDLE,
        SEEK_FAST,
        BACKOFF,
        SEEK_SLOW,
        DONE,
        FAILED,
    };

    void start();
    void cancel();
    void update();   // Call from loop().

    bool isActive() const { return state_ != State::IDLE && state_ != State::DONE && state_ != State::FAILED; }
    bool isHomed() const  { return homed_; }
    State state() const   { return state_; }
    const char* stateName() const;

private:
    State    state_      = State::IDLE;
    bool     homed_      = false;
    uint32_t startedMs_  = 0;
    float    savedAccel_ = 0;
    float    savedSpeed_ = 0;
};

extern Homing Home;
