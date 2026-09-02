#pragma once
//
// LVGL 8.4 configuration for routerLift.
//
// Deliberately minimal: lv_conf_internal.h supplies a default for anything not
// set here, so only the settings that actually matter for this board are
// listed. Reached via -DLV_CONF_INCLUDE_SIMPLE with hmi/include on the path.

#define LV_CONF_H

// ---- colour ---------------------------------------------------------------
// RGB565 to match the ILI6485 panel. LV_COLOR_16_SWAP stays 0 because
// Arduino_GFX's draw16bitRGBBitmap already expects native byte order.
#define LV_COLOR_DEPTH 16
#define LV_COLOR_16_SWAP 0

// ---- memory ---------------------------------------------------------------
// LVGL's own heap, separate from the draw buffer and the panel framebuffer.
// The framebuffer (480x272x2 = 261 KB) lives in PSRAM, which is why
// board_build.arduino.memory_type = qio_opi is mandatory.
#define LV_MEM_CUSTOM 0
#define LV_MEM_SIZE (48U * 1024U)

// ---- tick -----------------------------------------------------------------
#define LV_TICK_CUSTOM 1
#define LV_TICK_CUSTOM_INCLUDE "Arduino.h"
#define LV_TICK_CUSTOM_SYS_TIME_EXPR (millis())

#define LV_DISP_DEF_REFR_PERIOD 20      // 50 Hz
#define LV_INDEV_DEF_READ_PERIOD 20

// ---- fonts ----------------------------------------------------------------
// The height readout dominates the layout (Q25), so a large face is needed.
// Montserrat 48 renders "12.34" legibly from across a bench.
#define LV_FONT_MONTSERRAT_14 1
#define LV_FONT_MONTSERRAT_16 1
#define LV_FONT_MONTSERRAT_20 1
#define LV_FONT_MONTSERRAT_48 1
#define LV_FONT_DEFAULT &lv_font_montserrat_16

// ---- widgets --------------------------------------------------------------
// Only what the UI actually uses. Keyboard and textarea are needed for named
// presets (Q26); msgbox for faults.
#define LV_USE_LABEL     1
#define LV_USE_BTN       1
#define LV_USE_BTNMATRIX 1
#define LV_USE_BAR       1
#define LV_USE_KEYBOARD  1
#define LV_USE_TEXTAREA  1
#define LV_USE_MSGBOX    1
#define LV_USE_LIST      1
#define LV_USE_TABVIEW   1
#define LV_USE_ROLLER    1

// ---- off ------------------------------------------------------------------
// No demos, no filesystem, no images from file. This is a machine panel.
#define LV_USE_DEMO_WIDGETS 0
#define LV_USE_PERF_MONITOR 0
#define LV_USE_MEM_MONITOR  0
#define LV_USE_LOG          0
