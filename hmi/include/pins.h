#pragma once
//
// routerLift HMI — pin map for the ESP32-4827S043 (ESP32-S3-WROOM-1-N4R8).
//
// THIS IS THE ONLY PLACE PIN NUMBERS APPEAR. Nothing else in hmi/ may hardcode
// a GPIO. See docs/PINOUT.svg for the same map drawn out.
//
// The RGB parallel panel commits 20 GPIOs and the octal PSRAM takes 33-37,
// which is why the panel buttons live on an I2C expander rather than on pins.
// The TF card slot is sacrificed to free GPIO 10-13.

#include <stdint.h>

namespace Pins {

// ---------------------------------------------------------------- UART link
// To the FluidNC ESP32. 3.3 V both ends - no level shifting.
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
constexpr int8_t MPG_A = 11;
constexpr int8_t MPG_B = 12;

// ---------------------------------------------------------------------- I2C
// Shared bus: GT911 touch controller (0x5D) + MCP23017 expander (0x20).
constexpr int8_t I2C_SCL = 20;
constexpr int8_t I2C_SDA = 19;
constexpr uint8_t MCP_ADDR   = 0x20;
constexpr uint8_t GT911_ADDR = 0x5D;

// -------------------------------------------------------------------- Spare
// Freed by moving rough/fine and cycle start onto the expander.
// GPIO 0 is a boot strap - do NOT use it for a panel button. A leaning elbow
// at power-up would prevent the board booting.
constexpr int8_t SPARE_A = 10;
constexpr int8_t SPARE_B = 13;

// ------------------------------------------------- Committed by the board
// Listed so nobody reassigns them by accident. Do not use.
//   RGB bus     1, 3-9, 14, 15, 16, 21, 39-42, 45-48
//   Backlight   2
//   GT911 RST   38
//   Octal PSRAM 33-37
//   USB console 43, 44
constexpr int8_t TFT_BL = 2;

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
