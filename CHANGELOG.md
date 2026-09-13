# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — HMI board correction

Bench bring-up on 2026-09-13 showed the panel in hand is a **Guition
JC4827W543C**, not the Sunton ESP32-4827S043 that Rev H recorded. Spec Annex
B.10 was right; Rev H's "correction" of it was mistaken.

### Fixed

- HMI targets the JC4827W543C (XH-S3E N4R8 module): NV3041A panel over 4-bit
  QSPI (CS 45, SCK 47, D0–D3 21/48/40/39), IPS colour inversion, backlight on
  GPIO 1
- GT911 touch on the board's own I²C bus, SDA 8 / SCL 4, INT 3, RST 38. Both
  touch axes are flipped in firmware to match the panel at rotation 0
- MCP23017 button expander moved to its own I²C bus on GPIO 15 SDA / 16 SCL
  (connector P3), with external 4.7 kΩ pull-ups — the touch bus reaches no
  connector
- MPG A/B moved from GPIO 11/12 to 6/7 (connector P3); 11/12 are TF-card lines
  on this board
- `huge_app.csv` partitions — the stock 8 MB table boot-looped on 4 MB flash
- `memory_type = qio_opi` confirmed: PSRAM is octal, quad fails the ID read

### Added

- `hmi-diag` PlatformIO environment for board bring-up

## [Unreleased] — Rev H split architecture

The single-ESP32 design is superseded. Motion moves to stock FluidNC on a
classic ESP32; a 4.3" ESP32-S3 touch panel becomes the operator interface and
GRBL sender. FluidNC does not run on the S3, and the S3 cannot carry the full
machine pin budget — hence two boards.

**Nothing has been cut on this machine yet.** `steps_per_mm` is a placeholder
and the lift body is not bought.

### Added

- `firmware/config.yaml` — the complete FluidNC machine definition: axis,
  homing, soft limits, probe, `relay_spindle`, `macro0_pin`. No C++; the
  motion board runs an unmodified FluidNC binary (`298aabf`)
- `docs/UART-PROTOCOL.md` — HMI ↔ FluidNC command vocabulary, with `Link` as
  the single writer so the vocabulary stays exhaustive (`0995735`)
- `hmi/` — PlatformIO ESP32-S3 project for the ESP32-4827S043 panel
  - Increment 1: `Link` GRBL sender with one-command-in-flight window,
    `Wheel` PCNT quadrature decode with look-ahead clamp and
    cancel-on-reversal, `Buttons` on MCP23017 with short/long press (`e450644`)
  - Increment 2: Arduino_GFX RGB panel, GT911 touch, LVGL 8.4, main
    screen (`39c20b0`)
  - Increment 3: `Zero` two-touch probe sequencing and Z0 validity,
    `Store` named presets in NVS (`efb3d2c`)
- Rev H design set — four diagrams, BOM, design plan and Q&A (`e1b3230`),
  42 of 50 Q&A answers recorded (`9e16441`), Word design review
  document (`e80815e`)
- `docs/Router_Lift_Requirement_Specification_RevG.md` and the as-built
  wiring diagram (`d8e507a`)
- Mechanics Rev A — lift body selection and stepper drive design (`383e996`),
  workshop survey checklist (`e3b9cbf`)
- Lift body investigation: Sauter confirms the FML-P drives from the lower
  hex (`9189bf2`), full-size alternatives surveyed (`43da575`), the Wnew
  manual rules that lift out as shipped (`cf2d94d`), and the four candidates
  compared (`01c7596`, `f858ef2`)

### Changed

- **Soft limits are commissioning-only.** They live in `config.yaml` and are
  no longer operator-editable. Per-job ceilings come from presets and a
  teachable travel ceiling, both of which can only ever be *narrower* than the
  commissioned envelope
- **Rate switch is two positions (rough/fine)**, not the x1/x10/x100 bands
- **The HMI has no motion authority.** Homing, limits and probing are enforced
  by FluidNC. A bug in our firmware can produce a wrong depth, never an
  unsafe move
- Display board is the ESP32-4827S043 (RGB parallel), departing from spec
  Annex B.10's JC4827W543C/NV3041A — B.10 is wrong and is corrected in Rev H
- `README.md` rewritten for the two-board design (`1d0f235`)

### Removed

- Bespoke motion, homing, safety, relay and foot-switch firmware — all now
  native FluidNC behaviour. Reimplementing the homing state machine would be
  actively harmful
- ILI9488 TFT, XPT2046 touch controller, FastAccelStepper
- Function-board 4-bit ID. The MCP23017 remains in the HMI as the panel-button
  expander, but no longer identifies a board

### Deprecated

- The v1.x firmware moved to `legacy/`, kept as a porting reference and
  deliberately not built — no environment points at it (`01511d2`). The
  original root layout is recoverable at tag `v1.1.0-bespoke`

### Known issues

- `steps_per_mm: 800` and `MpgCfg::SCREW_LEAD_MM = 2.0` are placeholders
  assuming a 2 mm lead. Until measured against a dial indicator every depth is
  wrong by an unknown factor, invisibly — there is no stall detection to
  contradict a bad number
- The foot switch needs both press and release edges for dead-man behaviour.
  Whether `macro0_pin` fires on release is unverified; the mirrored-input plan
  in `firmware/README.md` is not yet proven
- Seven `config.yaml` items still to verify against the installed FluidNC
  release
- `docs/ARCHITECTURE.md` still describes the legacy module map
- HMI increments 4 (cycles) and 5 (fault log, diagnostics) not started

---

## [1.1.0-bespoke] - 2026-09-02

Tag only. The final state of the single-ESP32 firmware before the RevG pivot,
preserving the original root layout with `src/` and `include/`.

---

## [1.1.0] - 2026-05-25

### Added

- `Settings` module — NVS-persisted calibration under namespace `rl-cfg`, so
  motion, limit, relay and direction values survive a power cycle instead of
  resetting to defaults on boot. Writes are debounced 2 s to reduce NVS
  wear on rapid wheel turns (`ef13b68`)
- `docs/BENCH-TEST.md` — staged bring-up plan, each step passing before the
  next piece of hardware is fitted
- `docs/SCHEMATIC.svg` — wiring schematic (`20e6411`)

### Fixed

- First clean compile of the v1.0 firmware (`dd7aca4`)

---

## [1.0.1] - 2026-05-25

### Fixed

- Dir-invert calibration row read and wrote the motor-enable flag instead of
  the direction-inversion flag. Adds `MotorControl::dirInverted()` and uses it
  in `Menu` and `Display` (`307f81f`)

---

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
