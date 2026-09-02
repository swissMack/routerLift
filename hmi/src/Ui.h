#pragma once
//
// Ui — LVGL screens.
//
// Increment 2 builds only the main screen: the height readout and the status
// strip. Q25 asked for four things visible at all times, on a 480x272 panel,
// so the layout is roughly 3:1 - a dominant numeral over a slim strip.
//
//   +----------------------------------------------+
//   |                                              |
//   |            12.34 mm                          |  <- ~200 px, Montserrat 48
//   |                                              |
//   +----------------------------------------------+
//   | Z0 OK | IDLE | ROUTER | FINE | LINK          |  <- ~60 px
//   +----------------------------------------------+
//
// Second-level work - cycle config, preset management, calibration,
// diagnostics - stays on the touchscreen in later increments. Anything used
// while the router is running is a physical button, not a touch target (ENV-01).

#include <Arduino.h>
#include <lvgl.h>

class Ui {
public:
    void begin();
    void update();     // refresh from Link/Wheel state at UiCfg::REFRESH_MS

    void setZ0Valid(bool v) { z0Valid_ = v; }
    bool z0Valid() const { return z0Valid_; }

    void showMessage(const char* msg);

private:
    void buildMain_();
    void refresh_();

    lv_obj_t* scrMain_   = nullptr;
    lv_obj_t* lblHeight_ = nullptr;
    lv_obj_t* lblZ0_     = nullptr;
    lv_obj_t* lblState_  = nullptr;
    lv_obj_t* lblRouter_ = nullptr;
    lv_obj_t* lblScale_  = nullptr;
    lv_obj_t* lblLink_   = nullptr;
    lv_obj_t* lblMsg_    = nullptr;

    bool     z0Valid_ = false;
    uint32_t lastRefreshMs_ = 0;
};

extern Ui Screens;
