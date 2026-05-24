#pragma once
#include <Arduino.h>

// Touch-driven hierarchical menu.
// MPG = jog (main) or value editor (calibration fields).
// Touch = navigate menus, tap buttons, enter/exit edit modes.

class Menu {
public:
    enum class Screen : uint8_t {
        MAIN,
        ROOT_MENU,
        PRESET_PICKER,
        PRESET_SAVE,
        CALIB_MOTOR,
        CALIB_MOTION,
        CALIB_LIMITS,
        CALIB_SENSORS,
        SET_TARGET,
        FAULT_VIEW,
        HOMING_VIEW,
        ZEROING_VIEW,
    };

    void begin();
    void update();

    Screen current() const     { return screen_; }
    void   go(Screen s);

    float  targetMm() const    { return targetMm_; }
    void   setTargetMm(float m) { targetMm_ = m; }

    // True while a calibration row is in "edit" mode (MPG changes value).
    bool   isEditing() const   { return editing_; }
    int8_t cursor()    const   { return cursor_; }

    // Item count for the current calibration screen (used by Display).
    int8_t calibItemCount() const;

private:
    Screen screen_   = Screen::MAIN;
    int8_t cursor_   = 0;
    bool   editing_  = false;
    float  targetMm_ = 10.0;

    // Per-screen handlers.
    void handleMain_();
    void handleRoot_();
    void handlePresetPicker_(bool saving);
    void handleSetTarget_();
    void handleCalibMotor_();
    void handleCalibMotion_();
    void handleCalibLimits_();
    void handleCalibSensors_();
    void handleFaultView_();

    // Common helpers.
    bool tappedBack_();
    void calibValueEdit_(int32_t pulses);
};

extern Menu UIMenu;
