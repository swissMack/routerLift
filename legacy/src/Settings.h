#pragma once
#include <Arduino.h>

// Debounced NVS persistence for live-tunable calibration values.
// begin() loads from NVS (or applies Mech/Safety defaults if a key is
// missing) and pushes the result into Motor/Zero/RouterRelay.
// scheduleSave() marks the data dirty; update() flushes to NVS once the
// user has been idle for SAVE_DEBOUNCE_MS. Debouncing avoids hammering
// NVS on every MPG pulse while the user is editing a value.

class Settings {
public:
    bool begin();         // call AFTER Motor.begin() / Zero / RouterRelay
    void scheduleSave();  // call from any menu edit that touches a persisted field
    void update();        // call from loop()

    static constexpr uint32_t SAVE_DEBOUNCE_MS = 2000;

private:
    bool     dirty_      = false;
    uint32_t lastEditMs_ = 0;
    void flush_();
};

extern Settings Config;
