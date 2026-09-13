#include "Display.h"
#include "config.h"
#include "pins.h"
#include <Arduino_GFX_Library.h>
#include <TAMC_GT911.h>
#include <Wire.h>

Display Screen;

// ---------------------------------------------------------------------------
// Panel: Guition JC4827W543C - NV3041A controller over 4-bit QSPI.
//
// Drawn directly to the controller with no Arduino_Canvas in between, so
// LVGL's flush writes straight to the panel and there is no second
// framebuffer to keep in step. ips = true applies the colour inversion this
// IPS panel needs; without it every colour comes out inverted.
//
// History: Rev H drove a Sunton ESP32-4827S043 RGB panel here. That firmware
// boots cleanly on this board and shows nothing, because gfx->begin() on an
// RGB bus has no way to notice that no panel is attached.
// ---------------------------------------------------------------------------
static Arduino_DataBus* bus = new Arduino_ESP32QSPI(
    Pins::LCD_CS, Pins::LCD_SCK,
    Pins::LCD_D0, Pins::LCD_D1, Pins::LCD_D2, Pins::LCD_D3);

static Arduino_NV3041A* gfx = new Arduino_NV3041A(
    bus, GFX_NOT_DEFINED /* RST - tied to EN on this board */,
    0 /* rotation */, true /* IPS */);

// GT911 on the board's own I2C bus (Wire, 8/4). The MCP23017 has a separate
// bus - see Buttons.cpp.
static TAMC_GT911 ts(Pins::I2C_SDA, Pins::I2C_SCL,
                     Pins::TOUCH_INT, Pins::TOUCH_RST, 480, 272);

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
#ifdef HMI_DIAG_NO_I2C
    data->state = LV_INDEV_STATE_REL;
    return;
#endif
    ts.read();
    // Edge-logged so the serial console shows touch without flooding it at
    // LVGL's poll rate. Nothing on the main screen reacts to a tap yet, so this
    // is the only bench-visible proof that the GT911 is alive.
    static bool wasDown = false;
    if (ts.isTouched && ts.touches > 0) {
        // Both touch axes are mirrored against the panel at rotation 0 on the
        // JC4827W543C: a top-left tap reads ~(460, 230). Measured on the bench
        // 2026-09-13 with 14 taps. Flipped explicitly here rather than through
        // TAMC_GT911::setRotation so the correction is visible in our code.
        const int16_t x = (int16_t)(gfx->width()  - 1 - ts.points[0].x);
        const int16_t y = (int16_t)(gfx->height() - 1 - ts.points[0].y);
        data->state   = LV_INDEV_STATE_PR;
        data->point.x = x;
        data->point.y = y;
        Screen.noteActivity();
        if (!wasDown) Serial.printf("[TOUCH] down %d,%d\n", x, y);
        wasDown = true;
    } else {
        data->state = LV_INDEV_STATE_REL;
        if (wasDown) Serial.println("[TOUCH] up");
        wasDown = false;
    }
}

// ---------------------------------------------------------------------------

bool Display::begin() {
#ifdef HMI_DIAG_NO_I2C
    Serial.println("[DIAG] gfx->begin() ...");
#endif
    const bool gfxOk = gfx->begin();
#ifdef HMI_DIAG_NO_I2C
    Serial.printf("[DIAG] gfx->begin() returned %s, %dx%d\n",
                  gfxOk ? "true" : "FALSE", gfx->width(), gfx->height());
#else
    (void)gfxOk;
#endif

    // Backlight on LEDC so it can be dimmed rather than blanked (Q30).
    // Arduino-ESP32 core 3.x is pin-based; the 2.x channel API is gone.
    const bool blOk = ledcAttach(Pins::TFT_BL, 5000, 8);
    setBacklight_(UiCfg::BACKLIGHT_ON);
#ifdef HMI_DIAG_NO_I2C
    Serial.printf("[DIAG] backlight GPIO %d attach %s, duty %u\n",
                  Pins::TFT_BL, blOk ? "ok" : "FAILED", (unsigned)UiCfg::BACKLIGHT_ON);
    // Same colour cycle as the vendor demo: proves panel + timings + backlight.
    gfx->fillScreen(RGB565_RED);   delay(700);
    gfx->fillScreen(RGB565_GREEN); delay(700);
    gfx->fillScreen(RGB565_BLUE);  delay(700);
    Serial.println("[DIAG] colour cycle done");
#else
    (void)blOk;
#endif

    gfx->fillScreen(RGB565_BLACK);
    w_ = gfx->width();
    h_ = gfx->height();

    lv_init();

    // Wire.begin() has already been called by Buttons::begin() for the
    // expander; TAMC_GT911 calls it again, which is harmless.
#ifndef HMI_DIAG_NO_I2C
    ts.begin();
    ts.setRotation(ROTATION_NORMAL);
#endif

    // Quarter-screen draw buffer in internal RAM, as the vendor demo does.
    // No panel framebuffer on this board: flush_cb writes straight to the
    // NV3041A over QSPI, so this buffer is the only copy of the pixels.
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
