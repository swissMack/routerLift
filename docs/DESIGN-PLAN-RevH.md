# Pivot routerLift to the RevG split architecture

## Context

`docs/Router_Lift_Requirement_Specification_RevG.md` (committed as `d8e507a`) closes the
controller-platform open item with a **split architecture**: FluidNC on a standard ESP32 for
motion, and a 4.3" ESP32-S3 touch board as the operator panel over UART. FluidNC does not run
on the ESP32-S3, and the S3 board cannot carry the machine's full pin budget — hence two boards.

The repo currently holds a **bespoke single-ESP32 Arduino firmware** (29 files in `src/`,
`include/config.h`, `platformio.ini`) built around an ILI9488 TFT and an MCP23017 expander.
RevG supersedes that design wholesale. This plan retires it to `legacy/` and builds the two
new halves.

Decisions taken with the user this session (these are settled — do not relitigate):

| Decision | Choice |
|---|---|
| Old firmware | Move to `legacy/`, keep in tree as porting reference, not built |
| Display board | **ESP32-4827S043** (RGB parallel, ILI6485) — matches `docs/4.3inch_ESP32-4827S043.zip` |
| I/O split | Operator inputs on the S3; every safety-relevant input stays on FluidNC |
| UART protocol | GRBL/gcode — S3 acts as a GRBL sender, FluidNC stays stock |
| Soft limits | **Commissioning-only** in `config.yaml` — no longer operator-editable (see below) |
| Scope | Full pivot, both halves |

The board choice departs from spec Annex B.10, which records a JC4827W543C with an NV3041A QSPI
panel. The board in hand is the RGB parallel variant. **B.10 is wrong and must be corrected**
(see Phase 5). The I/O split also departs from B.10's "HMI only" rationale and needs ELE-11
reworded.

## Target layout

```
routerLift/
  firmware/          FluidNC config.yaml + macros + notes (no C++ — stock FluidNC binary)
  hmi/               PlatformIO ESP32-S3 project: LVGL UI + operator inputs + GRBL sender
  legacy/            the v1.x bespoke firmware, unbuilt, for reference
  docs/
```

---

## Phase 1 — Repo restructure

1. `git tag -a v1.1.0-bespoke -m "Final bespoke single-ESP32 firmware before RevG pivot"`
   so the working tree is recoverable by tag as well as by path.
2. `git mv src legacy/src`, `git mv include legacy/include`, `git mv platformio.ini legacy/platformio.ini`.
3. Add `legacy/README.md`: one paragraph stating this is the pre-RevG design, that it is not
   built by CI, and a table mapping each old module to where its logic now lives (below).
4. New root `platformio.ini` with a single `[env:hmi]` pointing at `hmi/`. `legacy/` is excluded
   from the build by simply not having an env.

**Where the old modules go** — this table belongs in `legacy/README.md`:

| Legacy module | Destination |
|---|---|
| `MotorControl`, `Homing`, `Safety` (limits/faults) | FluidNC `config.yaml` — native axes, homing, soft limits |
| `Zeroing` (brass stamp) | FluidNC probe (`G38.2`) driven by HMI |
| `Relay` | FluidNC `relay_spindle` (`M3`/`M5`) |
| `FootSwitch` | FluidNC `macro0_pin` + `$Macro0` |
| `RateSwitch` | HMI — rough/fine selector per ELE-09 (2 positions, not the old 3-band x1/x10/x100) |
| `MPG` | HMI — ESP32-S3 PCNT quadrature |
| `Menu`, `Display`, `Touch` | HMI — LVGL screens |
| `Presets`, `Settings` | HMI — NVS on the S3. **Except `softMinMm`/`softMaxMm`**, which become commissioning-only `config.yaml` values; their calibration rows are not ported |
| `IOExpander`, `FunctionBoard` | **Dropped.** No MCP23017 in the new design |

---

## Phase 2 — `firmware/config.yaml` (FluidNC)  ✅ WRITTEN (steps_per_mm provisional)

Stock FluidNC binary; all machine definition is config. Pin numbers come from
`docs/superseded-wiring_diagram.svg` (Annex B.9), with MPG A/B (GPIO 34/35) now freed because the handwheel
moved to the S3.

| Signal | GPIO | Notes |
|---|---|---|
| STEP → TB6600 PUL− | 26 | common-anode: PUL+/DIR+ to +5 V, ESP32 sinks |
| DIR → TB6600 DIR− | 27 | |
| **`ENA` → TB6600 ENA−** | **14** | **Added — diagram marks ENA± n/c. See below** |
| Router contactor | 4 | as `relay_spindle` so `M3`/`M5` owns router power |
| Probe (touch-off plate) | 32 | |
| Home / bottom limit | 33 | machine zero per MOT-04 |
| Top limit | 25 | bounds bit-change rapid per MOT-05 |
| Foot switch | 13 | `macro0_pin`; **use 13, not 34/35** — GPIO 34–39 have no internal pullups |
| UART1 TX → S3 | 17 | |
| UART1 RX ← S3 | 16 | |
| **`DRIVER_ALARM`** | **35** | **Reserved for MOT-10 / DEV-01 closure — see below.** Wire NC through the limit conditioning circuit |
| Reserved | 34 | Held for feedback hardware; do not reassign |
| **STOP button** | **21** | `feed_hold_pin` — native FluidNC control pin. **Works with no HMI involvement**, so it halts motion even if the S3 has crashed or the UART dropped. This is why it does not live on the HMI expander with the other five buttons |

### Level shifting — required in exactly one place

| Signal | Level | Shifter? |
|---|---|---|
| MPG A/B → S3 GPIO 11/12 | **5 V** | **Yes, required** — ESP32-S3 is not 5 V tolerant |
| STEP/DIR/ENA → TB6600 | 3.3 V sinking | No — *provided* the common anode change below |
| Limits (mechanical or NPN) | contact / open collector to 3.3 V | No — conditioning circuit covers it |
| Probe, foot switch, selector, cycle start | dry contact to GND | No |
| UART, HMI ↔ FluidNC | 3.3 V both ends | No (B.10) |
| Relay module input | 3.3 V into a 5 V board | Usually fine — **verify at bench test 3** |

**Change the TB6600 common anode from +5 V to +3.3 V.** `docs/superseded-wiring_diagram.svg` currently says
"common +5 V". With common-anode wiring the ESP32 sinks `PUL−`/`DIR−`, and in the *off* state
drives the pin to 3.3 V — leaving 5 − 3.3 = 1.7 V across the input optocoupler, above its ~1.2 V
LED forward drop. The opto never cleanly turns off. This is the classic ESP32↔TB6600 failure and
presents as **missed steps at higher step rates** — which on this build means silent depth error,
because DEV-01 leaves nothing to detect it. Tying the common to +3.3 V gives a true 0 V off state
and ≈8 mA on state ((3.3 − 1.2)/270 Ω), at the low end of the input range but generally sufficient.
Fallback if bench test 3 shows missed steps at rapid: a 74HCT245 buffer driving the inputs at 5 V.

**MPG conditioning.** A resistor divider is adequate on rate grounds — 100 PPR at a fast hand spin
is well under 1 kHz against ELE-10's 5 kHz ceiling. Given the router alongside, prefer a
**74HCT14 with two inverter stages per channel** for Schmitt hysteresis against EMI.

⚠️ **`MPG::SIGNALS_INVERTED` flips to `false`.** The legacy constant is `true`, assuming PC817
optocouplers. A divider, a 74LVC245, and a two-stage 74HCT14 are all **non-inverting**. Getting
this wrong makes the handwheel count backwards.

### TB6600 `ENA` — wire it, do not leave n/c

The diagram marks `ENA±` not connected, which means the motor is energised at 2.8 A/phase
continuously with no idle-current reduction. Two costs: FluidNC cannot de-energise the motor at
all, and ENV-03's 8-hour session requirement comes under real thermal pressure in both motor and
driver. The legacy firmware *had* software disable (`Pins::ENABLE`, used by `Safety::trigger()`);
that capability is lost in the new wiring because GPIO 27 became DIR.

Leaving it n/c is defensible — MEC-02's self-locking ACME screw holds position unpowered, so
nothing drops. But wire `ENA−` to **GPIO 14** anyway: it costs one pin, enables FluidNC's
`disable_pin` and `$Stepper/IdleTime`, and can be left permanently enabled by default. Discovering
you want it later means re-opening the enclosure.

### Closed-loop feedback (MOT-10) and closing DEV-01

MOT-10 makes feedback optional and §14 leaves "closed-loop in the first build?" open, but DEV-01
is only closable by a stall-capable driver *or* an encoder. Three paths, and they are not equal:

| Path | Mechanism | FluidNC impact | Pins |
|---|---|---|---|
| **A — TMC5160** | StallGuard load sensing; driver reports impending stall | Native — FluidNC drives Trinamic over SPI/UART and can home on StallGuard | SPI/UART bus |
| **B — Closed-loop driver** (CL57T, iHSS, integrated NEMA 23) | Encoder on the motor, driver closes the loop internally, asserts **ALARM** on lost position | **One digital input.** Stock FluidNC, still step/dir | 1 |
| **C — Raw encoder into the ESP32** | A/B quadrature into FluidNC for position verification | ✗ **Not supported** — FluidNC has no closed-loop feedback for step/dir axes | 2–3 |

**Path C is the trap**, and it is what "add an encoder" naturally suggests. Implementing it means
forking FluidNC, which destroys the "stock FluidNC, `config.yaml` only" property this whole
architecture rests on. Verify against the installed release, but plan as if unavailable.

**Path A also closes the ELE-01 deviation** ("Trinamic-class driver"), so it settles both halves
of DEV-01 in one move. **Path B is the cheap retrofit** — keeps the TB6600 wiring model, needs one
input, works with stock FluidNC today.

**Action now, cost one wire:** reserve **GPIO 35 as `DRIVER_ALARM`**, wired NC through the same
conditioning circuit as the limits so that both a driver fault and a broken wire fault the
machine. DEV-01 then closes as a `config.yaml` edit rather than a rewire. The pins freed by moving
the MPG to the S3 (34/35) are exactly what feedback hardware wants — reserve them, do not reuse.

Key values, from spec Annex B.5 and §2.1:

- `steps_per_mm: 800` — TB6600 at 1/8 microstepping = 1600 pulses/rev, T8 screw 2 mm lead.
  **Note this contradicts `legacy/include/config.h`** (1000 steps/rev, 4 mm pitch); the spec wins.
- `max_travel_mm: 90` (MEC-01 target), soft limits enabled (MOT-09).
- Rapid ≥10 mm/s, plunge 1–5 mm/s default 2–3 (MOT-08).
- Two-stage homing (fast seek, back off, slow confirm) to satisfy MOT-06's ±0.02 mm.

### Endstop management

Three independent layers, deliberately owned by three different things. Nothing in the HMI
appears in any of them — this is the core of ELE-11.

| Layer | Mechanism | Owner |
|---|---|---|
| **E-stop** | NC contact breaking mains L, feeding both the PSU and the router contactor | Hardware only. Not a GPIO, not visible to firmware (SAF-01) |
| **Hard limits** | `limit_neg_pin: gpio.33` (bottom), `limit_pos_pin: gpio.25` (top) | FluidNC — alarm state, motion halted |
| **Soft limits** | `$Limits/Soft`, envelope from `mpos_mm` + `max_travel_mm: 90` | FluidNC (MOT-09) |

**Three tiers of limit, and they must not be conflated:**

| Tier | Set by | Where | Changes |
|---|---|---|---|
| Hard limits | Physical switch position | Bolted to the machine | Never |
| Soft limits | Commissioning — travel + home reference | `config.yaml` | Once, at build |
| Job ceilings | Operator — presets, teachable Target Set (Phase 4b #2) | HMI, NVS | Every job |

**Soft limits move from tier 3 to tier 2 — a deliberate, user-approved change.**
`legacy/src/Settings.cpp` persists `softMinMm`/`softMaxMm` to NVS and `legacy/src/Menu.cpp`
exposes them as editable calibration rows. **Do not port those rows.** The operator must not be
able to widen their own envelope from the panel, and keeping them would give the HMI write access
to a safety-relevant setting, against ELE-11. The affordance is *replaced*, not removed: per-job
ceilings come from presets and the teachable Target Set, both of which can only ever be
*narrower* than the commissioned envelope. The HMI displays the envelope; it never writes it.

**Why the hard limits carry more weight on this build than on a typical machine.** DEV-01 means
the TB6600 has no stall detection, so FLT-01 is unimplementable here. Open-loop with no stall
sensing lets position error accumulate *silently* — a step missed during a heavy plunge does not
announce itself, it quietly shifts everything after it. Soft limits cannot catch this, because
FluidNC trusts its own step count. **The bottom switch is the only thing that ever discovers the
drift.** Two consequences: the switches are a primary protection here rather than a backstop, and
FW-09's Z0-invalidation discipline must be strict, because a limit hit tells you something
slipped but never how much.

**This deletes code rather than porting it.** `legacy/src/Homing.cpp`'s four-state
SEEK_FAST→BACKOFF→SEEK_SLOW→DONE machine and `main::checkEndstops()`'s polling — including its
careful suppression of endstop faults while homing or zeroing is active — are both native FluidNC
behaviour. The `homing:` block (`seek_rate`, `feed_rate`, `pulloff_mm`, `settle_ms`) does the
two-stage approach that MOT-06's ±0.02 mm needs, and FluidNC already knows a limit hit during a
homing cycle is expected rather than a fault. Do not reimplement any of it.

**The bottom switch does double duty** — home reference *and* negative hard limit on one pin.
MOT-04 makes it machine zero. FluidNC supports this directly; the top switch is limit-only and
exists to bound the bit-change rapid (MOT-05).

**Switch selection — decided. Support BOTH mechanical and inductive, selectable by config.**
Two switches fitted: bottom (GPIO 33, home + negative limit) and top (GPIO 25, positive limit).
The user has ordered both types; the design must accept either without rework.

**Both wired NC, and both then present identically to the ESP32:**

| | Idle (not at limit) | At limit | Wire break |
|---|---|---|---|
| Mechanical NC, COM→GND | contact closed → LOW | opens → pull-up → HIGH | floats → HIGH = triggered ✓ |
| Inductive NPN NC | transistor conducting → LOW | turns off → pull-up → HIGH | floats → HIGH = triggered ✓ |

Both are **active-HIGH with a pull-up**, and both fail safe — for the inductive sensor a severed
*supply* wire also reads as triggered. So the FluidNC pin string is the same either way:
`limit_neg_pin: gpio.33:pu` (active high is the default — no `:low`). This is the opposite
polarity from the usual CNC convention, a deliberate consequence of choosing NC for fail-safe.

**One common input-conditioning circuit accepts either type** — this is what makes swapping a
config change rather than a rewire, and it satisfies ELE-04 in hardware:

```
sensor out ──┬── 10k ──┬── GPIO 33
             │         │
          4k7 to 3V3   ├── BAT54S clamp to 3V3 / GND
                       └── 100nF to GND
```

- 10 k series + clamp means an accidental 24 V on the line delivers ~2 mA into the clamp instead
  of destroying the ESP32 — a live risk now that both sensor types share a drawer.
- 10 k × 100 nF ≈ 1 ms RC filter — ELE-04's "debounced, EMI-hardened" met in hardware, not
  software. Covers mechanical contact bounce (1–5 ms) too.
- External 4k7 pull-up rather than the internal ~45 k, keeping rise time sub-millisecond.

**Verify the inductive part numbers before wiring.** On the common `LJ12A3-4-Z/xx` family:
**`/BY` = NPN NC — required.** `/BX` = NPN NO, `/AY` = PNP NC, `/AX` = PNP NO. **Any `/A` suffix
is PNP and sources 24 V into the GPIO.** The clamp circuit survives it; a bare pin does not.

**Mechanical option:** roller-lever microswitch, NC, dry contact to GND. Omron **SS-5GL2** or
equivalent; V-156-1C25 for a more robust body; Honeywell 914CE / Omron D4C for IP67 per MEC-06.
Buy four — two fitted, two spares. **Roller lever chosen for overtravel, not repeatability:** with
no stall detection (DEV-01) a runaway drives into the switch until the controller reacts, and a
plain plunger bottoms out in ~0.5–1 mm and is destroyed where a lever deflects through several mm.

**Home-switch repeatability is not depth-critical**, for either type. FW-01 references cut depth
to the probe Z0, not to the home switch, so home variation shifts the soft-limit envelope and does
*not* move cut depth. This is why the inductive option's weaker repeatability (1–3 % of sensing
distance, ~0.04–0.12 mm, temperature-dependent) is acceptable here despite looking marginal
against MOT-02.

**Per-type config profiles.** Keep two commented blocks in `config.yaml` — the pin strings are
identical, only these differ:

| Setting | Mechanical | Inductive |
|---|---|---|
| `pulloff_mm` | 2 | 3 — larger release hysteresis |
| homing `feed_rate` | 60 mm/min | 40 mm/min — weaker repeatability, approach slower |
| Harness | 2-wire shielded pair | 3-wire + 24 V supply |

Wire **COM + NC**, leave NO unconnected. Shielded twisted pair, shield grounded at the controller
end only, routed away from the motor cable.

**Fit a hard mechanical stop just beyond each switch** — a shoulder or bolt head the carriage
cannot pass. The switch tells the controller to stop; the stop guarantees it. Cheap redundancy
given DEV-01, and it means an overrun damages nothing.

Other switchgear to purchase: 1 foot switch (momentary NO, GPIO 13), 1 rough/fine selector (SPDT,
HMI GPIO 10), 1 cycle-start button (momentary, HMI GPIO 13), and 1 E-stop — **latching
mushroom-head, NC, mains-rated**, since SAF-01 has it breaking L to both the PSU and the router
contactor. Not a logic-level button.

Three things to settle before wiring, in priority order:

1. **Confirm the ordered inductive sensors are NPN NC** (see part-number suffixes above) before
   anything is powered. `docs/superseded-wiring_diagram.svg` says only "shielded twisted pair · debounced
   (ELE-04)" and never states the type; the pre-RevG `CLAUDE.md` assumed NPN with a 24 V common.
   Record the actual as-built type and the conditioning circuit in Rev H rather than inheriting.
2. **Wire NC, not NO.** A broken wire or pulled connector then reads as triggered and faults the
   machine, rather than silently disabling the limit. FXBB made polarity an operator menu item
   (menu 13–15); for us it is a `config.yaml` pin modifier, which is correct — a commissioning
   decision, not an operating one.
3. **GPIO 33 and 25 both have usable internal pullups**, though the external 4k7 is preferred for
   rise time. This is not incidental: GPIO 34–39 have *no* internal pullups, which is exactly why
   the foot switch moved to GPIO 13 and the freed 34/35 stay unused. Do not quietly reassign a
   limit onto 34–39 later.
4. **Verify the soft-limit envelope convention.** FluidNC derives the travel envelope from
   `mpos_mm` together with `max_travel_mm` and the homing direction, and the sign convention
   differs between homing toward positive and toward negative. We home *down* to machine zero and
   work upward (positive = bit rising into the cut), which is the less common orientation. Confirm
   against the installed release's docs and prove it with `$J=` moves at both ends before trusting it.

**Two failure modes to design against, not just the trigger case:**

- **Stuck-on switch** — the FXBB diagnostic is worth stealing: if the axis has retreated ~4 mm and
  the switch still reads triggered, that is a dead switch or inverted polarity, not a limit
  (`ino:427-435`). FluidNC raises a pull-off failure alarm for the same condition; confirm it
  surfaces distinctly enough for the HMI to name the cause, and add an HMI-side check if not.
- **Phantom triggers from router EMI** — the real-world risk for a machine sitting next to a
  universal-motor router. ELE-04 mandates hardened inputs and ACC-07 is a 5-minute run with zero
  phantom triggers. FluidNC's software debounce alone is not the answer: shielded twisted pair
  (already on the diagram), an RC filter at the controller end, limit wiring routed away from the
  motor cable, and shield grounded at one end only.

Two further config areas need checking against the installed FluidNC version rather than assumed —
confirm the exact keys in the FluidNC wiki before writing:

- **Second UART channel.** FluidNC exposes a secondary GRBL channel via a `uart1:` section plus a
  `uart_channel1:` block carrying `report_interval_ms`. This is what makes "stock FluidNC, config
  only" possible — verify the key names and that `report_interval_ms` gives the ~10 Hz push the
  HMI wants, so it need not poll `?` continuously.
- **`$Macro0`** for the foot-switch plunge cycle. Confirm macro length limits and whether the
  macro can be made conditional on spindle-ready (SAF-03 / the legacy `Relay.isReady()` gate). If
  it cannot, the readiness gate moves into the HMI and the macro stays a bare move.

Also write `firmware/README.md`: which FluidNC release, how to flash it, how to upload
`config.yaml`, and the `$` settings that are not in the YAML.

---

## Phase 3 — `docs/UART-PROTOCOL.md`  ✅ COMPLETE

Written. Closes the §14 open item. GRBL/gcode over UART1, 115200, 3.3 V both sides, no level shifting.
Document, with worked examples:

- **Status:** HMI parses `<Idle|MPos:0.000,0.000,-12.345|FS:0,0>`. State, machine position, and
  feed drive the whole display (ELE-08).
- **Jog:** each MPG detent → `$J=G91 G21 Z<step> F<rate>`. Use jog commands, not `G91 G0`, so
  `0x85` jog-cancel is available and jogs never enter the queued motion buffer.
- **Homing:** `$H`. **Probe:** `G38.2 Z-<max> F<slow>` then read `PRB:` report.
- **Immediate:** `!` feed hold, `~` resume, `0x18` soft reset, `0x85` jog cancel.
- **Router:** `M3`/`M5` via `relay_spindle`.
- **Framing rules:** line-oriented, `\n`-terminated, one `ok`/`error:N` per line sent; the HMI
  keeps a bounded in-flight window and never sends a new line before the previous `ok`.
- **Link-loss behaviour:** define explicitly. If the HMI stops receiving status for N ms it shows
  a disconnected state and refuses to originate motion. Critically — per ELE-11 — link loss must
  **not** be able to start motion or block a stop, and the E-stop chain is hardware and is
  unaffected either way.
- A short table mapping each §7 canned-cycle step to the exact command sequence.

---

## Phase 4 — `hmi/` (ESP32-S3 firmware)

### Pin map (the tight part)

The RGB bus consumes 20 GPIOs, and the N4R8's octal PSRAM takes 33–37. **The TF card is
sacrificed** to free 10–13. Final budget:

| Function | GPIO |
|---|---|
| UART TX → FluidNC RX(16) | 18 |
| UART RX ← FluidNC TX(17) | 17 |
| MPG A / B (**via level shifter — see below**) | 11 / 12 |
| I²C SCL / SDA (GT911 **+ MCP23017**) | 20 / 19 |
| Spare | 10, 13, and 0 (BOOT strap — avoid for a panel button) |

**Panel buttons go on an MCP23017 at 0x20, not on GPIOs.** The RGB bus leaves the S3 with three
free pins and one of those is a boot strap, so five HMI-side buttons plus the rough/fine switch
will not fit. The expander shares the GT911's existing I²C bus (GT911 is at 0x5D — no conflict),
costs **zero GPIOs**, drives the ROUTER LED, and leaves ten I/O spare. Port the polling and
debounce from `legacy/src/IOExpander.cpp`; drop its board-ID logic.

| MCP23017 | Function |
|---|---|
| A0 | CYCLE START — start cycle / advance pass |
| A1 | ROUTER — toggle `M3`/`M5` |
| A2 | BIT CHANGE — short: rapid to top + lock out; long: exit, forcing re-probe |
| A3 | ZERO — short: probe `G38.2`; long: set zero here without probing |
| A4 | PRESET — short: recall active; long: save current height |
| A5 | Rough/fine selector (ELE-09) |
| B0 | ROUTER LED — lit = live, blinking = warming |

**STOP is deliberately NOT here** — it lives on FluidNC GPIO 21 as `feed_hold_pin`, so it halts
motion even if the S3 has crashed or the UART has dropped. See the FluidNC pin table. The other
five buttons all depend on HMI state (NVS presets, Z0 validity, cycle state machines) and cannot
move to FluidNC without forking it.

⚠️ **STOP is a feed hold, not an E-stop.** Keep them physically unmistakable — E-stop as the
mains-rated red mushroom on yellow, STOP as a flush round button, mounted well apart.

Fixed by the board: RGB bus 1, 3–9, 14, 15, 16, 21, 39–42, 45–48; backlight 2; GT911 SCL 20 /
SDA 19 / RST 38; console 43/44. Put this map in a single `hmi/include/pins.h` and nowhere else.

### Project setup

- `board = esp32-s3-devkitc-1`, `board_build.arduino.memory_type = qio_opi` (octal PSRAM),
  `board_build.partitions` sized for LVGL.
- `lib_deps`: `moononournation/GFX Library for Arduino`, `lvgl@^8.4`. Vendor `touch.h`/`touch.cpp`
  (GT911) from the zip's `3_3-4_TFT-LVGL-Widgets` demo — that demo is the working reference for
  panel init, LVGL glue, and touch, and its `Arduino_ESP32RGBPanel` +
  `Arduino_RPi_DPI_RGBPanel` (480×272, 9 MHz pclk) constructor arguments should be copied verbatim.
- LVGL draw buffers in PSRAM.

### Modules

- `Link` — GRBL sender: TX queue with the `ok` window, status-report parser, connection state.
- `Wheel` — PCNT quadrature on 11/12, 4× decode, 100 PPR. Scale per ELE-09/B.8: fine
  0.01 mm/detent (1 rev = 1 mm), rough 0.1 mm/detent (1 rev = 10 mm). Emits jog commands via `Link`.
  Rate-limit so a fast spin cannot flood the UART.
- `Cycles` — the §7 state machines: standard scribe/rough/finish scheduler (FW-02: equalised
  passes to D−F, finish at D), dovetail, keyhole, bit-change.
- `Zero` — FW-09 Z0-validity tracking. Invalidated by bit-change entry, homing loss, E-stop,
  brownout, stall, watchdog, **and link loss**. Presets lock when Z0 is invalid (FW-08).
- `Store` — NVS presets and calibration. Port the debounced-flush pattern from
  `legacy/src/Settings.cpp` (2 s dirty-flush) — it is sound and directly reusable.
- `Ui` — LVGL screens. `legacy/src/Menu.cpp` (12 screens) and `legacy/src/Display.cpp` are the
  content reference; the layout is redrawn for 480×272 landscape rather than 480×320.

### Safety invariants to carry across

From the old design's rationale, still binding:

- **One chokepoint for motion.** Every motion request goes out through `Link`. Nothing else writes
  to the UART.
- **MPG jogs, touch navigates.** Accidental touch must not move the cutter; accidental wheel spin
  must not fire a menu action.
- **The HMI has no motion authority (ELE-11).** Soft limits, homing, and the probe are enforced by
  FluidNC, not by the HMI. The HMI's own limit checks are advisory UI only — never the last line
  of defence.

---

## Phase 4b — Capability delta vs the FXBB FräsLift V3

Mined from `docs/reference/FXBB-original/FXBB_RouterLift_1-0-0.ino` (1166 lines) and its manual —
the shipping commercial lift this project replaces. RevG is the more capable machine in almost
every respect, so this is a short list of specific operator affordances worth adopting, not an
architectural rethink.

**Where FXBB has nothing and we already win** (no action — recorded so it is not re-litigated):
multi-pass scribe/rough/finish cycles; named presets (FXBB: one volatile, unnamed slot); router
power switching (FXBB has *no* relay or interlock at all — bit changes rely on operator
discipline); probe with plate-thickness handling; MOT-07 approach-from-below (FXBB has no
backlash compensation whatsoever, only a dead `runOut` code path); plural fault codes (FXBB has
exactly one, `ENDSTOP ERR`); Z0-validity tracking; two limit switches rather than a workspace
band inferred downward from one.

**Gaps worth closing:**

| # | FXBB capability | Our status | Adopt as | Where |
|---|---|---|---|---|
| 1 | **One-revolution look-ahead clamp** — jog target clamped to ≤1 motor rev ahead of actual position, so spinning the wheel fast cannot queue a long move (`ino:282-289`) | **Missing, and matters more for us.** Our MPG emits `$J=` per detent over UART; a fast spin can build a jog queue FluidNC will faithfully execute after the wheel stops | Clamp pending jog distance in `Wheel`; use `0x85` jog-cancel on direction reversal. Stronger than the rate-limit already in Phase 4 | HMI `Wheel` |
| 2 | **Target Set — teachable travel ceiling** — move to a height, long-press, that position becomes a hard upper limit you cannot jog past, so you can plunge blind into the work. Long-press again to clear (`ino:222-252`, `ino:307-312`) | **Missing.** We have static soft limits and saved presets, but nothing operator-teachable in one gesture at the machine | Adopt. A temporary ceiling distinct from both soft limits and presets, with a persistent on-screen indicator | HMI `Cycles` + `Ui`; new requirement |
| 3 | **Live derived values while editing** — setup screens show resulting mm-per-handwheel-revolution next to the raw step count (`ino:937`, `ino:960`) | **Missing.** ELE-08 lists what the display must show but not derived feedback during calibration | Adopt. Show mm/rev and mm/detent live in the calibration screens | HMI `Ui` |
| 4 | **Approaching-limit warning** — `WS MAX`/`WS MIN` shown within 10 steps of either limit (`ino:800-809`) | **Missing.** We fault at the limit but give no warning approaching it | Adopt. Proximity indicator in the status bar | HMI `Ui` |
| 5 | **Stuck-switch diagnostic** — if the axis has retreated ~4 mm and the endstop still reads triggered, raise a distinct fault (wrong NO/NC, dead switch) rather than driving on (`ino:427-435`) | **Partially covered.** FluidNC detects homing pull-off failure, but this is a sharper, better-named diagnostic | Confirm FluidNC's pull-off failure surfaces distinctly; if not, add an HMI-side check. Include the FXBB fault table's symptom→cause pairs in our FLT-05 code list | FluidNC + HMI |

**Considered and rejected:** operator-settable NO/NC polarity per switch (FXBB menu items 13–15) —
in our design that is a `config.yaml` pin modifier, correctly a commissioning decision, not an
operator one. Power-on toolchange (FXBB menu 12) — MOT-04 already mandates homing at power-up, so
making it optional would weaken the requirement. Forcing SLOW jog after zeroing (`ino:507-508`) —
FW-06's 0.05 mm sneak-up covers the intent without an unrequested mode change.

**Shared gap, flagged not scheduled:** both FXBB and our RevG are **mm-only**. Neither supports
inch. Worth a deliberate decision rather than an accident, though a metric shop makes it moot.

---

## Phase 5 — Spec amendment (Rev H)

The build has already diverged from RevG in two recorded ways, so the spec needs a revision rather
than silent drift:

- **Annex B.10** — replace the JC4827W543C/NV3041A record with the ESP32-4827S043 as-built:
  ILI6485 RGB parallel, the 20-pin bus, GT911 on 19/20, TF card sacrificed, and the resulting
  free-pin budget.
- **ELE-11** — reword. The HMI is no longer display-only; it owns the MPG and panel inputs and
  originates jog/cycle commands. Keep the invariant that it has no *authority over safety*:
  limits, homing, probe, and the E-stop chain are unaffected by HMI failure.
- **§2.1 Baseline** and **Annex B.9** — record the final GPIO split across both boards.
- **§14** — close "HMI↔controller UART protocol"; point at `docs/UART-PROTOCOL.md`.
- New **Annex A.7** changelog row, revision history row for H.

Three existing docs describe the retired architecture and must be rewritten or marked superseded:
`docs/ARCHITECTURE.md`, `docs/HARDWARE.md`, `docs/superseded-SCHEMATIC.svg`. `docs/BENCH-TEST.md` needs a full
rewrite — its 9-step ladder is built around the MCP23017 and the bespoke firmware.

Note `DEV-01` is untouched by all of this: the TB6600 still cannot do stall detection, so FLT-01
and the stall portion of ACC-09 stay deferred.

---

## Verification

Incremental, each step gating the next — no router, no bit, until the last steps.

1. **Build.** `pio run -e hmi` compiles. `legacy/` is not built.
2. **Panel bring-up.** Flash the HMI; LVGL widgets render at 480×272 and GT911 touch tracks. This
   is the highest-risk step (RGB timing, PSRAM buffers) — if it fails, diff against the vendor
   `3_3-4_TFT-LVGL-Widgets` demo before touching anything else.
3. **FluidNC standalone.** Upload `config.yaml`, connect over USB, confirm `$$` reads back, `$H`
   homes on the bottom switch, top limit faults, `G38.2` probes, `M3`/`M5` clicks the relay —
   all **with the motor on the bench, not mounted, and the router unplugged**.
3b. **Both sensor types, before anything is mounted.** With the conditioning circuit built, meter
   the GPIO node while triggering each switch type — confirm it swings 0 V ↔ 3.3 V and never
   exceeds 3.3 V with the inductive sensor powered from 24 V. Then home on each type in turn and
   confirm the identical pin string works for both. Finally, **pull the signal wire mid-idle on
   each** and confirm it faults rather than going quiet — that is the fail-safe claim, and it is
   worth proving rather than trusting.
4. **Link.** Cross-wire 17/18 ↔ 16/17, confirm the HMI's status bar tracks `MPos` live as the
   axis is jogged from the USB console. Then confirm the reverse: MPG detents move the axis.
5. **Pin-budget check.** Confirm 10/11/12/13 read correctly with the RGB panel running — a
   conflict here shows up as display corruption, not as an input fault.
6. **Link-loss test.** Pull the UART cable mid-jog. Motion must stop or complete safely and must
   never start; the HMI must show disconnected; `$H`/limits must still work from USB.
7. **Cycles dry-run.** Each §7 cycle end-to-end, air-cutting, router unplugged (ACC-05).
8. **Acceptance.** ACC-01 to ACC-04 repeatability with a dial indicator, then ACC-06/07/10/11.
   ACC-09's stall half stays deferred under DEV-01.

Only after all of the above: router plugged in at lowest speed, no bit in the collet, then
production cuts with an E-stop within arm's reach.

## Risks

- **RGB panel + LVGL on a 480×272 board with 6 free pins is the main technical risk.** If GPIO
  10–13 turn out to be committed to the TF card in hardware in a way that conflicts, the fallback
  is moving the UART to 43/44 and giving up the serial console — decide only if measured.
- FluidNC's second-UART key names must be verified against the installed release; if the version
  in hand lacks `uart_channel1`, the HMI has to share the USB serial channel, which costs the
  debug console.
- The canned cycles and Z0-validity logic living in the HMI is a real consequence of the GRBL
  choice. It is acceptable because FluidNC independently enforces limits, homing, and probing —
  but it means an HMI bug can produce a *wrong depth*, just never an *unsafe move*.
