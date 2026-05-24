#include "Touch.h"
#include "config.h"
#include <XPT2046_Touchscreen.h>

// XPT2046 raw readings are in 12-bit ADC space (0..4095); we map to the
// rotated screen coordinates (480x320 landscape). Calibration constants are
// approximate defaults - tweak per panel.

static XPT2046_Touchscreen ts(Pins::TOUCH_CS, Pins::TOUCH_IRQ);

// Raw-to-screen mapping. These values match common 3.5" ILI9488 + XPT2046
// modules in landscape rotation; if your touches land off-target, adjust.
static constexpr int16_t TS_X_MIN = 320;
static constexpr int16_t TS_X_MAX = 3900;
static constexpr int16_t TS_Y_MIN = 240;
static constexpr int16_t TS_Y_MAX = 3800;
static constexpr int16_t SCR_W    = 480;
static constexpr int16_t SCR_H    = 320;

Touch TouchPanel;

bool Touch::begin() {
    if (!ts.begin()) return false;
    ts.setRotation(1);
    return true;
}

void Touch::update() {
    bool raw = ts.touched();
    uint32_t now = millis();

    if (raw) {
        TS_Point p = ts.getPoint();
        // Map raw ADC to screen pixels.
        int16_t sx = map(p.x, TS_X_MIN, TS_X_MAX, 0, SCR_W);
        int16_t sy = map(p.y, TS_Y_MIN, TS_Y_MAX, 0, SCR_H);
        sx = constrain(sx, 0, SCR_W - 1);
        sy = constrain(sy, 0, SCR_H - 1);
        x_ = sx;
        y_ = sy;

        if (!pressed_) {
            // Edge: just pressed (with simple debounce by release gap).
            if ((now - releasedAtMs_) >= UI::TOUCH_DEBOUNCE_MS) {
                pressed_     = true;
                pressedAtMs_ = now;
                pressX_      = sx;
                pressY_      = sy;
                justPressed_ = true;
            }
        }
    } else {
        if (pressed_) {
            // Edge: just released.
            pressed_      = false;
            releasedAtMs_ = now;
            justReleased_ = true;

            // Detect tap: release came soon after press, no big movement.
            uint32_t held = now - pressedAtMs_;
            int16_t dx = x_ - pressX_;
            int16_t dy = y_ - pressY_;
            if (held < UI::LONG_PRESS_MS &&
                (dx * dx + dy * dy) < (20 * 20)) {
                tapPending_ = true;
                tapX_ = pressX_;
                tapY_ = pressY_;
            }
        }
    }
}

bool Touch::justPressed()  { bool e = justPressed_;  justPressed_  = false; return e; }
bool Touch::justReleased() { bool e = justReleased_; justReleased_ = false; return e; }

bool Touch::tappedRect(int16_t rx, int16_t ry, int16_t rw, int16_t rh) {
    if (!tapPending_) return false;
    if (tapX_ < rx || tapX_ >= rx + rw) return false;
    if (tapY_ < ry || tapY_ >= ry + rh) return false;
    tapPending_ = false;
    return true;
}
