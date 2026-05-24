# routerLift

Open-firmware automated router lift, ESP32-based, with a CNC-style manual
pulse generator (MPG) for jogging and a touch panel for menu navigation.

## At a glance

- ESP32 + PlatformIO + Arduino framework
- 3.5" ILI9488 TFT + XPT2046 resistive touch
- 5 V 4-terminal MPG (100 PPR) via opto-isolation, x1 / x10 / x100 rate switch
- DM542 stepper driver + ball-screw spindle, 1000 microsteps/rev
- NPN inductive endstops + brass-stamp tool-zeroing sensor
- Solid-state relay for router power with configurable startup delay
- Foot-switch plunge: press → target height, release → park
- Six NVS-backed height presets
- Hardware watchdog, soft limits, fault state machine

Status: **v1.0.0** — compiles, all modules wired. Calibration values
(steps/rev, pitch, soft limits, stamp offset) need tuning to your
mechanics before cutting.

## Documentation

- [docs/HARDWARE.md](docs/HARDWARE.md) — BOM, wiring, pin map, level-shifter circuit
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module breakdown, state machines, safety design
- [docs/UX.md](docs/UX.md) — MPG / touch / foot switch interaction model
- [CONTRIBUTING.md](CONTRIBUTING.md) — code style, commit conventions
- [CHANGELOG.md](CHANGELOG.md) — version history

## Quick start

```sh
git clone git@github.com:swissMack/routerLift.git
cd routerLift
pio run                  # compile
pio run -t upload        # flash
pio device monitor       # serial console at 115200
```

PlatformIO will pull all required libraries on first build:
FastAccelStepper, ESP32Encoder, TFT_eSPI, Adafruit_MCP23X17,
XPT2046_Touchscreen, ArduinoJson.

## Tuning checklist (before first cut)

1. Verify `DEFAULT_STEPS_PER_REV` matches your DM542 microstep DIP setting
2. Measure `DEFAULT_SPINDLE_PITCH_MM` (ball-screw lead per revolution)
3. Set `DEFAULT_SOFT_MIN_MM` and `DEFAULT_SOFT_MAX_MM` to safe travel limits
4. Set `DEFAULT_PARK_MM` to a position safely below the table surface
5. Calibrate `DEFAULT_STAMP_OFFSET_MM` with calipers
6. Tune `RELAY_STARTUP_DELAY_MS` to your router's spin-up time
7. Verify `MPG::SIGNALS_INVERTED` matches your level-shifter (PC817 = true, 74HCT14 double-buffered = false)
8. Start with `DEFAULT_MAX_SPEED_MM_S` conservative; increase after testing

## Reference materials

The `docs/reference/FXBB-original/` directory contains the original FXBB
FräsLift V3 documentation (PCB, schematic, software manual) that this
project draws inspiration from.

## Safety

This firmware drives a high-RPM router. Soft limits, endstops, and the
watchdog converge on a single fault handler that emergency-stops the
motor and forces the relay off. **Test with the router unpowered first.**
The author accepts no liability for misuse — read `docs/ARCHITECTURE.md`
before modifying motion-critical code.
