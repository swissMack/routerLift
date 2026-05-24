#pragma once
#include <Arduino.h>

// Automatic tool-length zeroing using a spring-loaded brass stamp with an
// inductive sensor underneath. Drive slowly downward until the sensor
// triggers, then set position = stamp_offset (the calibrated height from
// trigger point to true table surface).

class Zeroing {
public:
    enum class State : uint8_t {
        IDLE,
        SEEK,
        FINE_SEEK,
        DONE,
        FAILED,
    };

    void start();
    void cancel();
    void update();

    bool   isActive() const { return state_ != State::IDLE && state_ != State::DONE && state_ != State::FAILED; }
    State  state() const    { return state_; }

    float  stampOffsetMm() const            { return stampOffsetMm_; }
    void   setStampOffsetMm(float mm)       { stampOffsetMm_ = mm; }

private:
    State    state_         = State::IDLE;
    uint32_t startedMs_     = 0;
    float    stampOffsetMm_ = 10.0;
    float    savedSpeed_    = 0;
};

extern Zeroing Zero;
