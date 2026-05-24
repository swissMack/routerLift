// ============================================================================
// config.h - Central configuration for the router lift
// All pin assignments, mechanical defaults, and tunable constants live here.
// ============================================================================
#pragma once

#include <Arduino.h>

// ---------------------------------------------------------------------------
// FIRMWARE
// ---------------------------------------------------------------------------
#define FW_VERSION       "1.0.0"
#define FW_BOARD_NAME    "RouterLift"

// ---------------------------------------------------------------------------
// PIN ASSIGNMENTS  (ESP32 DevKit V1)
// ---------------------------------------------------------------------------
// Stepper driver (DM542) - 5V tolerant inputs via opto-isolation on driver
namespace Pins {
    constexpr uint8_t STEPPER_STEP   = 25;
    constexpr uint8_t STEPPER_DIR    = 26;
    constexpr uint8_t STEPPER_ENABLE = 27;   // Active-LOW on DM542

    // MPG (manual pulse generator) - 5V signals via 74HCT14 or PC817 opto.
    // 100 PPR continuous (no detents). Full-quadrature decode.
    constexpr uint8_t MPG_A          = 32;
    constexpr uint8_t MPG_B          = 33;

    // Router power relay (SSR recommended).
    constexpr uint8_t RELAY          = 16;

    // I2C bus for MCP23017 + any future devices.
    constexpr uint8_t I2C_SDA        = 21;
    constexpr uint8_t I2C_SCL        = 22;

    // TFT (ILI9488) - configured in platformio.ini for TFT_eSPI.
    // MISO=19  MOSI=23  SCK=18  CS=15  DC=2  RST=4
    // Listed here for documentation only.

    // Touch (XPT2046) - shares the TFT SPI bus.
    constexpr uint8_t TOUCH_CS       = 5;
    constexpr uint8_t TOUCH_IRQ      = 17;
}

// MCP23017 I/O assignments (0x20 default address)
namespace MCP {
    constexpr uint8_t I2C_ADDRESS    = 0x20;

    // Port A inputs (sensors / switches)
    constexpr uint8_t PIN_ENDSTOP_BOTTOM = 0;
    constexpr uint8_t PIN_ENDSTOP_TOP    = 1;
    constexpr uint8_t PIN_BRASS_STAMP    = 2;
    constexpr uint8_t PIN_FOOTSWITCH     = 3;

    // Port B inputs
    // B0..B3 = function-board ID (4 bits, jumpers to GND)
    // B4..B6 = 3-position rate switch (one pin LOW selects that band)
    constexpr uint8_t PIN_BOARD_ID_0     = 8;
    constexpr uint8_t PIN_BOARD_ID_1     = 9;
    constexpr uint8_t PIN_BOARD_ID_2     = 10;
    constexpr uint8_t PIN_BOARD_ID_3     = 11;
    constexpr uint8_t PIN_RATE_X1        = 12;
    constexpr uint8_t PIN_RATE_X10       = 13;
    constexpr uint8_t PIN_RATE_X100      = 14;
}

// ---------------------------------------------------------------------------
// MECHANICAL DEFAULTS (overridable via menu / NVS)
// ---------------------------------------------------------------------------
namespace Mech {
    constexpr uint16_t DEFAULT_STEPS_PER_REV    = 1000;
    constexpr float    DEFAULT_SPINDLE_PITCH_MM = 4.0;
    constexpr bool     DEFAULT_DIR_INVERTED     = false;

    constexpr float    DEFAULT_MAX_SPEED_MM_S    = 25.0;
    constexpr float    DEFAULT_ACCEL_MM_S2       = 100.0;
    constexpr float    DEFAULT_HOMING_SPEED_MM_S = 8.0;
    constexpr float    DEFAULT_ZERO_SPEED_MM_S   = 1.5;

    constexpr float    DEFAULT_SOFT_MIN_MM = -5.0;
    constexpr float    DEFAULT_SOFT_MAX_MM = 80.0;
    constexpr float    DEFAULT_PARK_MM     = -1.0;
    constexpr float    DEFAULT_STAMP_OFFSET_MM = 10.0;
}

// ---------------------------------------------------------------------------
// MPG (manual pulse generator)
// ---------------------------------------------------------------------------
namespace MPG {
    // Pulses per revolution at the MPG (after full-quadrature decode).
    // Most 4-terminal 5V MPGs are 100 PPR.
    constexpr uint16_t PULSES_PER_REV = 100;

    // True if signals are inverted by the level-shift hardware
    // (PC817 opto-isolators invert; 74HCT14 single inverter inverts;
    //  74HCT14 with two inverters per channel does not).
    constexpr bool SIGNALS_INVERTED = true;   // assume opto by default

    // Per-band step sizes when the wheel is turned slowly (mm per MPG pulse).
    constexpr float STEP_X1_MM   = 0.001;
    constexpr float STEP_X10_MM  = 0.010;
    constexpr float STEP_X100_MM = 0.100;

    // Velocity scaling within a band: at high turn rates the per-pulse step
    // is multiplied up by this factor. Provides the "gas pedal" feel.
    constexpr float VELOCITY_SCALE_MAX = 10.0;

    // Pulses-per-second thresholds for velocity scaling.
    constexpr float VEL_PPS_LOW    = 5.0;
    constexpr float VEL_PPS_HIGH   = 80.0;
}

// ---------------------------------------------------------------------------
// UI / UX
// ---------------------------------------------------------------------------
namespace UI {
    constexpr uint8_t  NUM_PRESETS         = 6;
    constexpr uint16_t TOUCH_DEBOUNCE_MS   = 60;
    constexpr uint16_t DISPLAY_REFRESH_MS  = 50;
    constexpr uint16_t LONG_PRESS_MS       = 700;   // for touch long-press
}

// ---------------------------------------------------------------------------
// SAFETY
// ---------------------------------------------------------------------------
namespace Safety {
    constexpr uint16_t WATCHDOG_TIMEOUT_S     = 5;
    constexpr uint16_t RELAY_STARTUP_DELAY_MS = 2500;
    constexpr uint16_t ENDSTOP_DEBOUNCE_MS    = 3;
    constexpr uint16_t HOMING_TIMEOUT_MS      = 30000;
    constexpr uint16_t BUTTON_DEBOUNCE_MS     = 25;
}

// ---------------------------------------------------------------------------
// FUNCTION BOARD IDs (read from MCP Port B0..B3)
// ---------------------------------------------------------------------------
enum class BoardId : uint8_t {
    UNKNOWN          = 0,
    ROUTER_LIFT      = 1,
    DUST_COLLECTION  = 2,
    MITER_SAW_STOP   = 3,
};
