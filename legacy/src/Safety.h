#pragma once
#include <Arduino.h>

// Centralised fault handling. Any subsystem can trigger a fault, which
// emergency-stops the motor and forces the relay off. Recovery requires
// explicit user acknowledgement.

enum class FaultCode : uint8_t {
    NONE = 0,
    ENDSTOP_HIT,
    HOMING_TIMEOUT,
    ZEROING_TIMEOUT,
    SOFT_LIMIT_VIOLATED,
    I2C_LOST,
    UNKNOWN_BOARD,
};

class SafetyMon {
public:
    void begin();
    void update();

    void trigger(FaultCode code, const char* msg = nullptr);
    void acknowledge();   // Clear fault after user input.

    bool        inFault() const   { return code_ != FaultCode::NONE; }
    FaultCode   code() const      { return code_; }
    const char* message() const   { return message_; }
    const char* codeName() const;

private:
    FaultCode code_ = FaultCode::NONE;
    char      message_[64] = {0};
};

extern SafetyMon Guard;
