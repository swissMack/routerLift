#pragma once
//
// Display — RGB panel, GT911 touch, and LVGL plumbing.
//
// The panel constructor and timings are copied VERBATIM from the vendor demo
// at docs/4.3inch_ESP32-4827S043.zip:
//   1-Demo/Demo_Arduino/3_3-4_TFT-LVGL-Widgets/LvglWidgets/
//
// Do not "improve" them from the datasheet. The demo is what is proven to work
// on this board; the porch and pclk values in particular are not obvious and
// getting them wrong gives a rolling or blank panel rather than a clean error.
//
// The zip is gitignored (112 MB, over GitHub's file limit) and exists only on
// the build machine.

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
