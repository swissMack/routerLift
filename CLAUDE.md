# Project: routerLift — handoff for Claude Code

> This section was added at end of a previous session that did the v1.0.0
> firmware design via MCP-only file editing. Below it, the original
> context-mode routing rules apply unchanged.

## What this repo is

ESP32-based open-firmware automated router lift. Built with PlatformIO +
Arduino framework. Drives a DM542 stepper + ball-screw spindle, jogged by
a CNC-style manual pulse generator (MPG), navigated by touch on a 3.5"
ILI9488 TFT. Designed to replace a FXBB FräsLift V3 (original docs at
`docs/reference/FXBB-original/`).

Repo: `git@github.com:swissMack/routerLift.git` (private).
Tag at handoff: `v1.0.0` on `origin/main`.

## State as of handoff

| What | Where |
| --- | --- |
| v1.0.0 baseline (29 source files, full docs) | Tagged + pushed to `origin/main` |
| v1.0.1 fix patches | **Written locally, NOT yet committed.** See below |
| Compile-test result | **Never run** — previous session's sandbox could not reach `registry.platformio.org` |

The v1.0.1 patches fix a leftover bug: in the calibration UI, the Dir-invert
toggle was reading/writing the motor-enable flag instead of the direction-
inversion flag. Three files modified: `src/MotorControl.h` adds a
`dirInverted()` getter; `src/Menu.cpp` and `src/Display.cpp` use that
getter instead of `isEnabled()`.

**First actions when you start:**

```sh
# 1. Commit the pending fix and run a real compile
git add src/MotorControl.h src/Menu.cpp src/Display.cpp
git commit -m "fix: Dir invert toggle uses dirInverted() not isEnabled()"
git push origin main
git tag -a v1.0.1 -m "Patch: dir-invert toggle"
git push --tags

# 2. First real compile of the codebase
pio run
```

If `pio run` succeeds, proceed to Step 2 (NVS persistence). If it fails,
match symptoms to "Open compile risks" below and patch the smallest set
of files needed.

## Pending work (in priority order)

### Step 2 — NVS persistence for calibration values

Currently only presets and the brass-stamp offset survive power cycles.
Motion/limit/relay/direction settings are in-RAM only and reset on boot.

- **New module:** `src/Settings.h/cpp` with global `extern Settings Config;`
- **NVS namespace:** `"rl-cfg"` (matching the `"rl-presets"` convention)
- **Fields to persist:** `stepsPerRev`, `spindlePitchMm`, `dirInverted`,
  `maxSpeedMmS`, `accelMmS2`, `softMinMm`, `softMaxMm`, `stampOffsetMm`,
  `relayStartupDelayMs`
- **API:**
  - `Config.begin()` reads from NVS, applies defaults if missing
  - `Config.scheduleSave()` marks dirty; called from every menu edit
  - `Config.update()` in `loop()`: if dirty AND >2 s since last edit, flush to NVS
    (debounced to reduce NVS wear on rapid wheel turns)
- **Integration points:**
  - `main.cpp` `setup()`: call `Config.begin()` and apply values **before**
    the existing `Motor.set*` default calls
  - `Menu.cpp` calibration handlers: call `Config.scheduleSave()` after
    every `Motor.set*`, `Zero.setStampOffsetMm`, `RouterRelay.setStartupDelayMs`
  - `main.cpp` `loop()`: add `Config.update();` next to the other always-on services
- **Acceptance test:** change a calibration value via touch UI, wait 3 s,
  power-cycle the ESP32. Value persists.
- **Bump version:** `v1.1.0` (minor — additive feature)

### Step 3 — Wiring schematic

- **Output file:** `docs/SCHEMATIC.svg` (rendered SVG, hand-drawn; no KiCad)
- **Must show clearly:**
  - ESP32 pinout (all pins used per `docs/HARDWARE.md` table)
  - MCP23017 on I²C with full Port A and Port B map
  - DM542 stepper driver wiring (PUL+, DIR+, ENA+, motor coils)
  - MPG via 2× PC817 opto-isolators (preferred — `MPG::SIGNALS_INVERTED = true` is already wired for this)
  - 3-position rate switch: common to GND, throws to MCP B4/B5/B6
  - TFT + XPT2046 sharing SPI bus, different CS lines
  - SSR for router with snubber if needed
  - NPN endstops with 24 V common
  - Foot switch (momentary, normally open, to MCP A.3)
- **Power architecture box:** 24 V PSU → buck → 5 V → buck → 3.3 V; star-ground near PSU
- Cross-reference `docs/HARDWARE.md` for pin/wiring tables — schematic is the visual companion

### Step 4 — Bench-test plan

- **Output file:** `docs/BENCH-TEST.md`
- Each step must pass before adding the next piece of physical hardware:
  1. **Bare ESP32** — no MCP, no motor, no router. Verify boot, serial banner at 115200, expected `"MCP23017 not found - degraded mode"` log.
  2. **Add MCP23017** — verify board-ID detection (expect "Function board: Router Lift" if jumpers set, otherwise "Unknown function board"), endstop reads via temporary serial-debug print loop.
  3. **Add display + touch** — verify 20 Hz rendering, tap calibration rows, adjust the touch ADC calibration constants in `Touch.cpp` if hit points are off.
  4. **Add MPG via opto-isolators** — verify pulse counting (one full wheel turn = 100 pulses), rate switch reads (each position labelled correctly on status bar), velocity scaling visible in main-screen `mm/pulse` readout.
  5. **Add stepper driver only (motor NOT yet mounted on the lift)** — verify motion, soft-limit rejection (try moving past `softMax` via serial debug command), endstop trigger forces a `FAULT` screen.
  6. **Mount motor on the lift mechanics** — verify two-stage homing, brass-stamp zeroing (stamp offset calibrated with calipers first), jog feel across all three rate bands.
  7. **Add SSR with the router unplugged from mains** — verify relay click on `POWER ON` tap, `isReady()` timing matches `RELAY_STARTUP_DELAY_MS` (status bar shows `WARMUP` → `ON`).
  8. **Plug router in at lowest speed setting only, no bit in the collet** — verify foot-switch plunge cycle (target → park).
  9. **Production cuts** only after all above pass and with a fresh emergency-stop button within arm's reach.

## Architectural decisions to preserve

Don't relitigate these — they're the result of multi-turn design discussion:

- **One chokepoint for motion safety.** Every motion request goes through
  `MotorControl::moveToMm()`, which enforces soft limits before any step
  reaches the driver. Never bypass it. New code paths must call it.
- **Three converging fault triggers.** Soft-limit violation in
  `MotorControl`, endstop polling in `main::checkEndstops()`, hardware
  watchdog in `SafetyMon`. All call `Safety::trigger()` which e-stops the
  motor and turns the relay off. First fault wins (no override).
- **MPG ↔ touch input separation.** MPG only jogs and edits values; touch
  only navigates menus. Deliberate: accidental touch can't move the
  cutter, accidental wheel-spin can't trigger a menu action.
- **Foot-switch plunge gated on `Relay.isReady()`.** Prevents plunging
  before the spindle reaches full speed. Do not remove this gate.
- **MPG signals are inverted at the level shifter** (PC817 opto-isolator
  assumption). `MPG::SIGNALS_INVERTED = true` is correct for that. If the
  user moves to a 74HCT14 with two inverters per channel, flip it to false.
- **Step size = `RateSwitch.baseStepMm() × velocity_scale`** where
  velocity_scale ∈ [1.0, 10.0]. Don't change the curve without discussion.
- **Function board ID via MCP23017 Port B0..B3** (4-bit jumpers). The
  display unit is generic; the function board identifies itself at boot.
  Future boards (dust collection, miter stop) reuse the same display.

## Open compile risks

The previous session never compiled the code. Apply only if `pio run` actually complains:

| Symptom | Fix |
| --- | --- |
| `XPT2046_Touchscreen` hangs in `touched()` (display goes dark / loop blocked) | If T_IRQ is unwired, use `XPT2046_Touchscreen ts(Pins::TOUCH_CS)` (no IRQ arg) in `src/Touch.cpp` |
| `'forceStop' is not a member of 'FastAccelStepper'` | Replace `stepper->forceStop()` with `stepper->forceStopAndNewPosition(stepper->getCurrentPosition())` in `src/MotorControl.cpp::emergencyStop()` |
| `esp_task_wdt_init` signature mismatch | Arduino-ESP32 core 3.x uses an `esp_task_wdt_config_t` struct. Wrap the call in `#if ESP_ARDUINO_VERSION_MAJOR >= 3` |
| `createSprite` returns false | RAM exhausted. Drop to `spr.setColorDepth(4);` in `Display::begin()`, or split into two half-height sprites and push them separately |

## Working conventions for this project

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`)
- One logical change per commit; safety-critical changes bench-tested first
- Build before pushing (`pio run`)
- User preferences: concise plain-language responses; show plan before changes; ask clarifying questions before destructive operations
- Standing rule: never delete or overwrite files without explicit user approval

## Key file references

- `include/config.h` — pins, mechanical defaults, MPG and UI constants (start here)
- `src/MotorControl.{h,cpp}` — motion API + soft limits (safety-critical)
- `src/Safety.{h,cpp}` — fault state machine + watchdog
- `src/MPG.{h,cpp}` — pulse decode + velocity scaling
- `src/RateSwitch.{h,cpp}` — x1/x10/x100 band selector
- `src/Touch.{h,cpp}` — XPT2046 with rectangular hit-testing
- `src/Menu.{h,cpp}` + `src/Display.{h,cpp}` — UI layer; layout constants must agree
- `src/main.cpp` — top-level state machine
- `docs/HARDWARE.md` — BOM, pin map, level-shifter circuits
- `docs/ARCHITECTURE.md` — module map and design rationale
- `docs/UX.md` — screen-by-screen reference
- `docs/reference/FXBB-original/` — original V3 documentation (PCB, schematic, software manual PDFs)

---

# context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
