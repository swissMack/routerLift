#pragma once
#include <Arduino.h>

// XPT2046 touch controller wrapper.
// - Shares SPI bus with the TFT (different CS line).
// - Polled in loop(); IRQ pin available for future power-saving use.
// - Exposes button-style API: rectangular hit-tests with debounce.

class Touch {
public:
    bool begin();
    void update();      // Call from loop().

    // Current touch state (debounced).
    bool isPressed() const    { return pressed_; }
    int16_t x() const         { return x_; }
    int16_t y() const         { return y_; }

    // Edge events - read-and-clear.
    bool justPressed();
    bool justReleased();

    // Did the user tap inside (x, y, w, h) since last call?
    // "Tap" = press-and-release with no movement outside the rect.
    bool tappedRect(int16_t rx, int16_t ry, int16_t rw, int16_t rh);

private:
    bool     pressed_       = false;
    int16_t  x_             = -1;
    int16_t  y_             = -1;
    uint32_t pressedAtMs_   = 0;
    uint32_t releasedAtMs_  = 0;
    int16_t  pressX_        = -1;
    int16_t  pressY_        = -1;
    bool     justPressed_   = false;
    bool     justReleased_  = false;
    bool     tapPending_    = false;
    int16_t  tapX_          = -1;
    int16_t  tapY_          = -1;
};

extern Touch TouchPanel;
