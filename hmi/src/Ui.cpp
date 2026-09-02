#include "Ui.h"
#include "config.h"
#include "Link.h"
#include "Wheel.h"
#include <stdio.h>

Ui Screens;

static const lv_color_t COL_BG    = LV_COLOR_MAKE(0x10, 0x12, 0x14);
static const lv_color_t COL_TEXT  = LV_COLOR_MAKE(0xF0, 0xF0, 0xEC);
static const lv_color_t COL_OK    = LV_COLOR_MAKE(0x3D, 0xD5, 0x6E);
static const lv_color_t COL_WARN  = LV_COLOR_MAKE(0xE8, 0xA3, 0x3D);
static const lv_color_t COL_FAULT = LV_COLOR_MAKE(0xE5, 0x48, 0x4A);
static const lv_color_t COL_DIM   = LV_COLOR_MAKE(0x6A, 0x70, 0x76);

static lv_obj_t* chip(lv_obj_t* parent, int16_t x, const char* text) {
    lv_obj_t* l = lv_label_create(parent);
    lv_label_set_text(l, text);
    lv_obj_set_style_text_font(l, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(l, COL_DIM, 0);
    lv_obj_align(l, LV_ALIGN_LEFT_MID, x, 0);
    return l;
}

void Ui::begin() {
    buildMain_();
    lastRefreshMs_ = millis();
}

void Ui::buildMain_() {
    scrMain_ = lv_obj_create(nullptr);
    lv_obj_set_style_bg_color(scrMain_, COL_BG, 0);
    lv_obj_clear_flag(scrMain_, LV_OBJ_FLAG_SCROLLABLE);

    // ---- height readout: the number you read from across the bench --------
    lblHeight_ = lv_label_create(scrMain_);
    lv_label_set_text(lblHeight_, "--.--");
    lv_obj_set_style_text_font(lblHeight_, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_color(lblHeight_, COL_TEXT, 0);
    lv_obj_align(lblHeight_, LV_ALIGN_CENTER, 0, -40);

    lv_obj_t* unit = lv_label_create(scrMain_);
    lv_label_set_text(unit, "mm");
    lv_obj_set_style_text_font(unit, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(unit, COL_DIM, 0);
    lv_obj_align(unit, LV_ALIGN_CENTER, 0, 10);

    // ---- message line ------------------------------------------------------
    lblMsg_ = lv_label_create(scrMain_);
    lv_label_set_text(lblMsg_, "");
    lv_obj_set_style_text_font(lblMsg_, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(lblMsg_, COL_WARN, 0);
    lv_obj_align(lblMsg_, LV_ALIGN_CENTER, 0, 48);

    // ---- status strip: all four Q25 items, always visible ------------------
    lv_obj_t* strip = lv_obj_create(scrMain_);
    lv_obj_set_size(strip, 480, 46);
    lv_obj_align(strip, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(strip, LV_COLOR_MAKE(0x1C, 0x1F, 0x22), 0);
    lv_obj_set_style_border_width(strip, 0, 0);
    lv_obj_set_style_radius(strip, 0, 0);
    lv_obj_clear_flag(strip, LV_OBJ_FLAG_SCROLLABLE);

    lblZ0_     = chip(strip, 4,   "Z0 --");
    lblState_  = chip(strip, 96,  "----");
    lblRouter_ = chip(strip, 190, "RTR OFF");
    lblScale_  = chip(strip, 300, "FINE");
    lblLink_   = chip(strip, 380, "NOLINK");

    lv_scr_load(scrMain_);
}

void Ui::refresh_() {
    char buf[24];

    // Height. Two decimals throughout (ELE-08, Q29).
    if (Motion.isConnected()) {
        snprintf(buf, sizeof(buf), "%.*f", UiCfg::DECIMALS, Motion.positionMm());
    } else {
        snprintf(buf, sizeof(buf), "--.--");
    }
    lv_label_set_text(lblHeight_, buf);

    // Z0 validity. Without this the height above is meaningless and the
    // operator would have no way to know (FW-09).
    lv_label_set_text(lblZ0_, z0Valid_ ? "Z0 OK" : "Z0 BAD");
    lv_obj_set_style_text_color(lblZ0_, z0Valid_ ? COL_OK : COL_FAULT, 0);

    // Machine state.
    const bool alarm = (Motion.state() == MachineState::Alarm);
    lv_label_set_text(lblState_, Motion.stateName());
    lv_obj_set_style_text_color(lblState_, alarm ? COL_FAULT : COL_TEXT, 0);

    // Router. SAF-03 - never be unsure whether the cutter is live.
    const bool rtr = Motion.routerOn();
    lv_label_set_text(lblRouter_, rtr ? "RTR ON" : "RTR OFF");
    lv_obj_set_style_text_color(lblRouter_, rtr ? COL_FAULT : COL_DIM, 0);

    // MPG scale (ELE-09).
    lv_label_set_text(lblScale_, Handwheel.isRough() ? "ROUGH" : "FINE");

    // Link. A dropped link is otherwise silent until you turn the wheel.
    const bool up = Motion.isConnected();
    lv_label_set_text(lblLink_, up ? "LINK" : "NOLINK");
    lv_obj_set_style_text_color(lblLink_, up ? COL_OK : COL_FAULT, 0);
}

void Ui::update() {
    if (!scrMain_) return;
    if (millis() - lastRefreshMs_ < UiCfg::REFRESH_MS) return;
    lastRefreshMs_ = millis();
    refresh_();
}

void Ui::showMessage(const char* msg) {
    if (lblMsg_) lv_label_set_text(lblMsg_, msg ? msg : "");
}
