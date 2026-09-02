#include "Zero.h"
#include "Link.h"
#include "config.h"
#include <string.h>

Zero Z0;

// Generous: a slow confirming probe over 50 mm legitimately takes a while.
static constexpr uint32_t STEP_TIMEOUT_MS = 90000;

void Zero::begin() {
    plateMm_ = MotionCfg::PROBE_PLATE_MM;
    valid_ = false;
    why_ = ZeroLost::NeverSet;
    state_ = ZeroState::Idle;
}

bool Zero::start() {
    if (isBusy()) return false;

    // Refuse rather than queue. The operator should see why nothing happened.
    if (!Motion.isConnected()) { fail_("no link"); return false; }
    if (Motion.state() == MachineState::Alarm) { fail_("machine in alarm"); return false; }
    if (Motion.state() != MachineState::Idle)  { fail_("machine not idle");  return false; }

    // FLT-02 probe self-check is enforced by FluidNC itself via
    // probe: check_mode_start. If the probe is already triggered - a trapped
    // croc clip, a chip bridging the plate - G38.2 returns an error rather
    // than instantly "succeeding" and setting Z0 wherever the bit happens to
    // be. That failure arrives as error:N and is handled in update().
    err_[0] = '\0';
    valid_ = false;                     // invalid for the whole sequence
    state_ = ZeroState::FastProbe;
    stepStartMs_ = millis();
    Motion.sendf("G38.2 Z-%.1f F%u",
                 MotionCfg::PROBE_MAX_TRAVEL_MM, MotionCfg::PROBE_FIND_MM_MIN);
    return true;
}

void Zero::cancel() {
    if (!isBusy()) return;
    Motion.feedHold();
    state_ = ZeroState::Idle;
    invalidate(ZeroLost::Manual);
}

void Zero::update() {
    if (!isBusy()) return;

    // A dropped link mid-probe leaves the reference unknowable.
    if (!Motion.isConnected()) { fail_("link lost during probe"); return; }

    if (Motion.hasError()) {
        // Most likely the probe self-check: already triggered at start.
        fail_(Motion.lastMessage());
        Motion.clearError();
        return;
    }

    if (millis() - stepStartMs_ > STEP_TIMEOUT_MS) { fail_("probe timed out"); return; }

    // Every step waits for the queue to drain AND the machine to stop moving.
    if (!Motion.idleAndSynced() || Motion.state() != MachineState::Idle) return;

    float pz; bool triggered;

    switch (state_) {
    case ZeroState::FastProbe:
        if (!Motion.takeProbeResult(pz, triggered)) return;
        // ':0' means the probe never made contact. Never assume the surface
        // was where we expected it - that is exactly how a wrong Z0 is set.
        if (!triggered) { fail_("no contact on fast probe"); return; }
        state_ = ZeroState::Retract;
        stepStartMs_ = millis();
        Motion.sendf("G91 G21 G0 Z%.2f", MotionCfg::PROBE_RETRACT_MM);
        break;

    case ZeroState::Retract:
        state_ = ZeroState::SlowProbe;
        stepStartMs_ = millis();
        // Only needs to travel the retract distance plus a margin. The slow
        // second touch is what actually delivers MOT-06's +/-0.02 mm.
        Motion.sendf("G38.2 Z-%.1f F%u",
                     MotionCfg::PROBE_RETRACT_MM * 3.0f,
                     MotionCfg::PROBE_CONFIRM_MM_MIN);
        break;

    case ZeroState::SlowProbe:
        if (!Motion.takeProbeResult(pz, triggered)) return;
        if (!triggered) { fail_("no contact on slow probe"); return; }
        state_ = ZeroState::Applying;
        stepStartMs_ = millis();
        // Z0 is the TABLE TOP (Q21). The bit is touching the plate, so the
        // table is one plate thickness below where the tip now sits.
        Motion.sendf("G10 L20 P1 Z%.3f", plateMm_);
        break;

    case ZeroState::Applying:
        state_ = ZeroState::Done;
        valid_ = true;
        err_[0] = '\0';
        break;

    default:
        break;
    }
}

void Zero::setHereUnprobed() {
    if (isBusy() || !Motion.isConnected()) return;
    // Long-press ZERO. Kept on a separate path from the probe sequence so it
    // can never be mistaken for a measured touch-off.
    Motion.send("G10 L20 P1 Z0");
    valid_ = true;
    state_ = ZeroState::Done;
    strncpy(err_, "zero set without probing", sizeof(err_) - 1);
}

void Zero::invalidate(ZeroLost why) {
    valid_ = false;
    why_ = why;
    if (isBusy()) state_ = ZeroState::Failed;
}

void Zero::fail_(const char* why) {
    state_ = ZeroState::Failed;
    valid_ = false;
    why_ = ZeroLost::ProbeFailed;
    strncpy(err_, why ? why : "probe failed", sizeof(err_) - 1);
    err_[sizeof(err_) - 1] = '\0';
}

const char* Zero::lostReasonText() const {
    switch (why_) {
        case ZeroLost::NeverSet:    return "never set";
        case ZeroLost::BitChange:   return "bit changed";
        case ZeroLost::HomingLost:  return "homing lost";
        case ZeroLost::Alarm:       return "alarm";
        case ZeroLost::LinkLost:    return "link lost";
        case ZeroLost::ProbeFailed: return "probe failed";
        case ZeroLost::Manual:      return "cancelled";
    }
    return "unknown";
}

const char* Zero::stateText() const {
    switch (state_) {
        case ZeroState::Idle:       return "";
        case ZeroState::FastProbe:  return "PROBING (fast)";
        case ZeroState::Retract:    return "PROBING (retract)";
        case ZeroState::SlowProbe:  return "PROBING (confirm)";
        case ZeroState::Applying:   return "SETTING ZERO";
        case ZeroState::Done:       return "Z0 SET";
        case ZeroState::Failed:     return "PROBE FAILED";
    }
    return "";
}
