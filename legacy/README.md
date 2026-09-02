# Legacy firmware — pre-RevG bespoke design

This is the **v1.x single-ESP32 Arduino firmware**, superseded by the RevG split
architecture. It is kept in the tree as a porting reference for UI layout, menu
structure, and calibration logic. **It is not built** — the root `platformio.ini`
has no environment pointing here.

The original tree layout (with `src/` and `include/` at the repo root) is preserved
at tag **`v1.1.0-bespoke`**.

## Why it was retired

`docs/Router_Lift_Requirement_Specification_RevG.md` closes the controller-platform
open item with a split design: **FluidNC on a standard ESP32** for motion, and a
**4.3" ESP32-S3 touch board** as the operator panel over UART. FluidNC does not run
on the ESP32-S3, and the S3 board cannot carry the full machine pin budget — hence
two controllers. This firmware assumed one.

The hardware assumptions are also gone: no ILI9488 TFT, no XPT2046 touch controller,
and **no MCP23017 expander** in the new design.

## Where each module's logic now lives

| Legacy module | Destination |
| --- | --- |
| `MotorControl`, `Homing`, `Safety` (limits/faults) | FluidNC `config.yaml` — native axes, homing, soft limits |
| `Zeroing` (brass stamp) | FluidNC probe (`G38.2`), driven by the HMI |
| `Relay` | FluidNC `relay_spindle` (`M3`/`M5`) |
| `FootSwitch` | FluidNC `macro0_pin` + `$Macro0` |
| `RateSwitch` | HMI — rough/fine selector per ELE-09 (2 positions, not the old x1/x10/x100 bands) |
| `MPG` | HMI — ESP32-S3 PCNT quadrature |
| `Menu`, `Display`, `Touch` | HMI — LVGL screens |
| `Presets`, `Settings` | HMI — NVS on the S3, **except** `softMinMm`/`softMaxMm` (see below) |
| `IOExpander`, `FunctionBoard` | **Dropped.** No MCP23017 in the new design |

## Two things that deliberately do NOT get ported

**1. `Homing.cpp`'s state machine and `main::checkEndstops()`.** The four-state
SEEK_FAST → BACKOFF → SEEK_SLOW → DONE sequence, and the endstop polling that had to
suppress faults while homing or zeroing was active, are both native FluidNC behaviour.
The `homing:` block does the two-stage approach, and FluidNC already treats a limit hit
during a homing cycle as expected rather than a fault. Reimplementing this would be
actively harmful.

**2. The soft-limit calibration rows.** `Settings.cpp` persists `softMinMm`/`softMaxMm`
to NVS and `Menu.cpp` exposes them as editable rows. In the new design soft limits are
**commissioning-only**, set in `config.yaml` from `max_travel_mm` and the home reference.
An operator must not be able to widen their own envelope from the panel. The affordance
is replaced, not removed: per-job ceilings come from presets and a teachable travel
ceiling, both of which can only ever be *narrower* than the commissioned envelope.

## Still worth reading before writing the HMI

- `src/Menu.cpp` — the 12-screen structure and navigation model
- `src/Display.cpp` — per-screen render methods and status-bar vocabulary
- `src/Settings.cpp` — the 2 s debounced NVS flush, which **is** carried across
- `include/config.h` — mechanical defaults, though note `steps_per_rev` and
  `spindlePitchMm` here (1000 / 4 mm) are superseded by the spec's as-built values
  (1600 pulses/rev at 1/8 microstepping, T8 2 mm lead → 800 steps/mm)
