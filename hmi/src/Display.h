#pragma once
//
// Display — NV3041A QSPI panel, GT911 touch, and LVGL plumbing.
//
// Board: Guition JC4827W543C. The QSPI bus and NV3041A constructor follow the
// Guition vendor example; pins are in hmi/include/pins.h. The panel is IPS and
// needs colour inversion, and both GT911 axes are mirrored against the panel
// at rotation 0.
//
// docs/4.3inch_ESP32-4827S043.zip is the vendor pack for a different (RGB
// parallel) board and is not a reference for this one.

#include <Arduino.h>
#include <lvgl.h>

class Display {
public:
    bool begin();          // false if the LVGL draw buffer could not be allocated
    void update();         // pump LVGL and handle backlight dimming

    uint16_t width()  const { return w_; }
    uint16_t height() const { return h_; }

    // Any touch or button press wakes the panel. It dims rather than blanking:
    // the height reading must always be visible (Q30).
    void noteActivity();
    bool isDimmed() const { return dimmed_; }

private:
    void setBacklight_(uint8_t duty);

    uint16_t w_ = 0, h_ = 0;
    uint32_t lastActivityMs_ = 0;
    bool     dimmed_ = false;
    bool     ok_ = false;
};

extern Display Screen;
