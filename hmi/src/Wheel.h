#pragma once
//
// Wheel — MPG handwheel decode and jog generation.
//
// The latency-sensitive path in the whole machine, and the one place the split
// architecture is measurably worse than a single-board design: a detent has to
// reach the step generator through a UART hop.
//
//   detent -> PCNT -> x scale -> coalesce -> clamp -> $J= -> Link -> FluidNC
//
// Three rules, all mandatory (docs/UART-PROTOCOL.md §5):
//   1. Coalesce detents over a short window into one command.
//   2. Clamp queued distance to one screw revolution ahead of reported MPos.
//   3. Cancel on direction reversal rather than waiting out queued motion.
//
// Rule 2 is adopted from FXBB (ino:282-289). Without it a fast spin queues
// motion that keeps running after the operator stops turning the wheel.

#include <Arduino.h>
#include "config.h"

class Wheel {
public:
    void begin(int8_t pinA, int8_t pinB);
    void update();

    // Rough/fine selector (ELE-09). Set from the expander each poll.
    void setRough(bool rough) { rough_ = rough; }
    bool isRough() const { return rough_; }

    float stepMm() const {
        return rough_ ? MpgCfg::STEP_ROUGH_MM : MpgCfg::STEP_FINE_MM;
    }

    // Motion is inhibited while a cycle owns the axis, or when the link is
    // down. The wheel must never be able to interrupt a running cycle.
    void inhibit(bool on) { inhibited_ = on; }
    bool inhibited() const { return inhibited_; }

    // Re-anchor the commanded position to a known machine position. Call after
    // homing, after any cycle move, and on reconnect - otherwise the
    // look-ahead clamp is measuring against a stale reference.
    void syncTo(float mm);
    float commandedMm() const { return commanded_; }

    // Diagnostics for the calibration screen (the FXBB live-derived-value
    // idea: show mm/rev next to the raw count while editing).
    int32_t rawCount()  const { return raw_; }
    float   mmPerRev()  const { return stepMm() * MpgCfg::PULSES_PER_REV; }
    uint32_t jogsSent() const { return jogsSent_; }
    uint32_t jogsClamped() const { return jogsClamped_; }

private:
    void flush_();

    int32_t  raw_ = 0;          // full-quadrature count, already divided by 4
    int32_t  lastRaw_ = 0;
    int32_t  pending_ = 0;      // detents accumulated this window
    float    commanded_ = 0.0f; // where we have told the machine to go
    int8_t   lastDir_ = 0;
    uint32_t lastFlushMs_ = 0;

    bool rough_ = false;
    bool inhibited_ = false;

    uint32_t jogsSent_ = 0;
    uint32_t jogsClamped_ = 0;
};

extern Wheel Handwheel;
