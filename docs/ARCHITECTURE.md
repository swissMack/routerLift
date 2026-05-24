# Architecture

## Module map

```
main.cpp ──┬── Safety       (fault state, hardware watchdog)
           ├── IOExpander   (MCP23017 abstraction)
           │     ├── Endstops, brass stamp, foot switch
           │     ├── Function board ID (4 bits)
           │     └── Rate switch (3 positions)
           ├── MotorControl (FastAccelStepper wrapper, mm-based, soft limits)
           ├── MPG          (manual pulse generator, velocity scaling)
           ├── RateSwitch   (x1 / x10 / x100 hardware switch)
           ├── Touch        (XPT2046 + rectangle hit-testing)
           ├── Homing       (two-stage seek)
           ├── Zeroing      (brass-stamp tool-length sensor)
           ├── Presets      (NVS, 6 slots)
           ├── Relay        (SSR + startup delay)
           ├── FootSwitch   (debounced via MCP23017)
           ├── FunctionBoard (boot-time board identity)
           ├── Menu         (touch-driven screen state machine)
           └── Display      (TFT_eSPI sprite, 8-bit colour)
```

## State machine

Top-level `AppState` in `main.cpp`:

```
BOOT ─→ HOMING ─→ IDLE
                   │
                   ├─→ PLUNGE       (foot switch pressed, relay ready)
                   ├─→ ZEROING      (brass-stamp routine running)
                   └─→ FAULT        (any module reported a fault)

PLUNGE      ─→ RETURN_PARK (foot switch released)
RETURN_PARK ─→ IDLE        (motor reached park)
ZEROING     ─→ IDLE        (zeroing complete or failed)
FAULT       ─→ IDLE        (user acknowledged)
```

Sub-state machines live inside `Homing` and `Zeroing`, each running a
two-stage seek (fast then slow re-approach for accuracy).

## Safety architecture

Three independent barriers, all converging on `Safety::trigger()`:

1. **Soft limits in `MotorControl::moveToMm()`.** Every motion request
   passes through this single function, which rejects out-of-range targets
   before they reach the stepper driver. No caller can bypass it.
2. **Endstop polling in `main::checkEndstops()`.** Outside of Homing and
   Zeroing (which expect endstop triggers), any endstop activation is a
   fault. The fault handler immediately calls `Motor.emergencyStop()` and
   `Relay.turnOff()`.
3. **Hardware watchdog (`esp_task_wdt`).** A 5-second window. If
   `Guard.update()` doesn't kick the watchdog (because the main loop is
   stuck), the ESP32 reboots cleanly with the relay defaulting to OFF.

All three converge on `SafetyMon::trigger()` which:
- Sets the global fault code (first fault wins, no override)
- Calls `Motor.emergencyStop()` (immediate halt + driver disable)
- Calls `Relay.turnOff()` (router power off)
- Forces the UI into `FAULT_VIEW` until the user acknowledges

## Input model

| Input | Used for | Notes |
| --- | --- | --- |
| MPG (rotary) | Jogging on main, value editing in calibration | 100 PPR full-quad |
| Rate switch | Selects MPG step band (x1/x10/x100) | Hardware, polled |
| Touch panel | All menu navigation, button taps | XPT2046, polled |
| Foot switch | Plunge to target / return to park | MCP-routed, debounced |
| Endstops | Homing trigger + safety | Active-LOW NPN |
| Brass stamp | Tool zeroing trigger | Active-LOW NPN |
| Board ID jumpers | Boot-time function board detection | 4 bits |

The MPG never opens a menu and the touch panel never jogs the lift.
This separation is deliberate: it means accidental touch can't change
the cutting position, and accidental MPG rotation can't accidentally
trigger a menu action.

## Step-size computation

```
effective_step_mm = RateSwitch.baseStepMm() * velocity_scale

where:
  RateSwitch.baseStepMm():
    x1   → 0.001 mm
    x10  → 0.010 mm
    x100 → 0.100 mm

  velocity_scale ∈ [1.0, 10.0], a smoothed function of MPG pulses/second:
    pps ≤  5  → 1.0
    pps ≥ 80  → 10.0
    in between → linear interpolation
```

At full sprint with `x100`, you get 1.0 mm per pulse — 10 mm per full
wheel turn. At dead slow on `x1`, you get 1 µm per pulse for fine
tuning. The result feels like a Bridgeport handwheel with a multiplier.

## Display rendering

Each frame is drawn to a `TFT_eSprite` (8-bit colour) and pushed in one
SPI burst. This gives flicker-free updates at 20 Hz with plenty of CPU
left for everything else.

Touch coordinates are mapped from the XPT2046's 12-bit ADC space to the
480×320 pixel coordinate system using calibration constants in
`Touch.cpp` — adjust these if hit points are off-target on your panel.

## Why this architecture

The system has three categories of work, each with different timing
requirements:

| Work | Latency need | Owner |
| --- | --- | --- |
| Step generation | Microseconds | FastAccelStepper (hardware timer) |
| Counting MPG pulses | None — hardware | ESP32 PCNT peripheral |
| Servicing UI, sensors, state machine | ~50 ms | Main loop |

Keeping these layered means the main loop can be unhurried (and easy to
read) without compromising motion smoothness or losing pulses. The
modules above the main loop are deliberately stateless about timing —
they expose request/query APIs that the loop polls at its own rate.
