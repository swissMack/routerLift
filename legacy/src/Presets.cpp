#include "Presets.h"
#include <Preferences.h>

static Preferences prefs;
static const char* NS = "rl-presets";

Presets PresetStore;

bool Presets::begin() {
    prefs.begin(NS, /*readOnly=*/false);
    char key[8];
    for (uint8_t i = 0; i < UI::NUM_PRESETS; ++i) {
        snprintf(key, sizeof(key), "p%u", i);
        cache_[i] = prefs.getFloat(key, NAN);
    }
    prefs.end();
    return true;
}

bool Presets::save(uint8_t slot, float mm) {
    if (slot >= UI::NUM_PRESETS) return false;
    cache_[slot] = mm;
    prefs.begin(NS, false);
    char key[8];
    snprintf(key, sizeof(key), "p%u", slot);
    prefs.putFloat(key, mm);
    prefs.end();
    return true;
}

bool Presets::clear(uint8_t slot) {
    if (slot >= UI::NUM_PRESETS) return false;
    cache_[slot] = NAN;
    prefs.begin(NS, false);
    char key[8];
    snprintf(key, sizeof(key), "p%u", slot);
    prefs.remove(key);
    prefs.end();
    return true;
}

float Presets::load(uint8_t slot) const {
    if (slot >= UI::NUM_PRESETS) return NAN;
    return cache_[slot];
}

bool Presets::isSet(uint8_t slot) const {
    if (slot >= UI::NUM_PRESETS) return false;
    return !isnan(cache_[slot]);
}
