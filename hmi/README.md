# HMI — ESP32-S3 operator panel

Our firmware. Runs on the ESP32-4827S043 (ESP32-S3-WROOM-1-N4R8) and acts as a **GRBL sender**
to the FluidNC board over UART.

```sh
pio run -e hmi          # build
pio run -e hmi -t upload
pio device monitor
```

## Architecture invariant

**This board has no motion authority (ELE-11).** Soft limits, hard limits, homing and probing are
enforced by FluidNC. Nothing here may enforce a limit or be the last line of defence. A bug in
this firmware can produce a *wrong cutting depth*; it must never produce an *unsafe move*.

`Link` is the single chokepoint — nothing else may write to the UART. That is what keeps the
command vocabulary in `docs/UART-PROTOCOL.md` §4 exhaustive rather than aspirational.

## Increments

| # | Scope | State |
| --- | --- | --- |
| 1 | Link, handwheel, buttons, headless serial diagnostics | Built |
| **2** | Display: Arduino_GFX RGB panel + GT911 touch + LVGL + main screen | **Built and compiling** |
| 3 | Zero / Z0 validity, named presets in NVS | Not started |
| 4 | Cycles: standard → bit-change → dovetail → keyhole | Not started |
| 5 | Fault log, diagnostics screen, runtime hours | Not started |

Increment 2 is enough to pass bench-test steps 1, 2, 4 and 5: the panel renders and touch
tracks, the link comes up and status is parsed, one detent moves the axis exactly 0.01 / 0.10 mm,
and the buttons and rough/fine selector read correctly.

RAM 22.4%, flash 21.4% of 4 MB.

## Modules

| File | Responsibility |
| --- | --- |
| `Link.{h,cpp}` | GRBL sender. Status parsing, one-command-in-flight window, realtime bytes |
| `Wheel.{h,cpp}` | MPG decode via PCNT, coalescing, look-ahead clamp, cancel-on-reversal |
| `Buttons.{h,cpp}` | MCP23017 polling, debounce, short/long press, ROUTER LED |
| `Display.{h,cpp}` | RGB panel, GT911 touch, LVGL plumbing, backlight dimming |
| `Ui.{h,cpp}` | LVGL screens. Increment 2 builds the main screen only |
| `../include/lv_conf.h` | LVGL config - minimal, `lv_conf_internal.h` defaults the rest |
| `main.cpp` | Bring-up and the loop |
| `../include/pins.h` | **The only place GPIO numbers appear** |
| `../include/config.h` | Tunable constants, each citing the Q&A item that decided it |

## Two provisional values

Both follow from the screw lead, which is unknown until a lift body is chosen and measured.

| Where | Value | Why provisional |
| --- | --- | --- |
| `firmware/config.yaml` | `steps_per_mm: 800` | Assumes a 2 mm lead |
| `include/config.h` | `MpgCfg::SCREW_LEAD_MM = 2.0` | Same assumption; sets the look-ahead clamp distance |

Too large a clamp and it does nothing; too small and the wheel feels like it is dragging.

## Build notes worth keeping

- **`src_dir` / `include_dir` must be in `[platformio]`, not `[env:]`.** PlatformIO silently
  warns and then fails with "Nothing to build".
- **Do not name a constant `LINE_MAX`.** POSIX `<limits.h>` defines it as a macro and the
  collision produces a baffling "expected ']' before numeric constant" in an unrelated header.
- **The stock `esp32-s3-devkitc-1` definition assumes 8 MB flash and no PSRAM.** This board is
  4 MB flash with 8 MB *octal* PSRAM, so `board_build.arduino.memory_type = qio_opi` and the
  flash size overrides are both required. With the wrong memory type the panel driver has no
  framebuffer.
- **LVGL needs `-DLV_CONF_INCLUDE_SIMPLE` and `-I hmi/include` in `build_flags`.** Without them
  it looks for `../../lv_conf.h` next to the library and the entire of LVGL fails to compile,
  with an error that points at LVGL's internals rather than at your configuration.
- **Arduino-ESP32 core 3.x dropped the channel-based LEDC API.** `ledcSetup` + `ledcAttachPin`
  become `ledcAttach(pin, freq, res)` and `ledcWrite(pin, duty)`. Note an old 2.x header may
  still be on disk and will mislead you if you grep for the signature.
- **Arduino_GFX colour constants are `RGB565_BLACK`, not `BLACK`,** in 1.6.x.

## The panel constructor

The **timing values** in `Display.cpp` are verbatim from the vendor demo in
`docs/4.3inch_ESP32-4827S043.zip` at `1-Demo/Demo_Arduino/3_3-4_TFT-LVGL-Widgets/`. Do not
re-derive the porch or pclk numbers from the datasheet — wrong values give a rolling or blank
panel rather than a clean error, which is a miserable thing to debug.

The **API shape** differs from the demo. It targets an older Arduino_GFX; 1.6.7 moved the timings
into `Arduino_ESP32RGBPanel` and renamed the display class from `Arduino_RPi_DPI_RGBPanel` to
`Arduino_RGB_Display`. Same numbers, different arrangement. If you ever pin an older GFX, the
demo's literal constructor works as written.

The zip is gitignored (112 MB, over GitHub's file limit) and exists only on the build machine.

## Next: increment 3

Zero / Z0-validity tracking and named presets in NVS. Then the cycles, in the order set by Q37:
standard → bit-change → dovetail → keyhole.
