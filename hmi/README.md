# HMI — ESP32-S3 operator panel

Our firmware. Runs on the Guition JC4827W543C (XH-S3E N4R8 module: ESP32-S3, 4 MB flash, 8 MB
octal PSRAM) and acts as a **GRBL sender** to the FluidNC board over UART.

```sh
pio run -e hmi          # build
pio run -e hmi -t upload
pio run -e hmi-diag     # board bring-up diagnostics
pio device monitor
```

Upload goes over the S3's native USB (`/dev/cu.usbmodem*`) and auto-resets. Only if the app has
hung: hold **BOOT**, tap **RST**, then upload.

`hmi-diag` skips all I²C (touch and MCP23017), waits for USB, logs display bring-up and cycles
red/green/blue. Never leave it on a panel in service — it has no touch or buttons.

## Pins (all in `include/pins.h`)

| Function | GPIO | Connector |
| --- | --- | --- |
| UART to FluidNC | TX 18 → FluidNC 16, RX 17 ← FluidNC 17 | P4 (P5 is the same — use one) |
| MPG A / B | 6 / 7, via a **74LVC14 on 3.3 V**, two stages per channel | P3 |
| MCP23017 (I²C bus 1, 100 kHz) | SDA 15 / SCL 16, external 4.7 kΩ pull-ups to 3.3 V | P3 |
| GT911 touch (I²C bus 0, on-board only) | SDA 8 / SCL 4, INT 3, RST 38 | — |
| NV3041A QSPI panel | CS 45, SCK 47, D0–D3 21/48/40/39, backlight 1 | — |
| Spares | 5, 9, 14 — **avoid 46** (boot strap) | P2 |

The MPG shifter is non-inverting, so `MpgCfg::SIGNALS_INVERTED = false`. A 74HCT14 is the wrong
part: it needs a 5 V supply and would drive 5 V into the S3.

## Restoring the factory demo

The board's original firmware is backed up in full (4 MB) at
`~/Documents/routerLift-firmware-backups/screen-original-dashboard.bin`. Restore with:

```sh
esptool.py --chip esp32s3 write_flash 0 screen-original-dashboard.bin
```

## Architecture invariant

**This board has no motion authority (ELE-11).** Soft limits, hard limits, homing and probing are
enforced by FluidNC. Nothing here may enforce a limit or be the last line of defence. A bug in
this firmware can produce a *wrong cutting depth*; it must never produce an *unsafe move*.

`Link` is the single chokepoint — nothing else may write to the UART. That is what keeps the
command vocabulary in `docs/UART-PROTOCOL.md` §4 exhaustive rather than aspirational.

**Status polling.** `Link` sends the `?` realtime byte every 100 ms (`LinkCfg::POLL_MS`).
FluidNC's `report_interval_ms` only reports on change, so without polling an idle machine sends
nothing and the link reads as lost. No status for 500 ms (`LinkCfg::TIMEOUT_MS`) = link lost:
feed hold is sent and Z0 is invalidated. Z0 stays invalid after the link recovers.

## Increments

| # | Scope | State |
| --- | --- | --- |
| 1 | Link, handwheel, buttons, headless serial diagnostics | Built. Link ✅ bench-verified (Step B); handwheel and buttons **not yet wired** |
| 2 | Display: Arduino_GFX NV3041A QSPI panel + GT911 touch + LVGL + main screen | Built. ✅ Display and touch bench-verified |
| 3 | Z0 validity, two-touch probe sequencing, named presets in NVS | Built. Z0 invalidation on link loss ✅ verified; probe not yet tested |
| 4 | Cycles: standard → bit-change → dovetail → keyhole | Not started |
| 5 | Fault log, diagnostics screen, runtime hours | Not started |

Increment 3 is enough, once the MPG, buttons and probe are wired, to attempt bench-test steps 1,
2, 4, 5 and the probe half of 7: the panel renders and touch tracks, the link comes up and status
is parsed, one detent moves the axis exactly 0.01 / 0.10 mm, the buttons and rough/fine selector
read correctly, and a two-touch probe sets Z0 while a failed probe leaves it invalid. Bench
progress is logged in `docs/BRINGUP-LOG.md`.

Flash ~24% of the 3 MB app slot (`huge_app.csv`).

## Modules

| File | Responsibility |
| --- | --- |
| `Link.{h,cpp}` | GRBL sender. Status parsing, one-command-in-flight window, realtime bytes |
| `Wheel.{h,cpp}` | MPG decode via PCNT, coalescing, look-ahead clamp, cancel-on-reversal |
| `Buttons.{h,cpp}` | MCP23017 polling, debounce, short/long press, ROUTER LED |
| `Display.{h,cpp}` | NV3041A QSPI panel, GT911 touch, LVGL plumbing, backlight dimming |
| `Ui.{h,cpp}` | LVGL screens. Increment 3 still builds the main screen only |
| `Zero.{h,cpp}` | Two-touch probe sequencing and Z0 validity - the most safety-relevant logic here |
| `Store.{h,cpp}` | NVS: named presets, plate thickness, teachable ceiling |
| `../include/lv_conf.h` | LVGL config - minimal, `lv_conf_internal.h` defaults the rest |
| `main.cpp` | Bring-up and the loop |
| `../include/pins.h` | **The only place GPIO numbers appear** |
| `../include/config.h` | Tunable constants, each citing the Q&A item that decided it |

## Two values from the datasheet, not a measurement

Both follow from the sauter FML-P's published 1.5 mm screw lead. The lift body is not yet bought,
so neither has been measured.

| Where | Value | Why provisional |
| --- | --- | --- |
| `firmware/config.yaml` | `steps_per_mm: 1066.67` | 1600 pulse/rev ÷ 1.5 mm — derived, confirm with a dial indicator |
| `include/config.h` | `MpgCfg::SCREW_LEAD_MM = 1.5` | Same lead; sets the look-ahead clamp distance |

Too large a clamp and it does nothing; too small and the wheel feels like it is dragging.

## Build notes worth keeping

- **`src_dir` / `include_dir` must be in `[platformio]`, not `[env:]`.** PlatformIO silently
  warns and then fails with "Nothing to build".
- **Do not name a constant `LINE_MAX`.** POSIX `<limits.h>` defines it as a macro and the
  collision produces a baffling "expected ']' before numeric constant" in an unrelated header.
- **The stock `esp32-s3-devkitc-1` definition assumes 8 MB flash and no PSRAM.** This board is
  4 MB flash with 8 MB *octal* PSRAM, so `board_build.arduino.memory_type = qio_opi` and the
  flash size overrides are both required. Octal is confirmed on the bench: with `qio_qspi` the
  PSRAM ID read fails.
- **Partitions must be `huge_app.csv`.** The stock table is the 8 MB layout and boot-loops on
  this 4 MB flash.
- **LVGL needs `-DLV_CONF_INCLUDE_SIMPLE` and `-I hmi/include` in `build_flags`.** Without them
  it looks for `../../lv_conf.h` next to the library and the entire of LVGL fails to compile,
  with an error that points at LVGL's internals rather than at your configuration.
- **Arduino-ESP32 core 3.x dropped the channel-based LEDC API.** `ledcSetup` + `ledcAttachPin`
  become `ledcAttach(pin, freq, res)` and `ledcWrite(pin, duty)`. Note an old 2.x header may
  still be on disk and will mislead you if you grep for the signature.
- **Arduino_GFX colour constants are `RGB565_BLACK`, not `BLACK`,** in 1.6.x.

## The panel constructor

The board is a **Guition JC4827W543C**: NV3041A over 4-bit QSPI (`Arduino_ESP32QSPI` +
`Arduino_NV3041A`), pins from the Guition vendor example, all in `pins.h`. The constructor's
`ips = true` is required — without it every colour comes out inverted. The GT911's axes are both
mirrored against the panel at rotation 0, so `Display.cpp` flips them.

**Wrong-board symptom worth remembering:** Rev H targeted a Sunton ESP32-4827S043 RGB panel.
That firmware boots cleanly on this board and shows nothing — `gfx->begin()` on an RGB bus cannot
tell no panel is attached. The gitignored `docs/4.3inch_ESP32-4827S043.zip` is that other board's
vendor pack and is not a reference for this one.

## Z0 validity — the rules

Z0 is the reference every cut depth is measured from, and **FluidNC has no concept of it**. This
board owns it entirely, which makes the FW-09 invalidation rules the most safety-relevant logic
in the HMI.

Invalidated by: link loss, alarm, bit-change entry, a failed probe, and never-set at boot.
Homing loss and E-stop arrive as an alarm and are covered by that.

**There is no override anywhere.** Not on the probe self-check, not on the re-probe after a bit
change, not on preset recall with an invalid Z0. That is deliberate: with no stall detection
(DEV-01), a wrong reference does not fail visibly — it produces a plausible-looking cut at the
wrong depth. Every override is a place to trust a number the machine cannot verify.

Two paths deliberately kept separate:

- `start()` runs the two-touch probe. The slow second touch is what delivers MOT-06's ±0.02 mm;
  the fast first touch only finds roughly where the surface is.
- `setHereUnprobed()` is the ZERO long-press. Never routed through the probe path, so it cannot
  be mistaken for a measured touch-off.

FLT-02's probe self-check is enforced by FluidNC via `probe: check_mode_start`, not here. If the
probe is already triggered — a trapped croc clip, a chip bridging the plate — `G38.2` returns an
error rather than instantly "succeeding" and setting Z0 wherever the bit happens to be.

## Next: increment 4

The cycles, in the order set by Q37: standard → bit-change → dovetail → keyhole. Keyhole last —
it is the only cycle where the cutter moves under power while engaged.
