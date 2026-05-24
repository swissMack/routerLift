#pragma once
#include <Arduino.h>
#include "config.h"

// Six preset slots backed by NVS (ESP32 Preferences library).
// Stored under namespace "rl-presets". NaN means "empty slot".

class Presets {
public:
    bool begin();

    bool   save(uint8_t slot, float mm);
    bool   clear(uint8_t slot);
    float  load(uint8_t slot) const;     // returns NAN if empty
    bool   isSet(uint8_t slot) const;

    // For UI navigation - currently highlighted slot.
    uint8_t activeSlot() const { return active_; }
    void    setActiveSlot(uint8_t s) { if (s < UI::NUM_PRESETS) active_ = s; }

private:
    float   cache_[UI::NUM_PRESETS] = {NAN, NAN, NAN, NAN, NAN, NAN};
    uint8_t active_ = 0;
};

extern Presets PresetStore;
