#pragma once
#include <Arduino.h>

// MotorControl wraps FastAccelStepper with mm-based API and hard soft-limit
// enforcement. Every motion command is checked against limits regardless of
// origin - jog, preset, foot switch, menu - so safety lives in one place.

class MotorControl {
public:
    bool begin();

    // --- Calibration (live-tunable, persisted by caller via Preferences) ---
    void setStepsPerRev(uint16_t s);
    void setSpindlePitchMm(float p);
    void setDirectionInverted(bool inv);
    void setMaxSpeedMmPerSec(float v);
    void setAccelMmPerSec2(float a);
    void setSoftLimits(float minMm, float maxMm);

    uint16_t stepsPerRev()        const { return stepsPerRev_; }
    float    spindlePitchMm()     const { return spindlePitchMm_; }
    float    maxSpeedMmPerSec()   const { return maxSpeedMmS_; }
    float    accelMmPerSec2()     const { return accelMmS2_; }
    float    softMinMm()          const { return softMinMm_; }
    float    softMaxMm()          const { return softMaxMm_; }

    // --- Motion commands (return false if rejected by soft limits) ---
    bool moveToMm(float targetMm);
    bool moveRelativeMm(float deltaMm);
    void stop();              // Decelerated stop.
    void emergencyStop();     // Immediate halt + disable driver.

    // --- Manual jogging ("gas pedal" via encoder) ---
    // Sets a continuous velocity in mm/s, sign = direction. 0 stops.
    void jog(float mmPerSec);

    // --- State queries ---
    float    currentPositionMm() const;
    bool     isMoving() const;
    bool     isEnabled() const { return enabled_; }
    int32_t  currentPositionSteps() const;

    // --- Position seeding (for homing / zeroing) ---
    void setCurrentPositionMm(float mm);
    void enable(bool on);

    // --- Conversion helpers ---
    int32_t mmToSteps(float mm) const;
    float   stepsToMm(int32_t steps) const;

private:
    bool   enabled_ = false;

    // Calibration
    uint16_t stepsPerRev_    = 1000;
    float    spindlePitchMm_ = 4.0;
    bool     dirInverted_    = false;

    // Motion profile
    float    maxSpeedMmS_    = 25.0;
    float    accelMmS2_      = 100.0;

    // Soft limits
    float    softMinMm_      = -5.0;
    float    softMaxMm_      = 80.0;

    bool withinLimits_(float mm) const;
    void applyProfile_();
};

extern MotorControl Motor;
