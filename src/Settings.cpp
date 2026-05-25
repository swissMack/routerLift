#include "Settings.h"
#include "MotorControl.h"
#include "Zeroing.h"
#include "Relay.h"
#include "config.h"
#include <Preferences.h>

// NVS namespace name. Mirrors the "rl-presets" convention used by Presets.
static const char* NS = "rl-cfg";
static Preferences prefs;

Settings Config;

bool Settings::begin() {
    prefs.begin(NS, /*readOnly=*/true);
    uint16_t stepsPerRev  = prefs.getUShort("stepsPerRev",   Mech::DEFAULT_STEPS_PER_REV);
    float    pitchMm      = prefs.getFloat ("pitchMm",       Mech::DEFAULT_SPINDLE_PITCH_MM);
    bool     dirInv       = prefs.getBool  ("dirInv",        Mech::DEFAULT_DIR_INVERTED);
    float    maxSpeedMmS  = prefs.getFloat ("maxSpdMmS",     Mech::DEFAULT_MAX_SPEED_MM_S);
    float    accelMmS2    = prefs.getFloat ("accelMmS2",     Mech::DEFAULT_ACCEL_MM_S2);
    float    softMinMm    = prefs.getFloat ("softMinMm",     Mech::DEFAULT_SOFT_MIN_MM);
    float    softMaxMm    = prefs.getFloat ("softMaxMm",     Mech::DEFAULT_SOFT_MAX_MM);
    float    stampOffset  = prefs.getFloat ("stampOffsetMm", Mech::DEFAULT_STAMP_OFFSET_MM);
    uint16_t relayDelayMs = prefs.getUShort("relayDelayMs",  Safety::RELAY_STARTUP_DELAY_MS);
    prefs.end();

    Motor.setStepsPerRev(stepsPerRev);
    Motor.setSpindlePitchMm(pitchMm);
    Motor.setDirectionInverted(dirInv);
    Motor.setMaxSpeedMmPerSec(maxSpeedMmS);
    Motor.setAccelMmPerSec2(accelMmS2);
    Motor.setSoftLimits(softMinMm, softMaxMm);
    Zero.setStampOffsetMm(stampOffset);
    RouterRelay.setStartupDelayMs(relayDelayMs);
    return true;
}

void Settings::scheduleSave() {
    dirty_      = true;
    lastEditMs_ = millis();
}

void Settings::update() {
    if (!dirty_) return;
    if ((millis() - lastEditMs_) < SAVE_DEBOUNCE_MS) return;
    flush_();
    dirty_ = false;
}

void Settings::flush_() {
    prefs.begin(NS, /*readOnly=*/false);
    prefs.putUShort("stepsPerRev",   Motor.stepsPerRev());
    prefs.putFloat ("pitchMm",       Motor.spindlePitchMm());
    prefs.putBool  ("dirInv",        Motor.dirInverted());
    prefs.putFloat ("maxSpdMmS",     Motor.maxSpeedMmPerSec());
    prefs.putFloat ("accelMmS2",     Motor.accelMmPerSec2());
    prefs.putFloat ("softMinMm",     Motor.softMinMm());
    prefs.putFloat ("softMaxMm",     Motor.softMaxMm());
    prefs.putFloat ("stampOffsetMm", Zero.stampOffsetMm());
    prefs.putUShort("relayDelayMs",  RouterRelay.startupDelayMs());
    prefs.end();
}
