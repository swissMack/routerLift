#pragma once
#include <Arduino.h>

class Display {
public:
    bool begin();
    void update();

private:
    uint32_t lastRenderMs_ = 0;

    void renderMain_();
    void renderRoot_();
    void renderPresetPicker_(bool saving);
    void renderSetTarget_();
    void renderCalibMotor_();
    void renderCalibMotion_();
    void renderCalibLimits_();
    void renderCalibSensors_();
    void renderHoming_();
    void renderZeroing_();
    void renderFault_();
    void renderHeader_(const char* title, bool drawBackButton);
    void renderStatusBar_();
    void drawButton_(int16_t x, int16_t y, int16_t w, int16_t h,
                     const char* label, uint16_t bg);
};

extern Display Screen;
