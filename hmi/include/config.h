#pragma once
//
// routerLift HMI — tunable constants.
//
// Every value here was decided in docs/DESIGN-QA.md; the Q number is cited so
// a reviewer can find the reasoning rather than guess at intent.
//
// Motion limits are NOT here. Soft limits, travel and steps_per_mm live in
// firmware/config.yaml and are commissioning values the operator cannot reach.
// This board never writes them.

#include <stdint.h>

// ------------------------------------------------------------------ Link
namespace LinkCfg {

constexpr uint32_t BAUD = 115200;

// No status report for this long => link considered lost. Five missed
// intervals at the 10 Hz FluidNC report rate.  (docs/UART-PROTOCOL.md §7.2)
constexpr uint32_t TIMEOUT_MS = 500;

// If FluidNC's automatic reporting is unavailable, poll '?' at this rate.
// Verify $Report/Interval exists in the installed release first.
constexpr uint32_t POLL_MS = 100;

// One command in flight at a time. Deliberately more conservative than the
// character-counting flow control a file streamer uses: these are short
// interactive commands, so simplicity beats throughput.
constexpr uint8_t  TX_QUEUE_DEPTH = 8;
constexpr uint16_t LINE_BUFFER       = 96;

// Give up waiting for 'ok' and fault. Homing and probing legitimately take a
// long time, so this is generous.
constexpr uint32_t ACK_TIMEOUT_MS = 60000;

} // namespace LinkCfg


// ------------------------------------------------------------------- MPG
namespace MpgCfg {

constexpr uint16_t PULSES_PER_REV = 100;   // ZS80-5E100S

// FALSE for the 74HCT14 two-stage buffer, which is non-inverting.
// The legacy firmware used true because it assumed PC817 optocouplers.
// Wrong value = wheel counts backwards.  (docs/BOM.md block G)
constexpr bool SIGNALS_INVERTED = false;

// ELE-09: two positions, not the legacy three-band x1/x10/x100.
constexpr float STEP_FINE_MM  = 0.01f;   // 1 rev = 1 mm
constexpr float STEP_ROUGH_MM = 0.10f;   // 1 rev = 10 mm

// Jog feed rate sent with $J=. Fast enough to feel responsive, inside the
// 12 mm/s machine rapid.  (Q14)
constexpr uint16_t JOG_FEED_MM_MIN = 600;

// --- The three mandatory handwheel rules (docs/UART-PROTOCOL.md §5) ---

// 1. Coalesce detents over this window into one $J= command. One command per
//    detent would flood the link on a fast spin.
constexpr uint32_t COALESCE_MS = 30;

// 2. Never let queued jog distance exceed one screw revolution ahead of the
//    reported machine position. Adopted from FXBB (ino:282-289), and it
//    matters more here because our commands cross a UART hop.
constexpr float LOOKAHEAD_LIMIT_REV = 1.0f;

// ###################################################################
// #  PROVISIONAL - sauter FML-P published spec, not yet measured.   #
// #  1.5 mm travel per revolution. Was 2.0, which assumed a screw   #
// #  on a machine that was never built.                             #
// #  Too large and the clamp does nothing; too small and the wheel  #
// #  feels like it is dragging. See docs/MECHANICS-RevH.md          #
// ###################################################################
constexpr float SCREW_LEAD_MM = 1.5f;

// 3. Cancel on direction reversal - send 0x85 and start fresh, rather than
//    waiting for queued motion in the old direction to finish.
constexpr bool CANCEL_ON_REVERSAL = true;

} // namespace MpgCfg


// --------------------------------------------------------------- Buttons
namespace ButtonCfg {

constexpr uint32_t POLL_MS      = 50;    // 20 Hz expander poll
constexpr uint32_t DEBOUNCE_MS  = 25;
constexpr uint32_t LONG_PRESS_MS = 700;  // short/long doubling gives 12
                                         // functions from 6 buttons

} // namespace ButtonCfg


// ---------------------------------------------------------------- Motion
// Values the HMI sends as part of commands. The machine's own limits are in
// firmware/config.yaml and are enforced there regardless of anything here -
// these are requests, not constraints.  (ELE-11)
namespace MotionCfg {

constexpr uint16_t PLUNGE_FEED_MM_MIN = 120;   // 2 mm/s   (Q15)
constexpr uint16_t RAPID_FEED_MM_MIN  = 720;   // 12 mm/s  (Q14)

// Two-touch probe (Q23). The slow second touch is what delivers MOT-06's
// ±0.02 mm; the first only finds roughly where the surface is.
constexpr uint16_t PROBE_FIND_MM_MIN    = 300; // 5 mm/s
constexpr uint16_t PROBE_CONFIRM_MM_MIN = 30;  // 0.5 mm/s
constexpr float    PROBE_RETRACT_MM     = 1.0f;
constexpr float    PROBE_MAX_TRAVEL_MM  = 50.0f;

// Measured with calipers and stored in NVS (FW-10). This is only a default.
constexpr float PROBE_PLATE_MM = 3.00f;

} // namespace MotionCfg


// ---------------------------------------------------------------- Cycles
namespace CycleCfg {

constexpr float ROUGH_DEPTH_MM     = 2.00f;  // inside FW-03's <=3 mm   (Q35)
constexpr float FINISH_ALLOW_MM    = 0.30f;  // FW-04 default           (Q35)
constexpr float SCRIBE_DEPTH_MM    = 0.30f;  // FW-05                   (Q36)
constexpr bool  SCRIBE_DEFAULT_ON  = true;   // toggled per job         (Q36)

// No auto-advance. Every pass holds until CYCLE START.  (Q34)
constexpr bool REQUIRE_PASS_CONFIRM = true;

} // namespace CycleCfg


// -------------------------------------------------------------------- UI
namespace UiCfg {

constexpr uint8_t  DECIMALS      = 2;      // ELE-08, mm to 0.01   (Q29)
constexpr uint32_t REFRESH_MS    = 50;     // 20 Hz
constexpr uint32_t DIM_AFTER_MS  = 300000; // 5 min, dim not blank (Q30)
constexpr uint8_t  BACKLIGHT_ON  = 255;
constexpr uint8_t  BACKLIGHT_DIM = 40;

constexpr uint8_t  MAX_PRESETS   = 12;     // named, NVS-stored    (Q26)
constexpr uint8_t  PRESET_NAME_LEN = 20;

// Advisory only - never blocks a cycle.  (ENV-04, Q42)
constexpr uint32_t RETOUCH_REMINDER_MS = 1800000;  // 30 min run time

constexpr uint8_t  FAULT_LOG_ENTRIES = 20;         // FLT-07, Q41

} // namespace UiCfg


// ------------------------------------------------------------------- NVS
namespace Nvs {

constexpr const char* NS_CONFIG  = "rl-cfg";
constexpr const char* NS_PRESETS = "rl-presets";
constexpr const char* NS_FAULTS  = "rl-faults";

// Debounced flush, ported from legacy/src/Settings.cpp - a sound pattern that
// keeps rapid edits from wearing the flash.
constexpr uint32_t SAVE_DEBOUNCE_MS = 2000;

} // namespace Nvs
