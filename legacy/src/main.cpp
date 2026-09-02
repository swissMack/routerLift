// ============================================================================
// Router Lift V1 - main.cpp
// Top-level state machine wiring all modules together.
// ============================================================================
#include <Arduino.h>
#include "config.h"
#include "IOExpander.h"
#include "MotorControl.h"
#include "MPG.h"
#include "RateSwitch.h"
#include "Touch.h"
#include "Homing.h"
#include "Presets.h"
#include "Zeroing.h"
#include "Relay.h"
#include "FootSwitch.h"
#include "FunctionBoard.h"
#include "Safety.h"
#include "Display.h"
#include "Menu.h"
#include "Settings.h"

enum class AppState : uint8_t {
    BOOT,
    HOMING,
    IDLE,
    PLUNGE,
    RETURN_PARK,
    ZEROING,
    FAULT,
};

static AppState appState = AppState::BOOT;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static void checkEndstops() {
    if (Home.isActive() || Zero.isActive()) return;
    if (IO.readEndstopBottom() || IO.readEndstopTop()) {
        Guard.trigger(FaultCode::ENDSTOP_HIT,
                      IO.readEndstopBottom() ? "Bottom endstop" : "Top endstop");
    }
}

static void enforceSoftLimits() {
    float p = Motor.currentPositionMm();
    if (p < Motor.softMinMm() - 0.5f || p > Motor.softMaxMm() + 0.5f) {
        Guard.trigger(FaultCode::SOFT_LIMIT_VIOLATED, "Position out of bounds");
    }
}

// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println();
    Serial.println("=== " FW_BOARD_NAME " v" FW_VERSION " ===");

    Guard.begin();

    if (!IO.begin()) {
        Serial.println("MCP23017 not found - degraded mode");
    }

    if (!Board.begin()) {
        Serial.printf("Unknown function board (raw id=%u)\n", Board.rawId());
    } else {
        Serial.printf("Function board: %s\n", Board.name());
    }

    if (!Motor.begin())    { Guard.trigger(FaultCode::I2C_LOST, "Motor init"); }
    if (!Wheel.begin())    { Serial.println("MPG init failed"); }
    if (!Screen.begin())   { Serial.println("Display init failed"); }
    if (!TouchPanel.begin()){ Serial.println("Touch init failed"); }
    PresetStore.begin();
    RouterRelay.begin();
    UIMenu.begin();

    // Load persisted calibration from NVS, falling back to Mech/Safety
    // defaults for any missing keys. Replaces the hard-coded default block.
    Config.begin();

    Home.start();
    appState = AppState::HOMING;
}

// ---------------------------------------------------------------------------
void loop() {
    // --- Always-on services ---
    Guard.update();
    Foot.update();
    Rate.update();
    Wheel.update();
    TouchPanel.update();
    Home.update();
    Zero.update();
    Config.update();
    checkEndstops();
    enforceSoftLimits();

    if (Guard.inFault()) appState = AppState::FAULT;

    switch (appState) {

    case AppState::BOOT:
        break;

    case AppState::HOMING:
        if (Home.state() == Homing::State::DONE)        appState = AppState::IDLE;
        else if (Home.state() == Homing::State::FAILED) Guard.trigger(FaultCode::HOMING_TIMEOUT, "Homing failed");
        break;

    case AppState::IDLE:
        if (Foot.justPressed()) {
            if (RouterRelay.isReady()) {
                Motor.moveToMm(UIMenu.targetMm());
                appState = AppState::PLUNGE;
            } else if (RouterRelay.isOn()) {
                Serial.println("Plunge ignored: spindle not at speed");
            } else {
                Serial.println("Plunge ignored: router relay off");
            }
        }
        if (Zero.isActive()) appState = AppState::ZEROING;
        break;

    case AppState::PLUNGE:
        if (Foot.justReleased()) {
            Motor.moveToMm(Mech::DEFAULT_PARK_MM);
            appState = AppState::RETURN_PARK;
        }
        break;

    case AppState::RETURN_PARK:
        if (!Motor.isMoving()) appState = AppState::IDLE;
        break;

    case AppState::ZEROING:
        if (!Zero.isActive()) appState = AppState::IDLE;
        break;

    case AppState::FAULT:
        if (!Guard.inFault()) appState = AppState::IDLE;
        break;
    }

    UIMenu.update();
    Screen.update();

    delay(1);
}
