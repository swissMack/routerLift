#include "Display.h"
#include "config.h"
#include "pins.h"
#include <Arduino_GFX_Library.h>
#include <TAMC_GT911.h>
#include <Wire.h>

Display Screen;

// ---------------------------------------------------------------------------
// Panel. The TIMING VALUES are verbatim from the vendor demo at
// docs/4.3inch_ESP32-4827S043.zip:
//   1-Demo/Demo_Arduino/3_3-4_TFT-LVGL-Widgets/LvglWidgets/
//
// The API SHAPE differs: the demo targets an older Arduino_GFX, while 1.6.7
// moved the timings into the panel constructor and renamed the display class
// from Arduino_RPi_DPI_RGBPanel to Arduino_RGB_Display. Same numbers, new
// arrangement. Do not re-derive the porch or pclk values from the datasheet -
// getting them wrong gives a rolling or blank panel, not a clean error.
// ---------------------------------------------------------------------------
static Arduino_ESP32RGBPanel* panel = new Arduino_ESP32RGBPanel(
    40 /* DE */, 41 /* VSYNC */, 39 /* HSYNC */, 42 /* PCLK */,
    45 /* R0 */, 48 /* R1 */, 47 /* R2 */, 21 /* R3 */, 14 /* R4 */,
    5  /* G0 */, 6  /* G1 */, 7  /* G2 */, 15 /* G3 */, 16 /* G4 */, 4 /* G5 */,
    8  /* B0 */, 3  /* B1 */, 46 /* B2 */, 9  /* B3 */, 1 /* B4 */,
    0 /* hsync_polarity */, 8 /* hsync_front_porch */,
    4 /* hsync_pulse_width */, 43 /* hsync_back_porch */,
    0 /* vsync_polarity */, 8 /* vsync_front_porch */,
    4 /* vsync_pulse_width */, 12 /* vsync_back_porch */,
    1 /* pclk_active_neg */, 9000000 /* prefer_speed */);

static Arduino_RGB_Display* gfx = new Arduino_RGB_Display(
    480 /* width */, 272 /* height */, panel, 0 /* rotation */, true /* auto_flush */);

// GT911 on the same I2C bus as the MCP23017 expander (0x5D vs 0x20).
// INT is unwired on this board, hence -1.
static TAMC_GT911 ts(Pins::I2C_SDA, Pins::I2C_SCL, -1, 38, 480, 272);

// ---------------------------------------------------------------------------
// LVGL plumbing
// ---------------------------------------------------------------------------
static lv_disp_draw_buf_t draw_buf;
static lv_color_t*        buf = nullptr;
static lv_disp_drv_t      disp_drv;
static lv_indev_drv_t     indev_drv;

static void flush_cb(lv_disp_drv_t* d, const lv_area_t* area, lv_color_t* color_p) {
    const uint32_t w = area->x2 - area->x1 + 1;
    const uint32_t h = area->y2 - area->y1 + 1;
#if (LV_COLOR_16_SWAP != 0)
    gfx->draw16bitBeRGBBitmap(area->x1, area->y1, (uint16_t*)&color_p->full, w, h);
#else
    gfx->draw16bitRGBBitmap(area->x1, area->y1, (uint16_t*)&color_p->full, w, h);
#endif
    lv_disp_flush_ready(d);
}

static void touch_cb(lv_indev_drv_t*, lv_indev_data_t* data) {
    ts.read();
    if (ts.isTouched && ts.touches > 0) {
        data->state   = LV_INDEV_STATE_PR;
        data->point.x = ts.points[0].x;
        data->point.y = ts.points[0].y;
        Screen.noteActivity();
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

// ---------------------------------------------------------------------------

bool Display::begin() {
    gfx->begin();

    // Backlight on LEDC so it can be dimmed rather than blanked (Q30).
    // Arduino-ESP32 core 3.x is pin-based; the 2.x channel API is gone.
    ledcAttach(Pins::TFT_BL, 5000, 8);
    setBacklight_(UiCfg::BACKLIGHT_ON);

    gfx->fillScreen(RGB565_BLACK);
    w_ = gfx->width();
    h_ = gfx->height();

    lv_init();

    // Wire.begin() has already been called by Buttons::begin() for the
    // expander; TAMC_GT911 calls it again, which is harmless.
    ts.begin();
    ts.setRotation(ROTATION_NORMAL);

    // Quarter-screen draw buffer in internal RAM, as the vendor demo does.
    // The 261 KB panel framebuffer lives in PSRAM and is Arduino_GFX's problem.
    const uint32_t px = (uint32_t)w_ * h_ / 4;
    buf = (lv_color_t*)heap_caps_malloc(sizeof(lv_color_t) * px,
                                        MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!buf) {
        // Not fatal to the machine: the panel is an operator convenience and
        // FluidNC still enforces every limit. But the UI cannot run.
        Serial.println("[LVGL] draw buffer allocation FAILED");
        return false;
    }
    lv_disp_draw_buf_init(&draw_buf, buf, nullptr, px);

    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res  = w_;
    disp_drv.ver_res  = h_;
    disp_drv.flush_cb = flush_cb;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    lv_indev_drv_init(&indev_drv);
    indev_drv.type    = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = touch_cb;
    lv_indev_drv_register(&indev_drv);

    lastActivityMs_ = millis();
    ok_ = true;
    return true;
}

void Display::update() {
    if (!ok_) return;
    lv_timer_handler();

    if (!dimmed_ && (millis() - lastActivityMs_) > UiCfg::DIM_AFTER_MS) {
        dimmed_ = true;
        setBacklight_(UiCfg::BACKLIGHT_DIM);
    }
}

void Display::noteActivity() {
    lastActivityMs_ = millis();
    if (dimmed_) {
        dimmed_ = false;
        setBacklight_(UiCfg::BACKLIGHT_ON);
    }
}

void Display::setBacklight_(uint8_t duty) {
    ledcWrite(Pins::TFT_BL, duty);
}
