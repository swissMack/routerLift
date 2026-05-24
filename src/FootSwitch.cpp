#include "FootSwitch.h"
#include "IOExpander.h"
#include "config.h"

FootSwitch Foot;

void FootSwitch::update() {
    bool raw = IO.readFootSwitch();  // true = pressed
    uint32_t now = millis();
    if (raw != lastRaw_) {
        lastRaw_   = raw;
        changedMs_ = now;
    }
    if ((now - changedMs_) >= UI::BUTTON_DEBOUNCE_MS && raw != stable_) {
        stable_ = raw;
        if (stable_) justPressed_  = true;
        else         justReleased_ = true;
    }
}
