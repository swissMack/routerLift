#pragma once
//
// Store — NVS persistence for named presets and calibration.
//
// Named presets are FW-08 as written (Q26): "6mm groove" outlives your memory
// of what slot 3 was.
//
// The debounced flush is ported from legacy/src/Settings.cpp - dirty flag plus
// a 2 s quiet period before writing. That pattern was sound and stops rapid
// edits from wearing the flash.
//
// What is NOT here: soft limits and travel. Those are commissioning values in
// firmware/config.yaml which this board never writes (Q-soft-limits). An
// operator must not be able to widen their own envelope from the panel.

#include <Arduino.h>
#include "config.h"

struct Preset {
    char  name[UiCfg::PRESET_NAME_LEN + 1];
    float depthMm;
    bool  used;
};

class Store {
public:
    void begin();
    void update();               // performs the debounced flush

    // ---- presets ----
    uint8_t count() const;
    const Preset* get(uint8_t slot) const;
    bool  save(uint8_t slot, const char* name, float depthMm);
    bool  rename(uint8_t slot, const char* name);
    bool  clear(uint8_t slot);
    int   findFreeSlot() const;

    uint8_t activeSlot() const { return active_; }
    void    setActiveSlot(uint8_t s);

    // ---- calibration ----
    float plateMm() const { return plateMm_; }
    void  setPlateMm(float mm);

    // ---- teachable travel ceiling (Q27, long-press PRESET) ----
    // A per-job limit that can only ever be NARROWER than the commissioned
    // envelope. It is a convenience, never a protection - FluidNC's soft
    // limits are what actually stop the axis.
    bool  hasCeiling() const { return ceilingSet_; }
    float ceilingMm() const { return ceilingMm_; }
    void  setCeiling(float mm);
    void  clearCeiling();

private:
    void scheduleSave_();
    void load_();
    void flush_();

    Preset  presets_[UiCfg::MAX_PRESETS];
    uint8_t active_ = 0;
    float   plateMm_ = 0.0f;

    bool  ceilingSet_ = false;
    float ceilingMm_ = 0.0f;

    bool     dirty_ = false;
    uint32_t dirtyAtMs_ = 0;
};

extern Store Presets;
