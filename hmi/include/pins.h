#pragma once
//
// routerLift HMI — pin map for the Guition JC4827W543C (ESP32-S3-WROOM-1-N4R8).
//
// THIS IS THE ONLY PLACE PIN NUMBERS APPEAR. Nothing else in hmi/ may hardcode
// a GPIO. See docs/PINOUT.svg for the same map drawn out.
//
// BOARD IDENTITY, confirmed on the bench 2026-09-13: the board in hand is the
// Guition JC4827W543C (NV3041A over QSPI), NOT the Sunton ESP32-4827S043 (RGB
// parallel) that Rev H recorded. The factory demo on it contained
// guition.com and Arduino_ESP32QSPI. Firmware built for the RGB board runs
// cleanly and shows nothing - gfx->begin() still returns true.
//
// The octal PSRAM takes 33-37. The panel buttons still live on an I2C
// expander so the free connector pins stay available.

#include <stdint.h>

namespace Pins {

// ---------------------------------------------------------------- UART link
// To the FluidNC ESP32. 3.3 V both ends - no level shifting.
// Connector P4 "UART1": GND · 3.3V · IO17 · IO18 (JST 1.25 mm, 4-pin).
// P5 carries the same four signals on a different plug - use one, not both.
constexpr int8_t UART_TX = 18;   // -> FluidNC GPIO 16 (RX)
constexpr int8_t UART_RX = 17;   // <- FluidNC GPIO 17 (TX)
constexpr int    UART_NUM = 1;

// ------------------------------------------------------------ MPG handwheel
// ZS80-5E100S, 100 PPR, 5 V, via a 74HCT14 (two stages per channel).
//
// The 74HCT14 pair is NON-INVERTING. The legacy firmware set
// MPG::SIGNALS_INVERTED = true because it assumed PC817 optocouplers.
// Getting this wrong makes the wheel count backwards - see SIGNALS_INVERTED
// in hmi/include/config.h.
// Connector P3: IO6 · IO7 · IO15 · IO16 (no power pins - take GND and the
// shifter's 3.3 V from P4). Moved from 11/12, which on this board are TF-card
// lines and reach no connector.
constexpr int8_t MPG_A = 6;
constexpr int8_t MPG_B = 7;

// ---------------------------------------------------------------------- I2C
// Two buses, because the board's own touch bus reaches no connector.
//
// Bus 0 (Wire) - on-board GT911 touch controller (0x5D) only. GPIO 8/4 are
// routed to the touch panel and nowhere else. Clear of the S3's native USB
// pins (19/20), so starting I2C does not kill the serial console.
constexpr int8_t I2C_SCL = 4;
constexpr int8_t I2C_SDA = 8;
constexpr uint8_t GT911_ADDR = 0x5D;

// Bus 1 - MCP23017 panel-button expander (0x20), on connector P3.
// Needs external 4.7 kOhm pull-ups to 3.3 V on both lines at the expander.
constexpr int8_t MCP_SDA = 15;
constexpr int8_t MCP_SCL = 16;
constexpr uint8_t MCP_ADDR = 0x20;

// -------------------------------------------------------------- Touch GT911
// INT also selects the GT911's I2C address during reset. GPIO 3 is a strap
// pin (JTAG source select) - fine as the touch interrupt, never a button.
constexpr int8_t TOUCH_INT = 3;
constexpr int8_t TOUCH_RST = 38;

// ------------------------------------------------------- Display (NV3041A)
// 4-bit QSPI, 480x272 IPS. Values from the Guition vendor example, matched
// by the ESPHome and profi-max configurations for this board.
constexpr int8_t LCD_CS  = 45;
constexpr int8_t LCD_SCK = 47;
constexpr int8_t LCD_D0  = 21;
constexpr int8_t LCD_D1  = 48;
constexpr int8_t LCD_D2  = 40;
constexpr int8_t LCD_D3  = 39;
constexpr int8_t TFT_BL  = 1;

// -------------------------------------------------------------------- Spare
// GPIO 0 is a boot strap - do NOT use it for a panel button. A leaning elbow
// at power-up would prevent the board booting.
//
// Connector-exposed GPIOs, read off the board silkscreen 2026-09-13:
//   P2  IO46 · IO9 · IO14 · IO5
//   P3  IO6  · IO7 · IO15 · IO16
//   P4  GND · 3.3V · IO17 · IO18   (P5 = same)
//   P1  GND · RXD · TXD · +5V      (UART0 + 5 V in)
// GPIO 46 is a boot strap - never drive it from outside at power-up.
//
// Allocated: P3 = MPG A/B (6/7) + MCP I2C (15/16); P4 = UART (17/18).
constexpr int8_t SPARE_A = 5;
constexpr int8_t SPARE_B = 9;
constexpr int8_t SPARE_C = 14;

// ------------------------------------------------- Committed by the board
// Listed so nobody reassigns them by accident. Do not use.
//   QSPI panel  21, 39, 40, 45, 47, 48
//   Backlight   1
//   Touch       3 (INT), 4 (SCL), 8 (SDA), 38 (RST)
//   Octal PSRAM 33-37
//   Native USB  19, 20
//   UART0       43, 44

} // namespace Pins


// MCP23017 bit assignments. Port A is inputs, Port B drives indicators.
// Buttons are momentary NO to GND with the expander's internal pull-ups, so
// a pressed button reads LOW.
namespace Expander {

constexpr uint8_t A_CYCLE_START = 0;
constexpr uint8_t A_ROUTER      = 1;
constexpr uint8_t A_BIT_CHANGE  = 2;
constexpr uint8_t A_ZERO        = 3;
constexpr uint8_t A_PRESET      = 4;
constexpr uint8_t A_ROUGH_FINE  = 5;   // SPDT toggle, not momentary
constexpr uint8_t A_FOOT_MIRROR = 6;   // see note below
constexpr uint8_t A_SPARE_7     = 7;

constexpr uint8_t B_ROUTER_LED  = 0;   // lit = live, blinking = warming

// A_FOOT_MIRROR carries the same contact as the foot switch on FluidNC
// GPIO 13. The motion board owns the PRESS (macro0_pin, plunges locally with
// no link latency); the HMI watches this mirror for the RELEASE so it can
// command the retract, giving Q39's dead-man behaviour.
//
// UNRESOLVED: this exists because a FluidNC macro pin may only fire on
// assert. If verification shows macro pins fire on both edges, this mirror
// becomes unnecessary. See firmware/README.md.

// STOP is deliberately NOT on this expander. It is wired to FluidNC's own
// feed_hold_pin (GPIO 21) so that it halts motion even if this board has
// crashed or the UART link has dropped.

} // namespace Expander
