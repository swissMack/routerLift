#include "Display.h"
#include "Menu.h"
#include "MotorControl.h"
#include "Presets.h"
#include "Homing.h"
#include "Zeroing.h"
#include "Relay.h"
#include "Safety.h"
#include "FunctionBoard.h"
#include "MPG.h"
#include "RateSwitch.h"
#include "config.h"
#include <TFT_eSPI.h>

static TFT_eSPI    tft;
static TFT_eSprite spr(&tft);

Display Screen;

static constexpr int16_t W = 480;
static constexpr int16_t H = 320;

// Colours.
static constexpr uint16_t COL_BG     = TFT_BLACK;
static constexpr uint16_t COL_HDR    = 0x2104;
static constexpr uint16_t COL_FG     = TFT_WHITE;
static constexpr uint16_t COL_ACCENT = 0x07E0;   // bright green
static constexpr uint16_t COL_WARN   = 0xFD20;   // amber
static constexpr uint16_t COL_FAULT  = 0xF800;   // red
static constexpr uint16_t COL_DIM    = 0x8410;
static constexpr uint16_t COL_BTN    = 0x18C3;   // dark slate
static constexpr uint16_t COL_BTN_OK = 0x05E0;
static constexpr uint16_t COL_BTN_NO = 0x9000;

bool Display::begin() {
    tft.init();
    tft.setRotation(1);
    tft.fillScreen(COL_BG);

    spr.setColorDepth(8);
    if (!spr.createSprite(W, H)) return false;
    spr.setTextDatum(TL_DATUM);
    return true;
}

void Display::update() {
    uint32_t now = millis();
    if ((now - lastRenderMs_) < UI::DISPLAY_REFRESH_MS) return;
    lastRenderMs_ = now;

    spr.fillSprite(COL_BG);

    switch (UIMenu.current()) {
        case Menu::Screen::MAIN:           renderMain_();              break;
        case Menu::Screen::ROOT_MENU:      renderRoot_();              break;
        case Menu::Screen::PRESET_PICKER:  renderPresetPicker_(false); break;
        case Menu::Screen::PRESET_SAVE:    renderPresetPicker_(true);  break;
        case Menu::Screen::SET_TARGET:     renderSetTarget_();         break;
        case Menu::Screen::CALIB_MOTOR:    renderCalibMotor_();        break;
        case Menu::Screen::CALIB_MOTION:   renderCalibMotion_();       break;
        case Menu::Screen::CALIB_LIMITS:   renderCalibLimits_();       break;
        case Menu::Screen::CALIB_SENSORS:  renderCalibSensors_();      break;
        case Menu::Screen::HOMING_VIEW:    renderHoming_();            break;
        case Menu::Screen::ZEROING_VIEW:   renderZeroing_();           break;
        case Menu::Screen::FAULT_VIEW:     renderFault_();             break;
    }
    renderStatusBar_();
    spr.pushSprite(0, 0);
}

void Display::drawButton_(int16_t x, int16_t y, int16_t w, int16_t h,
                          const char* label, uint16_t bg) {
    spr.fillRoundRect(x, y, w, h, 6, bg);
    spr.drawRoundRect(x, y, w, h, 6, COL_FG);
    spr.setTextColor(COL_FG, bg);
    spr.setTextSize(2);
    int16_t tw = spr.textWidth(label);
    spr.setCursor(x + (w - tw) / 2, y + (h - 16) / 2);
    spr.print(label);
}

void Display::renderHeader_(const char* title, bool drawBackButton) {
    spr.fillRect(0, 0, W, 32, COL_HDR);
    spr.setTextColor(COL_FG, COL_HDR);
    spr.setTextSize(2);
    spr.setCursor(8, 8);
    spr.print(title);
    if (drawBackButton) drawButton_(380, 2, 96, 28, "BACK", COL_BTN_NO);
}

void Display::renderStatusBar_() {
    spr.fillRect(0, H - 16, W, 16, COL_HDR);
    spr.setTextColor(COL_DIM, COL_HDR);
    spr.setTextSize(1);
    spr.setCursor(6, H - 12);
    spr.printf("%s v%s | Rate:%s | Relay:%s | %s",
        Board.name(), FW_VERSION, Rate.label(),
        RouterRelay.isOn() ? (RouterRelay.isReady() ? "ON" : "WARMUP") : "off",
        Home.isHomed() ? "homed" : "NOT homed");
}

// ---------------- MAIN -----------------------------------------------------
void Display::renderMain_() {
    renderHeader_("Router Lift", false);

    // Big position readout.
    spr.setTextColor(COL_ACCENT, COL_BG);
    spr.setTextSize(6);
    spr.setCursor(20, 45);
    spr.printf("%7.2f", Motor.currentPositionMm());
    spr.setTextSize(2);
    spr.setCursor(380, 90);
    spr.print("mm");

    // Mid-zone info.
    spr.setTextColor(COL_FG, COL_BG);
    spr.setTextSize(2);
    spr.setCursor(20, 130);  spr.printf("Target: %7.2f mm", UIMenu.targetMm());
    spr.setCursor(20, 154);  spr.printf("Park  : %7.2f mm", Mech::DEFAULT_PARK_MM);
    spr.setCursor(20, 178);
    spr.setTextColor(COL_WARN, COL_BG);
    spr.printf("Rate %s | %.3f mm/pulse", Rate.label(), Wheel.currentStepMm());

    // Active preset banner.
    spr.setCursor(20, 208);
    if (PresetStore.isSet(PresetStore.activeSlot())) {
        spr.setTextColor(COL_ACCENT, COL_BG);
        spr.printf("Preset %u: %.2f mm",
            PresetStore.activeSlot() + 1,
            PresetStore.load(PresetStore.activeSlot()));
    } else {
        spr.setTextColor(COL_DIM, COL_BG);
        spr.print("No active preset");
    }

    // Bottom button bar.
    int16_t y = 240;
    int16_t x = 8;
    drawButton_(x, y, 150, 58, "MENU",  COL_BTN); x += 158;
    drawButton_(x, y, 150, 58, "PARK",  COL_BTN); x += 158;
    drawButton_(x, y, 150, 58,
        RouterRelay.isOn() ? "POWER OFF" : "POWER ON",
        RouterRelay.isOn() ? COL_BTN_OK : COL_BTN_NO);
}

// ---------------- ROOT MENU ------------------------------------------------
static const char* ROOT_DSP[] = {
    "Recall Preset", "Save Preset", "Set Target",
    "Home", "Zero Tool", "Router Power",
    "Calibrate Motor", "Calibrate Motion",
    "Calibrate Limits", "Calibrate Sensors",
};
static const uint8_t ROOT_DSP_COUNT = sizeof(ROOT_DSP) / sizeof(ROOT_DSP[0]);

void Display::renderRoot_() {
    renderHeader_("Menu", true);
    spr.setTextSize(2);
    for (uint8_t i = 0; i < ROOT_DSP_COUNT; ++i) {
        int16_t y = 42 + i * 24;
        spr.setTextColor(COL_FG, COL_BG);
        spr.setCursor(20, y + 4);
        spr.print(ROOT_DSP[i]);
        spr.drawFastHLine(0, y + 23, W, COL_HDR);
    }
}

// ---------------- PRESET PICKER --------------------------------------------
void Display::renderPresetPicker_(bool saving) {
    renderHeader_(saving ? "Save Preset to slot..." : "Recall Preset...", true);
    spr.setTextSize(2);
    for (uint8_t i = 0; i < UI::NUM_PRESETS; ++i) {
        int16_t y = 50 + i * 32;
        spr.fillRoundRect(8, y, W - 16, 28, 4, COL_BTN);
        spr.setTextColor(COL_FG, COL_BTN);
        spr.setCursor(20, y + 6);
        if (PresetStore.isSet(i)) spr.printf("Slot %u: %7.2f mm", i + 1, PresetStore.load(i));
        else                      spr.printf("Slot %u: (empty)",   i + 1);
    }
}

// ---------------- SET TARGET ----------------------------------------------
void Display::renderSetTarget_() {
    renderHeader_("Set Target Height", true);
    spr.setTextColor(COL_ACCENT, COL_BG);
    spr.setTextSize(6);
    spr.setCursor(20, 70);
    spr.printf("%7.2f", UIMenu.targetMm());
    spr.setTextSize(2);
    spr.setCursor(380, 115);
    spr.print("mm");

    spr.setTextColor(COL_DIM, COL_BG);
    spr.setCursor(20, 170);
    spr.printf("Spin MPG to adjust  -  Rate %s, %.3f mm/pulse",
               Rate.label(), Wheel.currentStepMm());

    drawButton_(80,  240, 150, 58, "OK",     COL_BTN_OK);
    drawButton_(250, 240, 150, 58, "CANCEL", COL_BTN_NO);
}

// ---------------- CALIB SCREENS -------------------------------------------
static void drawCalibRow(TFT_eSprite& s, int16_t y, bool selected, bool editing,
                         const char* label, const char* value) {
    uint16_t bg = COL_BTN;
    if (selected && editing) bg = COL_WARN;
    else if (selected)       bg = COL_ACCENT;
    s.fillRoundRect(8, y, W - 16, 32, 4, bg);
    s.setTextColor(bg == COL_BTN ? COL_FG : COL_BG, bg);
    s.setTextSize(2);
    s.setCursor(20,  y + 8); s.print(label);
    s.setCursor(260, y + 8); s.print(value);
}

void Display::renderCalibMotor_() {
    renderHeader_("Calibrate Motor", true);
    char v[24];
    int8_t c = UIMenu.cursor(); bool e = UIMenu.isEditing();
    snprintf(v, sizeof(v), "%u",      Motor.stepsPerRev());           drawCalibRow(spr, 50,  c==0, e, "Steps/rev",  v);
    snprintf(v, sizeof(v), "%.3f mm", Motor.spindlePitchMm());        drawCalibRow(spr, 88,  c==1, e, "Pitch",      v);
    snprintf(v, sizeof(v), "%s",      Motor.isEnabled()?"yes":"no");  drawCalibRow(spr, 126, c==2, e, "Dir invert", v);
}

void Display::renderCalibMotion_() {
    renderHeader_("Calibrate Motion", true);
    char v[24];
    int8_t c = UIMenu.cursor(); bool e = UIMenu.isEditing();
    snprintf(v, sizeof(v), "%.1f mm/s",   Motor.maxSpeedMmPerSec()); drawCalibRow(spr, 50, c==0, e, "Max speed", v);
    snprintf(v, sizeof(v), "%.0f mm/s^2", Motor.accelMmPerSec2());   drawCalibRow(spr, 88, c==1, e, "Accel",     v);
}

void Display::renderCalibLimits_() {
    renderHeader_("Calibrate Limits", true);
    char v[24];
    int8_t c = UIMenu.cursor(); bool e = UIMenu.isEditing();
    snprintf(v, sizeof(v), "%.2f mm", Motor.softMinMm()); drawCalibRow(spr, 50, c==0, e, "Soft min", v);
    snprintf(v, sizeof(v), "%.2f mm", Motor.softMaxMm()); drawCalibRow(spr, 88, c==1, e, "Soft max", v);
}

void Display::renderCalibSensors_() {
    renderHeader_("Calibrate Sensors", true);
    char v[24];
    int8_t c = UIMenu.cursor(); bool e = UIMenu.isEditing();
    snprintf(v, sizeof(v), "%.2f mm", Zero.stampOffsetMm());           drawCalibRow(spr, 50, c==0, e, "Stamp offset", v);
    snprintf(v, sizeof(v), "%u ms",   RouterRelay.startupDelayMs());   drawCalibRow(spr, 88, c==1, e, "Relay delay",  v);
}

void Display::renderHoming_() {
    renderHeader_("Homing", false);
    spr.setTextColor(COL_ACCENT, COL_BG);
    spr.setTextSize(3);
    spr.setCursor(20, 100); spr.print(Home.stateName());
    spr.setTextSize(2);
    spr.setTextColor(COL_FG, COL_BG);
    spr.setCursor(20, 160); spr.printf("Position: %.2f mm", Motor.currentPositionMm());
}

void Display::renderZeroing_() {
    renderHeader_("Zeroing Tool", false);
    spr.setTextColor(COL_ACCENT, COL_BG);
    spr.setTextSize(3);
    spr.setCursor(20, 100);
    switch (Zero.state()) {
        case Zeroing::State::SEEK:      spr.print("Seeking...");   break;
        case Zeroing::State::FINE_SEEK: spr.print("Fine seek..."); break;
        case Zeroing::State::DONE:      spr.print("Done");         break;
        case Zeroing::State::FAILED:    spr.print("Failed");       break;
        default: spr.print("Idle"); break;
    }
    spr.setTextSize(2);
    spr.setTextColor(COL_FG, COL_BG);
    spr.setCursor(20, 160); spr.printf("Position: %.2f mm", Motor.currentPositionMm());
}

void Display::renderFault_() {
    spr.fillRect(0, 0, W, 32, COL_FAULT);
    spr.setTextColor(COL_FG, COL_FAULT);
    spr.setTextSize(2);
    spr.setCursor(8, 8); spr.print("FAULT");

    spr.setTextColor(COL_FAULT, COL_BG);
    spr.setTextSize(3);
    spr.setCursor(20, 80);  spr.print(Guard.codeName());
    spr.setTextSize(2);
    spr.setTextColor(COL_FG, COL_BG);
    spr.setCursor(20, 140); spr.print(Guard.message());

    drawButton_(140, 240, 200, 58, "ACKNOWLEDGE", COL_BTN_NO);
}
