# Bench-test plan

Incremental bring-up. Each stage must pass before adding the next piece of physical hardware. Do not skip ahead — every stage doubles as a fault-localisation tool for the next one. If stage N fails, the bug is in what stage N added, not what came before.

## Safety contract (applies to every stage)

- The router stays **unplugged from mains** until stage 7, with **no bit in the collet** until stage 8.
- A separately-wired E-stop on the 24 V rail (cuts stepper + relay simultaneously) must be within arm's reach from stage 5 onward. The firmware watchdog and soft-limit/endstop fault paths are software safeguards — not substitutes for a hardware cutoff.
- Keep `softMin` / `softMax` tight (e.g. ±5 mm around park) until stage 6 mechanics are validated. Plenty of time to widen them after.
- Never bypass `MotorControl::moveToMm()` in any test code added during bring-up; that single function is the soft-limit chokepoint (see `docs/ARCHITECTURE.md`).

## Tools

- USB cable + serial monitor at **115200 baud** (`pio device monitor` works).
- Multimeter for continuity / voltage checks before powering anything new.
- Logic analyser or scope (optional but useful at stages 4 and 5 for MPG / step pulse inspection).
- Digital calipers for stage 6 (brass-stamp offset calibration).

## Reading the firmware status

The boot banner is the first thing you should see:

```
=== RouterLift v1.1.0 ===
```

If the banner appears, the ESP32 booted and `Serial.begin(115200)` ran. Subsequent log lines tell you which modules failed `begin()`:

- `MCP23017 not found - degraded mode` — I²C did not detect the expander at `0x20`
- `Unknown function board (raw id=N)` — MCP responded but the 4-bit board-ID jumpers don't match any `BoardId` enum value
- `Function board: Router Lift` — full I/O working
- `MPG init failed`, `Display init failed`, `Touch init failed` — module-specific begin failures
- `Plunge ignored: spindle not at speed` / `Plunge ignored: router relay off` — runtime guard messages once stage 8 is reached

## Stage 1 — Bare ESP32

**Hardware**
- ESP32 DevKit V1 only. No MCP, no display, no stepper driver, no router. Powered from USB.

**Procedure**
1. Flash the firmware: `pio run -t upload`.
2. Open the serial monitor at 115200 baud.
3. Power-cycle.

**Pass criteria**
- Boot banner appears within ~1 s.
- Exactly one `MCP23017 not found - degraded mode` line is logged (expected — there is no MCP yet).
- No watchdog reboots (banner does not re-appear every 5 s).
- Top/bottom endstop messages are absent (no I/O expander to read them).

**If it fails**
- No banner → check USB power, board selection in `platformio.ini` (`board = esp32dev`), and that the serial monitor is at 115200.
- Reboot loop → most likely cause is the watchdog (`SafetyMon::begin()` adds the main task; if anything in `setup()` blocks > 5 s the WDT fires). Re-flash with `-DCORE_DEBUG_LEVEL=4` to get verbose ESP-IDF logs.

## Stage 2 — Add MCP23017

**Hardware added**
- MCP23017 wired to GPIO21 (SDA) / GPIO22 (SCL) with 4.7 kΩ pull-ups to 3.3 V. Address jumpers strapped for `0x20` (A0/A1/A2 to GND).
- Set the 4-bit function-board ID jumpers on Port B0..B3 to match `BoardId::ROUTER_LIFT` (= 1, so B0 to GND, B1..B3 floating high via internal pull-ups). Cross-reference `include/config.h::BoardId`.
- Endstop sensors and foot switch can be wired (per `docs/HARDWARE.md` MCP map) but do not need to be triggered yet.

**Procedure**
1. Power-cycle.
2. Watch the boot banner.
3. With the serial monitor open, manually trigger each endstop (wave a metal object past the inductive face) and the foot switch. Add a temporary debug print in `loop()` if you want to see live values:
   ```cpp
   static uint32_t lastDbg = 0;
   if (millis() - lastDbg > 250) {
       lastDbg = millis();
       Serial.printf("EB=%d ET=%d STAMP=%d FOOT=%d RATE=%u\n",
           IO.readEndstopBottom(), IO.readEndstopTop(),
           IO.readStampPickup(), IO.readFootSwitch(),
           IO.readRateMultiplier());
   }
   ```
   Remove this print before stage 5.

**Pass criteria**
- `Function board: Router Lift` appears (not `Unknown function board`).
- `MCP23017 not found - degraded mode` does **not** appear.
- Endstop / stamp / foot lines toggle 0↔1 on physical activation, with no chatter when idle.
- `RATE=` matches the rotary switch position (1, 10, 100; reads `0` if the wiper is between positions or the switch is unwired).

**If it fails**
- `MCP23017 not found` → check I²C wiring, pull-up presence, and that the I²C bus address is `0x20`. `pio device monitor` plus an I²C scanner sketch is a quick triage.
- `Unknown function board` → re-check the B0..B3 jumpers against `BoardId` in `include/config.h`. Each bit is active-LOW (jumper to GND = 1).
- Endstops chatter → the NPN open-collector lines need either an external pull-up to 3.3 V or interface optocouplers; do not rely on MCP internal pull-ups alone with long cable runs.

## Stage 3 — Add display + touch

**Hardware added**
- 3.5" ILI9488 SPI TFT with XPT2046 touch. SPI pins per the `platformio.ini` `build_flags` (SCK 18, MOSI 23, MISO 19, TFT_CS 15, DC 2, RST 4). Touch CS on GPIO 5, touch IRQ on GPIO 17 (polled in v1.1.0; the IRQ pin is wired but unused).
- Backlight to 5 V via a series resistor or driven from the TFT module's onboard LED pin per its datasheet.

**Procedure**
1. Power-cycle.
2. Confirm the main screen renders.
3. Tap the `MENU` bottom-bar button → tap `Calibration` → walk through `Motor`, `Motion`, `Limits`, `Sensors` rows. Confirm each tap registers and that selected rows highlight.
4. If hit points are off (tap registers a row above/below your finger), adjust `TS_X_MIN / TS_X_MAX / TS_Y_MIN / TS_Y_MAX` in `src/Touch.cpp` and re-flash. Default values fit a common panel but every batch is slightly different.

**Pass criteria**
- No `Display init failed` / `Touch init failed` lines.
- Status bar updates at roughly 20 Hz (counted by eye — `mm/pulse` readout updates smoothly).
- Tap accuracy across all corners of the 480×320 screen is within ~10 px after calibration.
- Returning to the main screen via the `Back` arrow works from every menu depth.

**If it fails**
- Display shows white/static → SPI wiring; re-check MISO is on 19, MOSI 23, SCK 18, and that `User_Setup.h` is **not** loaded (we use `USER_SETUP_LOADED=1` + build flags exclusively).
- Touch never registers → confirm `TOUCH_CS` on GPIO 5 and that the panel's touch controller shares the SPI bus correctly. The `TOUCH_CS pin not defined` warning during build is harmless (TFT_eSPI's own touch helpers are unused; we drive XPT2046 directly via `XPT2046_Touchscreen`).
- Touch hangs the UI on power-up with T_IRQ unwired → change `XPT2046_Touchscreen ts(Pins::TOUCH_CS, Pins::TOUCH_IRQ)` in `src/Touch.cpp` to `XPT2046_Touchscreen ts(Pins::TOUCH_CS)` (no IRQ arg).

## Stage 4 — Add MPG via opto-isolators

**Hardware added**
- 100 PPR 5 V MPG, level-shifted to ESP32 GPIO 32 (A) and GPIO 33 (B) via 2× PC817 opto-isolators per `docs/HARDWARE.md`. With opto-isolators the signal is inverted; `MPG::SIGNALS_INVERTED = true` in `include/config.h` is already wired for this.
- 3-position SP3T rate switch on MCP B4/B5/B6 if not already done in stage 2.

**Procedure**
1. Open the main screen.
2. Turn the wheel one full revolution clockwise slowly. The `mm/pulse` readout should multiply by the current band:
   - x1 → 0.001 mm/pulse base, ~0.001 mm/pulse at slow rotation
   - x10 → 0.010 mm/pulse base
   - x100 → 0.100 mm/pulse base
3. Spin briskly. Velocity scaling should kick in — `mm/pulse` rises toward `10×` the base step.
4. Reverse direction. Sign should flip without losing counts (the PCNT peripheral handles direction).
5. Cycle the rate switch through all three positions. The status bar label should change `x1` ↔ `x10` ↔ `x100`.

**Pass criteria**
- One full wheel turn = 100 net pulses on x1 base (verify by zeroing position and turning exactly one revolution in `Set Target` mode — target should change by 0.1 mm).
- Brisk rotation produces visibly larger per-pulse steps (gas-pedal feel).
- Idle wheel produces zero spurious pulses for >10 s.
- Reversing direction does not lose or gain counts (turn 100 pulses CW, then 100 pulses CCW; target returns to start within ±1 pulse).
- Rate switch reads correctly in all three positions; intermediate (between-detent) position reads `0` and the band does not change.

**If it fails**
- Pulses appear in the wrong direction → flip `MPG::SIGNALS_INVERTED`.
- Lost counts at high spin rate → either the opto LED current is too low (drop the series resistor from 330 Ω to 220 Ω) or the opto transistor pull-up is too high (drop the 10 kΩ to 4.7 kΩ). The PCNT peripheral itself does not lose counts; the analogue level shifter does.
- Rate switch reads `0` always → check that the switch common is wired to GND (not 3.3 V) and that the throws land on B4/B5/B6.

## Stage 5 — Add stepper driver (motor not yet mounted)

**Hardware added**
- DM542 stepper driver. PUL+/PUL- to GPIO 25 + GND. DIR+/DIR- to GPIO 26 + GND. ENA+/ENA- to GPIO 27 + GND. Driver microsteps set to give **1000 steps/rev** (DM542 SW dip table: 1000 = SW5/6/7/8 OFF/ON/ON/OFF).
- Stepper motor wired to A+/A-/B+/B- but **not yet bolted into the lift** — let it sit on the bench with the shaft free to spin. This isolates "motor moves" from "lift moves correctly".
- 24 V supply to driver power inputs. **Do not power the lift mechanics yet.**

**Procedure**
1. Tighten the soft limits to a narrow window for testing: open `MENU > Calibration > Limits` and set `softMin = -2 mm`, `softMax = 2 mm` (with the wheel; values persist via NVS after 2 s).
2. Power-cycle. The motor should energise briefly when `Motor.begin()` runs (audible click / holding torque).
3. On the main screen, tap the target field. Use the wheel to dial in `+1.0` mm. Tap `GO` (or whatever the explicit "move to target" path is in your build).
4. The motor should rotate smoothly to the new position. Reverse with `-1.0` mm.
5. **Soft-limit test:** dial a target of `+5.0` mm (outside `softMax`). The `moveToMm()` call should be rejected with no motion. The target field will jump back to a clamped value or the move will simply not start. No fault is generated for a rejected move — `moveToMm()` returns `false`.
6. **Endstop fault test:** physically wave a metal object past one of the inductive sensors (or short the sensor input to GND). The status should switch to a `FAULT` screen with `ENDSTOP_HIT` and the motor should be force-disabled. Acknowledge the fault via the UI to return to `IDLE`.

> **Note.** v1.1.0 does not yet ship a serial debug command parser, so the "command-line soft-limit test" mentioned in the handoff has to be done via the touch UI as described above. If you want a hard "try to move 1000 mm" stress test, add a one-shot test path behind a compile flag and remove it afterward.

**Pass criteria**
- Motion is smooth (no audible chatter, no missed steps when reversing direction at speed).
- A 10 mm round-trip ends at the same indicated position (within ±1 step).
- Soft-limit-violating targets are rejected silently (no motion, no fault — `moveToMm()` returned false).
- Endstop trigger forces a `FAULT_VIEW` screen and disables the driver. The relay (when wired in stage 7) also turns off as part of the fault path.

**If it fails**
- Motor stalls / chatters → speed/accel may be too high for the current microstep + voltage combination. Open `MENU > Calibration > Motion` and halve `Max speed` and `Accel`. NVS will remember the new values after 2 s idle.
- Reverses to wrong direction → `MENU > Calibration > Motor` → toggle `Dir invert`. (This is the v1.0.1 fix point — confirm the toggle now writes/reads the direction-invert flag, not the enable flag.)
- Position drift on round-trip → microstep mismatch between driver and `stepsPerRev` config. Re-check DM542 dip switches; the firmware default is 1000.

## Stage 6 — Mount motor on the lift

**Hardware added**
- Motor bolted to the lift body. Ball-screw spindle coupled to motor shaft via 698 RS bearing. Top + bottom inductive endstops wired and aimed at the moving carriage.
- Brass-stamp pickup wired but its position-offset will be calibrated in this stage.

**Procedure**
1. With soft limits still tight (from stage 5), hand-crank the lift to roughly mid-travel before powering on. This prevents the first homing pass from slamming into an endstop while you're testing.
2. Tap `MENU > Home`. The Homing module runs a two-stage seek: fast travel toward the bottom endstop, back off, slow re-approach for accuracy.
3. After homing completes, widen the soft limits to the real mechanical range via `MENU > Calibration > Limits`.
4. **Brass-stamp calibration:** measure the stamp-trigger-to-table distance with calipers (depress the stamp until the inductive sensor would trigger, measure to the table surface). Enter that value in `MENU > Calibration > Sensors > Stamp offset`.
5. Run `MENU > Zero` with the stamp positioned correctly. The carriage should descend slowly, trip on the stamp pickup, and report position = `stampOffsetMm`.
6. Test jog feel on all three rate bands:
   - x1: a single click of the wheel should produce a visibly small (~0.001 mm) movement that you can confirm only by watching the position readout.
   - x10: clearly visible per-click motion.
   - x100: rapid travel; the gas-pedal scaling should give ~1 mm per pulse when spun briskly.

**Pass criteria**
- Two-stage homing converges to a repeatable position (re-home three times in a row, observe the indicated zero stays within ±1 step).
- Zeroing places the carriage exactly `stampOffsetMm` above the table — confirm with a precision spacer or calipers.
- Jog feel is responsive across all three bands with no missed steps.
- No `HOMING_TIMEOUT` or `ZEROING_TIMEOUT` faults under nominal operation.

**If it fails**
- Homing times out → `Mech::DEFAULT_HOMING_SPEED_MM_S` may be too low for `Safety::HOMING_TIMEOUT_MS`, or the endstop is not in the travel path. Re-aim the inductive sensor and re-check `HOMING_TIMEOUT_MS` budget.
- Zeroing repeatability poor → stamp spring may be too stiff or the inductive sensor too far from the stamp face. Aim for the sensor to trigger within the first 0.2 mm of stamp deflection.
- Carriage hunts (oscillates) at end-of-travel → motion accel too low; let the firmware decelerate more gracefully by *raising* `Accel` slightly so the planned stop is reached before the soft-limit clamp kicks in.

## Stage 7 — Add SSR with router unplugged from mains

**Hardware added**
- Solid-state relay control input on GPIO 16. The router stays **unplugged from mains** — we are only verifying the relay clicks and the firmware enforces the startup delay.

**Procedure**
1. Tap `POWER ON` on the main screen. The SSR should click (audible / LED indicator).
2. Watch the status bar: it should show `WARMUP` for the duration of `RELAY_STARTUP_DELAY_MS` (default 2500 ms), then transition to `ON`.
3. Tap `POWER OFF`. SSR clicks off. Status bar returns to `off`.
4. **Plunge-gate test:** with the relay `WARMUP` (still in startup-delay window), press the foot switch. The serial log should print `Plunge ignored: spindle not at speed` and the carriage must **not** move.
5. With the relay fully `ON` (after the delay), press the foot switch. Confirm the plunge cycle starts (it will move toward the current target — the lift may move on the bench even without a router cutting, which is fine for this stage).

**Pass criteria**
- SSR responds to `POWER ON` / `POWER OFF` taps with no delay.
- `WARMUP` → `ON` transition timing matches `RELAY_STARTUP_DELAY_MS` (verify with a stopwatch — within ±100 ms is fine).
- Foot-switch plunge during `WARMUP` is correctly rejected (logged and no motion).
- Foot-switch plunge during `ON` starts a `PLUNGE` cycle; releasing the foot returns the lift to `Mech::DEFAULT_PARK_MM`.

**If it fails**
- SSR doesn't click → check that the SSR control input is rated for 3.3 V logic (most are 3-32 V DC, but verify). Check that GPIO 16 is wired through any required snubber/series resistor per the SSR datasheet.
- `WARMUP` never transitions to `ON` → check the `startupDelayMs_` persisted value via `MENU > Calibration > Sensors > Relay delay`. If it was accidentally set to a huge value, reset to 2500 ms.
- Plunge ignored even when `ON` → `Foot.justPressed()` is edge-triggered, not level. The press must be released and re-pressed cleanly; debounce is `Safety::BUTTON_DEBOUNCE_MS = 25 ms`.

## Stage 8 — Plug router in at lowest speed setting, no bit in collet

**Hardware added**
- Router plugged into the SSR-switched mains outlet. **Speed selector at its lowest setting.** **No bit in the collet.**

**Procedure**
1. Tap `POWER ON`. Confirm the router spools up to its (low) commanded speed during `WARMUP`.
2. After the relay reaches `ON`, set a small plunge target (e.g. 2 mm below park) via `MENU > Set Target`.
3. Press and hold the foot switch. The carriage should plunge to the target.
4. Release the foot switch. The carriage should return to `Mech::DEFAULT_PARK_MM`.
5. Repeat the plunge cycle 5–10 times to confirm reliability.
6. Tap `POWER OFF`. The SSR cuts; the router winds down.

**Pass criteria**
- Plunge starts only after `WARMUP → ON` (still rejected during warmup).
- Plunge and return motion is smooth at the configured `Max speed` / `Accel`.
- Releasing the foot switch always returns to park, including releases mid-plunge.
- No fault triggers occur during normal cycling.
- Emergency stop (the hardware 24 V cutoff from the safety contract): hit it during a plunge — the motor must stop instantly, the relay must cut, and the firmware should reboot cleanly with the relay defaulting to OFF on the next boot.

**If it fails**
- Router doesn't spool up during `WARMUP` → mechanical issue with the router or the SSR isn't actually passing mains current. Verify with the router selector on its lowest setting and double-check SSR load wiring.
- Plunge feels jerky → the router's vibration is not the issue here (no bit, low speed). Re-check stepper Accel / Max speed. Stepper resonance at certain speeds is common with low microstepping; bump microsteps to 1600 or 3200 (and update `stepsPerRev` accordingly).
- Random faults during cycling → likely electrical noise from the router on the 24 V rail. Add a snubber across the SSR load contacts and confirm the logic ground is star-pointed at the PSU (per `docs/HARDWARE.md` Power architecture).

## Stage 9 — Production cuts

**Pre-conditions**
- All stages 1–8 pass cleanly and have been re-verified within the last week.
- The hardware E-stop has been tested mid-plunge in stage 8.
- A bit is in the collet, mounted to spec, and you have routed test material that you are willing to scrap.

**Procedure**
- First cut should be a single shallow pass (e.g. 1 mm depth) in scrap material at the router's normal operating speed.
- Cycle the lift 10× more on the same scrap to confirm repeatability.
- Only then move to production stock.

**Pass criteria**
- Cut depth is consistent across 10 cycles (within ±0.05 mm — limited by mechanical stack, not firmware).
- No watchdog reboots, no fault triggers, no missed steps over an extended cutting session.
- The E-stop, when hit, still cleanly cuts power and reboots with the relay OFF.

## After bench-testing

- Restore production soft limits if you tightened them for stage 5 (`MENU > Calibration > Limits`).
- Remove any temporary `Serial.printf` debug prints added during stages 2 / 4.
- Tag a release (`v1.2.0` or whatever the next bump is) recording "bench-validated against physical lift" in the message.
- File any hardware quirks discovered (sensor positions, calibration offsets, dip-switch settings) into `docs/HARDWARE.md` so the next person doesn't rediscover them.
