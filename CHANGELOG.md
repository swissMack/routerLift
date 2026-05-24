# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-24

Initial release.

### Added

- ESP32 firmware foundation built on PlatformIO + Arduino framework
- Motion control via FastAccelStepper with mm-based API and soft limits
- CNC-style manual pulse generator (MPG) input
  - 100 PPR full-quadrature decode via PCNT peripheral
  - 3-position rate switch (x1 / x10 / x100) for step-size band
  - Velocity-aware scaling within each band
- Touch UI on 3.5" ILI9488 + XPT2046
  - Bottom-bar buttons (MENU / PARK / POWER) on main screen
  - Hierarchical menu with BACK button
  - In-place calibration editing (tap row → edit with MPG → tap to commit)
- Six NVS-backed height presets
- Two-stage homing routine (fast seek + slow re-approach)
- Brass-stamp tool zeroing with offset compensation
- Solid-state relay control with configurable startup delay
- Foot switch plunge cycle (target → park)
- Dual-board architecture: 4-bit board ID via MCP23017 Port B
- Hardware watchdog and centralised fault handling
- ILI9488 display with sprite double-buffering

### Documentation

- `README.md` — quick start and tuning checklist
- `docs/HARDWARE.md` — BOM, pin map, level-shifter circuits
- `docs/ARCHITECTURE.md` — module map, state machine, safety design
- `docs/UX.md` — input model, screen-by-screen reference
- `CONTRIBUTING.md` — code style and PR guidelines
