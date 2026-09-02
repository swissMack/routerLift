#include "Wheel.h"
#include "Link.h"
#include <ESP32Encoder.h>

Wheel Handwheel;
static ESP32Encoder enc;

void Wheel::begin(int8_t pinA, int8_t pinB) {
    ESP32Encoder::useInternalWeakPullResistors = puType::up;

    // SIGNALS_INVERTED is false for the 74HCT14 two-stage buffer, which is
    // non-inverting. The legacy firmware used true because it assumed PC817
    // optocouplers. Wrong value = the wheel counts backwards.
    if (MpgCfg::SIGNALS_INVERTED) enc.attachFullQuad(pinB, pinA);
    else                          enc.attachFullQuad(pinA, pinB);

    enc.clearCount();
    raw_ = lastRaw_ = 0;
    pending_ = 0;
    lastDir_ = 0;
    lastFlushMs_ = millis();
}

void Wheel::update() {
    // attachFullQuad counts all four edges; /4 gives detents.
    raw_ = (int32_t)(enc.getCount() / 4);

    int32_t delta = raw_ - lastRaw_;
    lastRaw_ = raw_;

    if (inhibited_) {
        pending_ = 0;          // discard, do not bank motion for later
        return;
    }

    if (delta != 0) {
        // Rule 3 - cancel on reversal rather than waiting out queued motion
        // in the old direction.
        int8_t dir = (delta > 0) ? 1 : -1;
        if (MpgCfg::CANCEL_ON_REVERSAL && lastDir_ != 0 && dir != lastDir_) {
            Motion.jogCancel();
            pending_ = 0;
        }
        lastDir_ = dir;
        pending_ += delta;
    }

    // Rule 1 - coalesce. One command per detent would flood the link.
    if (pending_ != 0 && (millis() - lastFlushMs_) >= MpgCfg::COALESCE_MS) {
        flush_();
    }
}

void Wheel::flush_() {
    lastFlushMs_ = millis();

    if (!Motion.isConnected()) { pending_ = 0; return; }

    float delta = pending_ * stepMm();
    pending_ = 0;
    if (delta == 0.0f) return;

    // Rule 2 - clamp look-ahead. Never let commanded position run more than
    // one screw revolution ahead of where the machine reports it actually is.
    // Adopted from FXBB (ino:282-289); it matters more here because our
    // commands cross a UART hop and can queue up behind it.
    const float limit = MpgCfg::LOOKAHEAD_LIMIT_REV * MpgCfg::SCREW_LEAD_MM;
    const float ahead = (commanded_ + delta) - Motion.positionMm();

    if (fabsf(ahead) > limit) {
        float allowed = (ahead > 0 ? limit : -limit)
                      - (commanded_ - Motion.positionMm());
        if ((delta > 0) != (allowed > 0) || fabsf(allowed) < 1e-4f) {
            jogsClamped_++;
            return;                       // already at the limit, drop it
        }
        delta = allowed;
        jogsClamped_++;
    }

    commanded_ += delta;
    Motion.sendf("$J=G91 G21 Z%.3f F%u", delta, MpgCfg::JOG_FEED_MM_MIN);
    jogsSent_++;
}

void Wheel::syncTo(float mm) {
    commanded_ = mm;
    pending_ = 0;
    lastDir_ = 0;
}
