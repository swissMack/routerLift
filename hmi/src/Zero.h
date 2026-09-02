#pragma once
//
// Zero — touch-off sequencing and Z0 validity.
//
// Z0 is the reference every cut depth is measured from, and FluidNC has no
// concept of it. This board owns it entirely, which makes the invalidation
// rules (FW-09) the most safety-relevant logic in the HMI.
//
// The stance throughout is that Z0 is invalid until proven otherwise, and that
// there is NO override anywhere. With no stall detection (DEV-01) a wrong
// reference does not fail visibly - it produces a plausible-looking cut at the
// wrong depth. Every override we might add is a place to trust a number the
// machine cannot verify.
//
// Reference is the TABLE TOP (Q21), so depth means bit projection above the
// table and is independent of stock thickness.

#include <Arduino.h>

enum class ZeroState : uint8_t {
    Idle,
    FastProbe,      // G38.2 at 5 mm/s - finds roughly where the surface is
    Retract,        // back off 1 mm
    SlowProbe,      // G38.2 at 0.5 mm/s - this is what delivers MOT-06
    Applying,       // G10 L20 to set the work offset
    Done,
    Failed
};

// Why Z0 was invalidated. Shown to the operator, and logged, because "Z0 BAD"
// without a reason is not actionable.
enum class ZeroLost : uint8_t {
    NeverSet, BitChange, HomingLost, Alarm, LinkLost, ProbeFailed, Manual
};

class Zero {
public:
    void begin();
    void update();

    // Start a touch-off. Refused unless the machine is homed and idle.
    bool start();
    void cancel();

    bool      isValid() const { return valid_; }
    ZeroState state()   const { return state_; }
    bool      isBusy()  const { return state_ != ZeroState::Idle &&
                                       state_ != ZeroState::Done &&
                                       state_ != ZeroState::Failed; }

    void invalidate(ZeroLost why);
    ZeroLost lostReason() const { return why_; }
    const char* lostReasonText() const;
    const char* stateText() const;

    // Set zero at the current position without probing - the long-press on
    // ZERO. Deliberately separate from the probe path so it can never be
    // mistaken for a measured touch-off.
    void setHereUnprobed();

    // Plate thickness (FW-10), measured with calipers and kept in NVS.
    void  setPlateMm(float mm) { plateMm_ = mm; }
    float plateMm() const { return plateMm_; }

    const char* lastError() const { return err_; }

private:
    void fail_(const char* why);

    ZeroState state_ = ZeroState::Idle;
    bool      valid_ = false;
    ZeroLost  why_   = ZeroLost::NeverSet;
    float     plateMm_ = 0.0f;
    uint32_t  stepStartMs_ = 0;
    char      err_[48] = {0};
};

extern Zero Z0;
