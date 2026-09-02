#include "Safety.h"
#include "MotorControl.h"
#include "Relay.h"
#include "IOExpander.h"
#include "config.h"
#include <esp_task_wdt.h>

SafetyMon Guard;

void SafetyMon::begin() {
    esp_task_wdt_init(Safety::WATCHDOG_TIMEOUT_S, true);
    esp_task_wdt_add(NULL);
}

void SafetyMon::update() {
    esp_task_wdt_reset();
    if (inFault()) return;

    // Endstop hit during normal motion (not homing) is a fault.
    extern class Homing Home;          // forward
    extern class Zeroing Zero;
    // The Homing/Zeroing modules expect endstop triggers; only fault
    // if we're outside those routines.
    // (Implemented in main.cpp where module state is visible.)
}

void SafetyMon::trigger(FaultCode c, const char* msg) {
    if (code_ != FaultCode::NONE) return; // first fault wins
    code_ = c;
    Motor.emergencyStop();
    RouterRelay.turnOff();
    if (msg) {
        strncpy(message_, msg, sizeof(message_) - 1);
        message_[sizeof(message_) - 1] = '\0';
    } else {
        message_[0] = '\0';
    }
}

void SafetyMon::acknowledge() {
    code_ = FaultCode::NONE;
    message_[0] = '\0';
}

const char* SafetyMon::codeName() const {
    switch (code_) {
        case FaultCode::NONE:                return "OK";
        case FaultCode::ENDSTOP_HIT:         return "Endstop hit";
        case FaultCode::HOMING_TIMEOUT:      return "Homing timeout";
        case FaultCode::ZEROING_TIMEOUT:     return "Zeroing timeout";
        case FaultCode::SOFT_LIMIT_VIOLATED: return "Soft limit";
        case FaultCode::I2C_LOST:            return "I2C lost";
        case FaultCode::UNKNOWN_BOARD:       return "Unknown board";
    }
    return "?";
}
