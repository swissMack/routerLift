#include "Store.h"
#include <Preferences.h>
#include <string.h>

Store Presets;
static Preferences prefs;

void Store::begin() {
    memset(presets_, 0, sizeof(presets_));
    plateMm_ = MotionCfg::PROBE_PLATE_MM;
    load_();
}

void Store::load_() {
    if (!prefs.begin(Nvs::NS_PRESETS, /*readOnly=*/true)) return;

    char key[8];
    for (uint8_t i = 0; i < UiCfg::MAX_PRESETS; i++) {
        snprintf(key, sizeof(key), "p%u", i);
        if (prefs.getBytesLength(key) == sizeof(Preset)) {
            prefs.getBytes(key, &presets_[i], sizeof(Preset));
            presets_[i].name[UiCfg::PRESET_NAME_LEN] = '\0';   // never trust flash
        }
    }
    active_     = prefs.getUChar("active", 0);
    plateMm_    = prefs.getFloat("plate", MotionCfg::PROBE_PLATE_MM);
    ceilingSet_ = prefs.getBool("ceilSet", false);
    ceilingMm_  = prefs.getFloat("ceil", 0.0f);
    prefs.end();

    if (active_ >= UiCfg::MAX_PRESETS) active_ = 0;
}

void Store::flush_() {
    if (!prefs.begin(Nvs::NS_PRESETS, /*readOnly=*/false)) return;

    char key[8];
    for (uint8_t i = 0; i < UiCfg::MAX_PRESETS; i++) {
        snprintf(key, sizeof(key), "p%u", i);
        if (presets_[i].used) prefs.putBytes(key, &presets_[i], sizeof(Preset));
        else                  prefs.remove(key);
    }
    prefs.putUChar("active", active_);
    prefs.putFloat("plate", plateMm_);
    prefs.putBool("ceilSet", ceilingSet_);
    prefs.putFloat("ceil", ceilingMm_);
    prefs.end();

    dirty_ = false;
}

// Debounced flush, ported from legacy/src/Settings.cpp: mark dirty on every
// edit, write only once the operator has stopped fiddling.
void Store::update() {
    if (!dirty_) return;
    if (millis() - dirtyAtMs_ < Nvs::SAVE_DEBOUNCE_MS) return;
    flush_();
}

void Store::scheduleSave_() {
    dirty_ = true;
    dirtyAtMs_ = millis();
}

uint8_t Store::count() const {
    uint8_t n = 0;
    for (uint8_t i = 0; i < UiCfg::MAX_PRESETS; i++) if (presets_[i].used) n++;
    return n;
}

const Preset* Store::get(uint8_t slot) const {
    if (slot >= UiCfg::MAX_PRESETS || !presets_[slot].used) return nullptr;
    return &presets_[slot];
}

bool Store::save(uint8_t slot, const char* name, float depthMm) {
    if (slot >= UiCfg::MAX_PRESETS) return false;
    strncpy(presets_[slot].name, name ? name : "", UiCfg::PRESET_NAME_LEN);
    presets_[slot].name[UiCfg::PRESET_NAME_LEN] = '\0';
    presets_[slot].depthMm = depthMm;
    presets_[slot].used = true;
    scheduleSave_();
    return true;
}

bool Store::rename(uint8_t slot, const char* name) {
    if (slot >= UiCfg::MAX_PRESETS || !presets_[slot].used) return false;
    strncpy(presets_[slot].name, name ? name : "", UiCfg::PRESET_NAME_LEN);
    presets_[slot].name[UiCfg::PRESET_NAME_LEN] = '\0';
    scheduleSave_();
    return true;
}

bool Store::clear(uint8_t slot) {
    if (slot >= UiCfg::MAX_PRESETS) return false;
    memset(&presets_[slot], 0, sizeof(Preset));
    scheduleSave_();
    return true;
}

int Store::findFreeSlot() const {
    for (uint8_t i = 0; i < UiCfg::MAX_PRESETS; i++) if (!presets_[i].used) return i;
    return -1;
}

void Store::setActiveSlot(uint8_t s) {
    if (s >= UiCfg::MAX_PRESETS) return;
    active_ = s;
    scheduleSave_();
}

void Store::setPlateMm(float mm) {
    plateMm_ = mm;
    scheduleSave_();
}

void Store::setCeiling(float mm) {
    ceilingMm_ = mm;
    ceilingSet_ = true;
    scheduleSave_();
}

void Store::clearCeiling() {
    ceilingSet_ = false;
    ceilingMm_ = 0.0f;
    scheduleSave_();
}
