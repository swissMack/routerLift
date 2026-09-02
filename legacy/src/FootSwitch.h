#pragma once
#include <Arduino.h>

// Debounced foot-switch reader (via MCP23017).
// Press = drive to target height; Release = return to Park.

class FootSwitch {
public:
    void update();   // Call from loop().

    bool isPressed() const     { return stable_; }
    bool justPressed()         { bool e = justPressed_;  justPressed_  = false; return e; }
    bool justReleased()        { bool e = justReleased_; justReleased_ = false; return e; }

private:
    bool     stable_        = false;
    bool     lastRaw_       = false;
    uint32_t changedMs_     = 0;
    bool     justPressed_   = false;
    bool     justReleased_  = false;
};

extern FootSwitch Foot;
