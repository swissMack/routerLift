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
| 1 | Router contactor | Coil to suit relay module; contacts ≥2× router nameplate | 🛒 | PWR-03. Add arc suppression (RC snubber across contacts) |
| 1 | RCD / GFCI | To suit local installation | 🛒 | PWR-02 |
| 1 | Mains fuse + holder | Sized for PSU + router | 🛒 | In L, after the E-stop |
| 1 | Router socket | Switched, PE-bonded | 🛒 | Fed from contactor T1 |
| — | Mains cable, 3-core | To local code | 🛒 | PE to enclosure, lift frame **and** router socket |

## B · Power supply and rails

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | PSU | **24–36 V DC**, ≥50 % current margin | 🛒 | ⚠️ **Not 48 V.** TB6600 absolute max ≈40–42 V. This narrows §2.1's stated 24–48 V range and is a direct consequence of DEV-01 |
| 1 | DC-DC buck | 24–36 V → **5 V, ≥2 A** | 🛒 | HMI panel + backlight ≈0.5 A, MPG ≈40 mA, relay ≈70 mA. The RevG figure of ≥1 A assumed the QSPI display; the RGB panel draws more |
| — | +3.3 V | From the ESP32 devkit's onboard LDO | ✅ | Only load is 3 opto commons ≈24 mA |
| 1 | Star-ground point | At the PSU | 🛒 | PWR-04. One ground reference, not a daisy chain |

## C · Motion controller

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | ESP32 devkit | Classic ESP32 (**not** S3 — FluidNC does not run on S3) | 🛒 | Runs stock FluidNC; all machine definition in `config.yaml` |
| 1 | Relay module | 5 V, opto-isolated, drives the contactor coil | 🛒 | GPIO 4 via `relay_spindle` (`M3`/`M5`). Verify it triggers reliably from 3.3 V logic at bench test 3 |

## D · Stepper drive

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Stepper driver | **HLTNC TB6600** | ✅ | DIP: 1/8 µstep, 1600 pulse/rev, 2.8 A/phase → **800 steps/mm** at 2 mm lead |
| 1 | Stepper motor | **NEMA 23 57HS76-3004A08**, 3.0 A/phase | ✅ | Coils RED/GRN/YEL/BLU → A+/A−/B+/B− |
| 1 | Lead screw | **T8 ACME, 2 mm lead**, self-locking, anti-backlash nut | 🛒 | MEC-02, MEC-03. Ball screw only with a brake per MEC-07 |
| — | Motor cable | Shielded, 4-core, ≥0.75 mm² | 🛒 | Route **away** from limit wiring |

> ⚠️ **Tie `PUL+`/`DIR+`/`ENA+` to +3.3 V, not +5 V.** With a 5 V common, the ESP32's
> 3.3 V logic high leaves 1.7 V across the input optocoupler — above its ~1.2 V LED
> drop — so it never fully turns off. Result is missed steps at rapid, which under
> DEV-01 is *silent depth error*. Fallback if bench test 3 shows missed steps:
> 1× **74HCT245** buffer driving the inputs at a proper 5 V.

> ⚠️ **Wire `ENA−` to GPIO 14.** The RevG diagram marks `ENA±` n/c, which leaves the
> motor at 2.8 A/phase permanently with no idle reduction — an ENV-03 thermal risk
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
| 5 | Resistor | 4.7 kΩ, pull-up to +3.3 V | External rather than the internal ~45 kΩ, for rise time |
| 5 | Diode array | BAT54S, clamp to 3V3 / GND | What makes a mis-wired PNP sensor survivable |
| 5 | Capacitor | 100 nF to GND | 10 k × 100 n ≈ 1 ms RC — **ELE-04 met in hardware** |

This one circuit accepts either switch type with no config change: wired NC, both
mechanical and inductive NPN idle LOW and read HIGH at the limit, and both fail safe
on a broken wire.

## F · Operator panel (HMI)

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Touch display board | **ESP32-4827S043** — ESP32-S3-N4R8, 4.3" 480×272 IPS, ILI6485 **RGB parallel**, GT911 touch | ✅ | ⚠️ Spec Annex B.10 wrongly records a JC4827W543C (NV3041A QSPI). Corrected in Rev H |
| 1 | Panel cutout / bezel | 120 × 70 mm module | 🛒 | Confirm against the board in hand |

> The RGB bus consumes 20 GPIOs and octal PSRAM takes 33–37, leaving ~6 usable pins.
> **The TF card slot is sacrificed** to free GPIO 10–13.

## G · MPG handwheel and level shifting

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | MPG handwheel | **ZS80-5E100S** — 80 mm dial, 100 PPR, 5 V, single-ended | ✅ | ⚠️ Spec B.8 records the ZS61 (60 mm). Same electricals, larger dial. Corrected in Rev H |
| 1 | Schmitt inverter | **74HCT14**, two stages per channel | 🛒 | 5 V → 3.3 V with hysteresis for EMI. **Non-inverting** as configured |
| — | MPG cable | Shielded, 4-core | 🛒 | ELE-10 |

> ⚠️ **Level shifting is required here and only here.** The ESP32-S3 is not 5 V
> tolerant. Consequence for firmware: **`MPG::SIGNALS_INVERTED = false`** — the legacy
> value of `true` assumed PC817 optocouplers. Wrong value makes the wheel count backwards.

## H · Physical control panel

Six buttons with short/long-press doubling, giving twelve functions, plus the rough/fine
switch. Deliberately split across both boards.

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | I/O expander | **MCP23017**, I²C, addr **0x20** | 🛒 | On the HMI's existing bus (SCL 20 / SDA 19) alongside the GT911 at 0x5D. **Costs zero GPIOs.** 16 I/O, 10 spare |
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

**Side benefit:** moving rough/fine and cycle start onto the expander frees HMI `G10` and `G13`,
taking the S3 from zero spare GPIOs to three. `legacy/src/IOExpander.cpp` also becomes reusable —
port the polling and debounce, drop the board-ID logic.

## Enclosure, connectors and cable

| Qty | Item | Specification | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Enclosure | **≥IP54** | 🛒 | ENV-02, MEC-06. Electronics outside the router cabinet |
| — | Connectors | Keyed, distinct types for LV vs mains | 🛒 | PWR-04 — segregation, and impossible to cross-plug |
| — | Cable gland set | To suit IP rating | 🛒 | |
| — | Ferrites | On motor and sensor runs | 🛒 | Helps ACC-07's zero-phantom-trigger test |

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
| Display board | JC4827W543C, NV3041A QSPI | **ESP32-4827S043**, ILI6485 RGB parallel | Rev H, Annex B.10 |
| Handwheel | ZS61 (60 mm dial) | **ZS80** (80 mm dial), same 100 PPR | Rev H, Annex B.8 |
| PSU range | 24–48 V (ELE-01) | **24–36 V** | Already noted §2.1 under DEV-01 |
| TB6600 common | +5 V | **+3.3 V** | Rev H, Annex B.9 |
| `ENA±` | n/c | **Wired to GPIO 14** | Rev H, Annex B.9 |
| MPG pins | FluidNC GPIO 34/35 | **HMI GPIO 11/12**; 34/35 reserved for feedback | Rev H, Annex B.9 |
