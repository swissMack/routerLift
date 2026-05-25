#include "Menu.h"
#include "MPG.h"
#include "Touch.h"
#include "MotorControl.h"
#include "Presets.h"
#include "Homing.h"
#include "Zeroing.h"
#include "Relay.h"
#include "Safety.h"
#include "Settings.h"
#include "config.h"

Menu UIMenu;

// --------------------------------------------------------------------------
// Layout constants - must match Display.cpp button positions.
// Centralised here so Menu can hit-test against the same regions Display draws.
// --------------------------------------------------------------------------
namespace Layout {
    // Bottom button bar (shared across most screens).
    constexpr int16_t BAR_Y      = 240;
    constexpr int16_t BAR_H      = 58;
    constexpr int16_t BTN_GAP    = 8;

    // Main screen bottom-bar buttons: MENU, PARK, POWER
    constexpr int16_t MAIN_BTN_W = 150;

    // Menu rows.
    constexpr int16_t ROW_Y0     = 42;
    constexpr int16_t ROW_H      = 24;
    constexpr int16_t ROW_W      = 480;

    // Back button (top-right of menu screens).
    constexpr int16_t BACK_X = 380;
    constexpr int16_t BACK_Y = 2;
    constexpr int16_t BACK_W = 96;
    constexpr int16_t BACK_H = 28;

    // OK / CANCEL buttons used by SET_TARGET.
    constexpr int16_t OK_X     = 80;
    constexpr int16_t CANCEL_X = 250;
    constexpr int16_t OK_W     = 150;
    constexpr int16_t OK_H     = 58;
}

static const char* ROOT_ITEMS[] = {
    "Recall Preset",
    "Save Preset",
    "Set Target",
    "Home",
    "Zero Tool",
    "Router Power",
    "Calibrate Motor",
    "Calibrate Motion",
    "Calibrate Limits",
    "Calibrate Sensors",
};
static const uint8_t ROOT_COUNT = sizeof(ROOT_ITEMS) / sizeof(ROOT_ITEMS[0]);

void Menu::begin() {
    screen_ = Screen::MAIN;
    cursor_ = 0;
}

void Menu::go(Screen s) {
    screen_  = s;
    cursor_  = 0;
    editing_ = false;
}

bool Menu::tappedBack_() {
    return TouchPanel.tappedRect(Layout::BACK_X, Layout::BACK_Y,
                                 Layout::BACK_W, Layout::BACK_H);
}

void Menu::update() {
    if (Guard.inFault())          { screen_ = Screen::FAULT_VIEW; }
    else if (Home.isActive())     { screen_ = Screen::HOMING_VIEW; }
    else if (Zero.isActive())     { screen_ = Screen::ZEROING_VIEW; }

    switch (screen_) {
        case Screen::MAIN:           handleMain_();              break;
        case Screen::ROOT_MENU:      handleRoot_();              break;
        case Screen::PRESET_PICKER:  handlePresetPicker_(false); break;
        case Screen::PRESET_SAVE:    handlePresetPicker_(true);  break;
        case Screen::SET_TARGET:     handleSetTarget_();         break;
        case Screen::CALIB_MOTOR:    handleCalibMotor_();        break;
        case Screen::CALIB_MOTION:   handleCalibMotion_();       break;
        case Screen::CALIB_LIMITS:   handleCalibLimits_();       break;
        case Screen::CALIB_SENSORS:  handleCalibSensors_();      break;
        case Screen::FAULT_VIEW:     handleFaultView_();         break;
        case Screen::HOMING_VIEW:
        case Screen::ZEROING_VIEW:
            if (!Home.isActive() && !Zero.isActive()) go(Screen::MAIN);
            (void)Wheel.consumePulses();
            break;
    }
}

// ---------------- MAIN ----------------------------------------------------
void Menu::handleMain_() {
    // MPG jogs the lift.
    int32_t p = Wheel.consumePulses();
    if (p != 0) {
        Motor.moveRelativeMm(p * Wheel.currentStepMm());
    }

    // Bottom-bar buttons.
    int16_t y = Layout::BAR_Y;
    int16_t x = Layout::BTN_GAP;
    if (TouchPanel.tappedRect(x, y, Layout::MAIN_BTN_W, Layout::BAR_H)) {
        go(Screen::ROOT_MENU);
        return;
    }
    x += Layout::MAIN_BTN_W + Layout::BTN_GAP;
    if (TouchPanel.tappedRect(x, y, Layout::MAIN_BTN_W, Layout::BAR_H)) {
        Motor.moveToMm(Mech::DEFAULT_PARK_MM);
        return;
    }
    x += Layout::MAIN_BTN_W + Layout::BTN_GAP;
    if (TouchPanel.tappedRect(x, y, Layout::MAIN_BTN_W, Layout::BAR_H)) {
        if (RouterRelay.isOn()) RouterRelay.turnOff();
        else                    RouterRelay.turnOn();
        return;
    }
}

// ---------------- ROOT MENU -----------------------------------------------
void Menu::handleRoot_() {
    (void)Wheel.consumePulses();  // discard - menu uses touch

    if (tappedBack_()) { go(Screen::MAIN); return; }

    for (uint8_t i = 0; i < ROOT_COUNT; ++i) {
        int16_t y = Layout::ROW_Y0 + i * Layout::ROW_H;
        if (TouchPanel.tappedRect(0, y, Layout::ROW_W, Layout::ROW_H)) {
            switch (i) {
                case 0: go(Screen::PRESET_PICKER); break;
                case 1: go(Screen::PRESET_SAVE);   break;
                case 2: targetMm_ = Motor.currentPositionMm(); go(Screen::SET_TARGET); break;
                case 3: Home.start();              go(Screen::HOMING_VIEW); break;
                case 4: Zero.start();              go(Screen::ZEROING_VIEW); break;
                case 5: RouterRelay.isOn() ? RouterRelay.turnOff() : RouterRelay.turnOn(); break;
                case 6: go(Screen::CALIB_MOTOR);   break;
                case 7: go(Screen::CALIB_MOTION);  break;
                case 8: go(Screen::CALIB_LIMITS);  break;
                case 9: go(Screen::CALIB_SENSORS); break;
            }
            return;
        }
    }
}

// ---------------- PRESET PICKER -------------------------------------------
void Menu::handlePresetPicker_(bool saving) {
    (void)Wheel.consumePulses();
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }

    for (uint8_t i = 0; i < UI::NUM_PRESETS; ++i) {
        int16_t y = 50 + i * 32;
        if (TouchPanel.tappedRect(0, y, 480, 32)) {
            if (saving) {
                PresetStore.save(i, Motor.currentPositionMm());
            } else if (PresetStore.isSet(i)) {
                PresetStore.setActiveSlot(i);
                Motor.moveToMm(PresetStore.load(i));
            }
            go(Screen::MAIN);
            return;
        }
    }
}

// ---------------- SET TARGET ----------------------------------------------
void Menu::handleSetTarget_() {
    int32_t p = Wheel.consumePulses();
    if (p != 0) targetMm_ += p * Wheel.currentStepMm();
    if (targetMm_ < Motor.softMinMm()) targetMm_ = Motor.softMinMm();
    if (targetMm_ > Motor.softMaxMm()) targetMm_ = Motor.softMaxMm();

    // OK and CANCEL touch zones.
    if (TouchPanel.tappedRect(Layout::OK_X, Layout::BAR_Y,
                              Layout::OK_W, Layout::OK_H)) {
        go(Screen::ROOT_MENU);
        return;
    }
    if (TouchPanel.tappedRect(Layout::CANCEL_X, Layout::BAR_Y,
                              Layout::OK_W, Layout::OK_H)) {
        go(Screen::ROOT_MENU);
        return;
    }
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }
}

// ---------------- CALIBRATION SCREENS -------------------------------------
// Common pattern: each row has a tappable area. Tapping toggles edit mode
// for that row; while editing, MPG pulses change the value.

void Menu::calibValueEdit_(int32_t /*pulses*/) { /* implemented per-screen */ }

int8_t Menu::calibItemCount() const {
    switch (screen_) {
        case Screen::CALIB_MOTOR:   return 3;  // steps/rev, pitch, dir
        case Screen::CALIB_MOTION:  return 2;  // max speed, accel
        case Screen::CALIB_LIMITS:  return 2;  // soft min, soft max
        case Screen::CALIB_SENSORS: return 2;  // stamp offset, relay delay
        default: return 0;
    }
}

static int8_t hitCalibRow(int8_t n) {
    for (int8_t i = 0; i < n; ++i) {
        int16_t y = 50 + i * 38;
        if (TouchPanel.tappedRect(0, y, 480, 32)) return i;
    }
    return -1;
}

void Menu::handleCalibMotor_() {
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }

    int8_t row = hitCalibRow(3);
    if (row >= 0) {
        if (cursor_ == row) editing_ = !editing_;
        else { cursor_ = row; editing_ = true; }
    }

    int32_t p = Wheel.consumePulses();
    if (editing_ && p != 0) {
        switch (cursor_) {
            case 0: Motor.setStepsPerRev(Motor.stepsPerRev() + p * 100); break;
            case 1: Motor.setSpindlePitchMm(Motor.spindlePitchMm() + p * 0.1f); break;
            case 2: Motor.setDirectionInverted(!Motor.dirInverted()); break;
        }
        Config.scheduleSave();
    }
}

void Menu::handleCalibMotion_() {
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }

    int8_t row = hitCalibRow(2);
    if (row >= 0) {
        if (cursor_ == row) editing_ = !editing_;
        else { cursor_ = row; editing_ = true; }
    }

    int32_t p = Wheel.consumePulses();
    if (editing_ && p != 0) {
        switch (cursor_) {
            case 0: Motor.setMaxSpeedMmPerSec(Motor.maxSpeedMmPerSec() + p * 1.0f); break;
            case 1: Motor.setAccelMmPerSec2(Motor.accelMmPerSec2() + p * 10.0f); break;
        }
        Config.scheduleSave();
    }
}

void Menu::handleCalibLimits_() {
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }

    int8_t row = hitCalibRow(2);
    if (row >= 0) {
        if (cursor_ == row) editing_ = !editing_;
        else { cursor_ = row; editing_ = true; }
    }

    int32_t p = Wheel.consumePulses();
    if (editing_ && p != 0) {
        float lo = Motor.softMinMm();
        float hi = Motor.softMaxMm();
        if (cursor_ == 0) { lo += p * 0.5f; Motor.setSoftLimits(lo, hi); }
        if (cursor_ == 1) { hi += p * 0.5f; Motor.setSoftLimits(lo, hi); }
        Config.scheduleSave();
    }
}

void Menu::handleCalibSensors_() {
    if (tappedBack_()) { go(Screen::ROOT_MENU); return; }

    int8_t row = hitCalibRow(2);
    if (row >= 0) {
        if (cursor_ == row) editing_ = !editing_;
        else { cursor_ = row; editing_ = true; }
    }

    int32_t p = Wheel.consumePulses();
    if (editing_ && p != 0) {
        if (cursor_ == 0) {
            Zero.setStampOffsetMm(Zero.stampOffsetMm() + p * 0.1f);
        } else if (cursor_ == 1) {
            int32_t v = (int32_t)RouterRelay.startupDelayMs() + p * 100;
            if (v < 0)     v = 0;
            if (v > 30000) v = 30000;
            RouterRelay.setStartupDelayMs((uint16_t)v);
        }
        Config.scheduleSave();
    }
}

// ---------------- FAULT VIEW ----------------------------------------------
void Menu::handleFaultView_() {
    (void)Wheel.consumePulses();
    // Any tap on the lower half of the screen acknowledges the fault.
    if (TouchPanel.tappedRect(0, 200, 480, 120)) {
        Guard.acknowledge();
        go(Screen::MAIN);
    }
}
