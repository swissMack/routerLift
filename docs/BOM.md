# Bill of Materials

Document: RTL-BOM-001 · Rev A · Companion to `SCHEMATIC-RevH.svg`

Closes the §14 open item *"Produce the bill of materials."* Blocks A–H match the
schematic blocks exactly.

**Status key:** ✅ in hand · 🛒 to buy · 🔭 future / DEV-01 closure

---

## A · Mains, E-stop and router power

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | E-stop button | Latching mushroom head, **NC**, mains-rated | 🛒 | SAF-01. Breaks L to **both** PSU and contactor. Not a logic-level button |
| 1 | Router contactor | Coil to suit relay module; contacts ≥2× router nameplate | 🛒 | PWR-03. Add arc suppression (RC snubber across contacts). ⚠️ **Coil voltage unverified** — the wiring map assumes 230 V AC; no part chosen yet |
| 1 | RCD / GFCI | To suit local installation | 🛒 | PWR-02 |
| 1 | Mains fuse + holder | Sized for PSU + router | 🛒 | In L, after the E-stop |
| 1 | Router socket | Switched, PE-bonded | 🛒 | Fed from contactor T1 |
| 1 | **Bit-change key switch** | Keyed, 2-position, key removable in OFF only | 🛒 | **SAF-02 hardware interlock.** In series with the contactor coil, between the relay contact and A2. Key out = contactor physically cannot pull in, regardless of firmware |
| — | Mains cable, 3-core | To local code | 🛒 | PE to enclosure, lift frame **and** router socket |

## B · Power supply and rails

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | PSU | **24–36 V DC**, ≥50 % current margin | 🛒 | ⚠️ **Not 48 V.** TB6600 absolute max ≈40–42 V. This narrows §2.1's stated 24–48 V range and is a direct consequence of DEV-01 |
| 1 | DC-DC buck | 24–36 V → **5 V, ≥2 A** | 🛒 | Budget: panel ≈0.26 A (vendor spec), FluidNC ESP32 devkit up to ≈0.25 A with WiFi, relay module ≈70 mA, MPG ≈40 mA, shifter and expander negligible — **≈0.6–0.7 A**. ≥2 A is ≈3× margin, covering WiFi TX peaks and relay-coil inrush |
| — | +3.3 V (motion) | From the ESP32 devkit's onboard LDO | ✅ | Loads: 3 opto commons ≈24 mA + 5 conditioning pull-ups ≈4 mA |
| — | +3.3 V (panel) | From the panel's own regulator, P4 `3.3V` pin | ✅ | Feeds the 74LVC14 and MCP23017 only. ⚠️ **Never join it to the motion ESP32's 3.3 V** — join GND only |
| 1 | Star-ground point | At the PSU | 🛒 | PWR-04. One ground reference, not a daisy chain |

## C · Motion controller

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | ESP32 devkit | Classic ESP32 (**not** S3 — FluidNC does not run on S3) | 🛒 | Runs stock FluidNC; all machine definition in `config.yaml` |
| 1 | Relay module | 5 V, opto-isolated, drives the contactor coil | 🛒 | GPIO 4 via the `Relay` spindle (`M3`/`M5`). Verify it triggers reliably from 3.3 V logic at bench test 3 |

## D · Stepper drive

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Stepper driver | **HLTNC TB6600** | ✅ | DIP: 1/8 µstep, 1600 pulse/rev. ⚠️ **Set 1.0–1.4 A/phase, NOT 2.8 A** — see below. → **1066.67 steps/mm** at the FML-P's 1.5 mm lead |
| 1 | Stepper motor | **NEMA 23 57HS76-3004A08**, 3.0 A/phase | ✅ | Coils RED/GRN/YEL/BLU → A+/A−/B+/B− |
| 1 | **Router lift body** | **sauter Fräslift FML-P** — 1.5 mm/rev, 65 mm travel, Ø43 mm neck | 🛒 | **€329 B-stock** (`II-SA-FML-P`) / €378 new. Self-locking (~2.3° lead angle). See `docs/MECHANICS-RevH.md` |
| 1 | Shaft coupling | **Zero-backlash jaw (spider) or Oldham**, motor shaft → hex stub | 🛒 | Backlash goes straight into MOT-02. **No universal joints** |
| 1 | Drive stub | Hex bit stock to suit the lift's lower socket | 🛒 | ⚠️ **Measure it** — the published 5 mm is the *upper* socket |
| 1 | Motor bracket | Rigid, below the lift, coaxial with the spindle | 🛒 | Fabricated. The coupling absorbs residual misalignment, not a bad bracket |
| 1 | Spindle motor | Ø43 mm neck, ≤5 kg, ≤1,100 W — AMB, Suhner or Mafell | 🛒 | Continuous-duty with soft start, unlike a handheld router |
| — | Motor cable | Shielded, 4-core, ≥0.75 mm² | 🛒 | Route **away** from limit wiring |

> ⚠️ **Tie `PUL+`/`DIR+`/`ENA+` to +3.3 V, not +5 V.** With a 5 V common, the ESP32's
> 3.3 V logic high leaves 1.7 V across the input optocoupler — above its ~1.2 V LED
> drop — so it never fully turns off. Result is missed steps at rapid, which under
> DEV-01 is *silent depth error*. Fallback if bench test 3 shows missed steps:
> 1× **74HCT245** buffer driving the inputs at a proper 5 V.

> ⚠️ **Set the driver to 1.0–1.4 A/phase, not 2.8 A.** The lift needs about
> 0.15 N·m; the 57HS76 delivers ~2 N·m. That >10× margin is a *hazard* — with no
> stall detection (DEV-01) an oversized motor will destroy the lift if it drives
> into a hard stop. Lower current also cuts the heat caused by `idle_ms: 255`.
> This supersedes Annex B.5's 2.8 A, chosen when the mechanics were unknown.

> ⚠️ **Wire `ENA−` to GPIO 14.** The RevG diagram marks `ENA±` n/c, which leaves the
> motor energised permanently with no idle reduction — an ENV-03 thermal risk
> over an 8-hour session, and no way for FluidNC to de-energise. One extra wire buys
> `disable_pin` and `$Stepper/IdleTime`.

## E · Sensors and input conditioning

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 4 | Limit switch, mechanical | Roller lever, **NC**, e.g. Omron SS-5GL2 | ✅ | 2 fitted + 2 spares. Roller lever chosen for **overtravel**, not repeatability |
| 2 | Limit switch, inductive | **NPN NC** — `LJ12A3-4-Z/BY` | ✅ | ⚠️ Verify suffix. `/BX` = NPN NO, `/AY` and `/AX` are **PNP and source 24 V into the GPIO** |
| 1 | Touch-off probe plate | Conductive plate + croc clip | 🛒 | MOT-06. Record plate thickness (FW-10) |
| 1 | Foot switch | Momentary **NO**, industrial | 🛒 | FluidNC GPIO 13, `macro0_pin` |
| 2 | Hard mechanical stop | Shoulder / bolt the carriage cannot pass | 🛒 | One beyond each limit switch. Cheap insurance given DEV-01 |
| — | Sensor cable | Shielded twisted pair | 🛒 | Shield grounded at the **controller end only** |

### Conditioning circuit — ×5 (HOME, TOP, PROBE, FOOT, DRV_ALM)

| Qty | Item | Specification | Notes |
| --- | --- | --- | --- |
| 5 | Resistor | 10 kΩ, series | Limits an accidental 24 V to ~2 mA into the clamp |
| 5 | Resistor | 4.7 kΩ, pull-up to +3.3 V, **sensor/wire side** of the 10 kΩ | External rather than the internal ~45 kΩ, for rise time |
| 5 | Diode array | BAT54S, clamp to 3V3 / GND, **GPIO side** | What makes a mis-wired PNP sensor survivable |
| 5 | Capacitor | 100 nF to GND, **GPIO side** | 10 k × 100 n ≈ 1 ms RC — **ELE-04 met in hardware** |

**Topology:** `+3.3 V — 4.7 kΩ — wire node — 10 kΩ — GPIO node (BAT54S + 100 nF) — GPIO`. The
pull-up must sit on the wire side: on the GPIO side the 10 k / 4.7 k divider leaves a closed switch
at ≈2.2 V, which does not read LOW. Same as `docs/WIRING-RevH.md` diagram 4.

This one circuit accepts either switch type with no config change: wired NC, both
mechanical and inductive NPN idle LOW and read HIGH at the limit, and both fail safe
on a broken wire.

## F · Operator panel (HMI)

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Touch display board | **Guition JC4827W543C** — XH-S3E N4R8 (ESP32-S3, 4 MB flash, 8 MB octal PSRAM), 4.3" 480×272 IPS, NV3041A **QSPI**, GT911 touch | ✅ | Matches spec Annex B.10. Rev H wrongly recorded an ESP32-4827S043; bench bring-up 2026-09-13 confirmed the JC4827W543C |
| — | Supply | 5 V, ≈260 mA | — | Vendor spec. From the buck (block B) |
| 1 | Panel cutout / bezel | 120 × 70.2 mm module (vendor spec) | 🛒 | Confirm against the board in hand |
| 2 | Pull-up resistor | 4.7 kΩ, to 3.3 V | 🛒 | MCP23017 I²C bus 1 (GPIO 15 SDA / 16 SCL) |
| 3 | Connector leads | **MX1.25 (Molex 51021-compatible) 4-pin, single-ended**, pre-crimped | 🛒 | For P2, P3, P4. Only one lead ships with the board. Check pin 1 on P4 before trusting colours (see `docs/BRINGUP-LOG.md`) |

> Only ten GPIOs reach the JST 1.25 mm connectors: P1 GND · RXD · TXD · +5V (power/console),
> P2 IO46 · IO9 · IO14 · IO5, P3 IO6 · IO7 · IO15 · IO16, P4 "UART1" GND · 3.3V · IO17 · IO18
> (P5 carries the same as P4 — use one). Allocation: UART on P4 (TX 18 → FluidNC RX 16, RX 17 ←
> FluidNC TX 17, plus GND); MPG A/B and I²C bus 1 on P3; spares 5/9/14 on P2; GPIO 46 is a boot
> strap, avoid. The touch I²C bus (8/4) and the TF card lines (10–13) reach no connector.

## G · MPG handwheel and level shifting

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | MPG handwheel | **ZS80-5E100S** — 80 mm dial, 100 PPR, 5 V, single-ended | ✅ | ⚠️ Spec B.8 records the ZS61 (60 mm). Same electricals, larger dial. Corrected in Rev H |
| 1 | Schmitt inverter | **74LVC14, powered from 3.3 V** (panel P4), two stages per channel | 🛒 | 5 V-tolerant inputs, outputs swing 0–3.3 V, hysteresis for EMI. **Non-inverting** as configured |
| — | MPG cable | Shielded, 4-core | 🛒 | ELE-10 |

> ⚠️ **74LVC14, not 74HCT14 — design error corrected 2026-09-13.** Rev A of this BOM specified a
> 74HCT14. That part needs a 4.5–5.5 V supply, so its outputs swing to 5 V — unsafe into the
> ESP32-S3 — and at 3.3 V it is out of spec. The 74LVC14 runs at 3.3 V with 5 V-tolerant inputs
> and the same Schmitt action. If a 74HCT14 has already arrived, do not connect it to the S3.

> ⚠️ **Level shifting is required here and only here.** The ESP32-S3 is not 5 V
> tolerant. Consequence for firmware: **`MPG::SIGNALS_INVERTED = false`** — the legacy
> value of `true` assumed PC817 optocouplers. Wrong value makes the wheel count backwards.

## H · Physical control panel

Six buttons with short/long-press doubling, giving twelve functions, plus the rough/fine
switch. Deliberately split across both boards.

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | I/O expander | **MCP23017**, I²C, addr **0x20** | 🛒 | On its own I²C bus 1, GPIO 15 SDA / 16 SCL (connector P3), 100 kHz, external 4.7 kΩ pull-ups to 3.3 V. Powered from P4 GND · 3.3V. The touch bus reaches no connector. **Costs two GPIOs.** 16 I/O, 10 spare |
| 6 | Push button | Momentary NO, panel mount, ≥16 mm | 🛒 | Dry contacts to GND, expander internal pull-ups |
| 1 | Rough/fine selector | SPDT toggle → GND | 🛒 | ELE-09: 2 positions, not the legacy 3-band x1/x10/x100 |
| 1 | Indicator LED | Panel mount, + series resistor | 🛒 | ROUTER only — lit = live, blinking = warming |

### Button map

| Button | Board / pin | Short press | Long press |
| --- | --- | --- | --- |
| **STOP** | **FluidNC GPIO 21** → `feed_hold_pin` | Feed hold; router stays on | Soft reset (`0x18`) |
| CYCLE START | MCP23017 A0 | Start cycle / advance pass | — |
| ROUTER | MCP23017 A1 | Toggle router (`M3`/`M5`) | — |
| BIT CHANGE | MCP23017 A2 | Rapid to top, lock out | Exit, forcing re-probe |
| ZERO | MCP23017 A3 | Probe touch-off (`G38.2`) | Set zero here, no probe |
| PRESET | MCP23017 A4 | Recall active preset | Save current height |
| rough/fine | MCP23017 A5 | MPG scale | — |
| ROUTER LED | MCP23017 B0 | — | — |

**Why STOP is on the other board.** FluidNC's native control pins act with no HMI involvement, so
STOP halts motion even if the S3 has crashed or the UART has dropped. The other five depend on HMI
state — PRESET reads NVS on the S3, ZERO orchestrates the probe and Z0 validity, BIT CHANGE drives
an HMI state machine — so they cannot move without forking FluidNC.

> ⚠️ **STOP is a feed hold, not an E-stop.** The E-stop remains the mains-rated mushroom that kills
> the contactor (block A). Make them physically unmistakable — E-stop as a red mushroom on yellow,
> STOP as a flush round button, mounted well apart. **Two red mushrooms with different behaviours
> is a dangerous panel.**

**Side benefit:** keeping rough/fine and cycle start on the expander leaves three of the board's ten
connector GPIOs spare (5, 9, 14). `legacy/src/IOExpander.cpp` also becomes reusable —
port the polling and debounce, drop the board-ID logic.

## Enclosure, connectors and cable

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Enclosure | **≥IP54** | 🛒 | ENV-02, MEC-06. Electronics outside the router cabinet |
| — | Connectors | Keyed, distinct types for LV vs mains | 🛒 | PWR-04 — segregation, and impossible to cross-plug |
| — | Cable gland set | To suit IP rating | 🛒 | |
| — | Ferrites | On motor and sensor runs | 🛒 | Helps ACC-07's zero-phantom-trigger test |
| 1 | DIN rail + terminal blocks | To suit enclosure | 🛒 | PSU, buck, ESP32, TB6600 and conditioning board on rail; terminals make the cable schedule practical |

## Test equipment

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | **Dial indicator** | 0.01 mm resolution + magnetic base | 🛒 | **The most important item still to buy.** Required for ACC-01–04, and the only way to measure the real screw lead and confirm `steps_per_mm`. Without it every depth figure stays an assumption |
| 1 | Bench PSU | Adjustable, **current-limited** | 🛒 | Set the limit low during bring-up so a wiring error trips it rather than destroying a board — relevant given the PNP hazard and the 24 V rail |
| 1 | Multimeter | Continuity + DC volts | 🛒 | Bench test 4: confirm the conditioning circuit swings 0–3.3 V and never exceeds it with the inductive sensor on 24 V |

## 🔭 Future — closing DEV-01

DEV-01 (TB6600 has no stall detection, so FLT-01 and the stall half of ACC-09 are
deferred) closes by **one** of:

| Option | Item | FluidNC impact | Pins |
| --- | --- | --- | --- |
| **A** | TMC5160 driver | Native — StallGuard, and closes the ELE-01 deviation too | SPI/UART |
| **B** | Closed-loop driver (CL57T, iHSS, integrated NEMA 23) | **One digital input.** Stock FluidNC, still step/dir | 1 |
| **C** | ~~Raw encoder into the ESP32~~ | ✗ **Not supported** — no closed-loop feedback for step/dir axes. Would require forking FluidNC | — |

**Reserved now, at the cost of one wire:** GPIO 35 as `DRIVER_ALARM`, wired NC through
the same conditioning circuit as the limits. GPIO 34 held alongside it. Both are pins
freed by moving the MPG to the HMI board. With these reserved, option B becomes a
`config.yaml` edit rather than a rewire.

---

## Deviations from RevG recorded here

| Item | RevG says | As built | Where corrected |
| --- | --- | --- | --- |
| Display board | JC4827W543C, NV3041A QSPI | **Same — not a deviation.** Rev H's ESP32-4827S043 record was wrong (bench, 2026-09-13) | Annex B.10 stands |
| Handwheel | ZS61 (60 mm dial) | **ZS80** (80 mm dial), same 100 PPR | Rev H, Annex B.8 |
| PSU range | 24–48 V (ELE-01) | **24–36 V** | Already noted §2.1 under DEV-01 |
| TB6600 common | +5 V | **+3.3 V** | Rev H, Annex B.9 |
| `ENA±` | n/c | **Wired to GPIO 14** | Rev H, Annex B.9 |
| MPG pins | FluidNC GPIO 34/35 | **HMI GPIO 6/7**; 34/35 reserved for feedback | Rev H, Annex B.9 |
| MPG level shifter | — | **74LVC14 at 3.3 V** (BOM Rev A's 74HCT14 was a design error) | This BOM, block G |
