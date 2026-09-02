# Design Q&A — refining Rev H

50 open questions. Answers feed `DESIGN-PLAN-RevH.md`, `SCHEMATIC-RevH.svg`, `BOM.md`
and the Rev H spec amendment. Answer in any order; leave blanks where you don't know yet.

Marked **[BLOCKING]** where the answer changes work already planned, **[BUY]** where it
affects what you order.

---

## Decisions recorded so far

| Q | Question | Answer |
| --- | --- | --- |
| — | Existing machine? | **None. Greenfield build.** The FXBB is reference only, never a retrofit target |
| — | Work the lift must do | **All four**: repeatable depth, grooves/dados/rebates, dovetails/joinery, keyhole slots |
| — | Mechanics approach | **Motorise a commercial manual lift body.** Rigidity and guides bought in, not built |
| — | v1 scope | **Full spec as written** — all four canned cycles, full Z0 machinery |
| 17 | Motor idle current | **Stay energised always.** `$Stepper/IdleTime = 255`. ENA still wired to GPIO 14 so this stays changeable. Measure temperature at ACC-04 |
| 25 | Always-on-screen | **All four**: large height, Z0 validity, machine + router state, MPG scale + link status. Layout ~3:1 — dominant numeral over a slim status strip |
| 33 | Cycles in v1 | **All four.** Keyhole built last regardless — the only cycle where the cutter moves under power while engaged |
| 39 | Foot switch | **Hold to plunge, release to retract.** Dead-man behaviour, gated on relay ready |
| 43 | Link loss mid-cycle | **Feed hold immediately.** Z0 invalidated, re-home and re-probe required. No auto-resume |
| — | Physical buttons | **Six.** STOP on FluidNC's native `feed_hold_pin`; the other five on an MCP23017 I²C expander. LED on ROUTER only. All in the same panel as the display |

### Physical control panel (new — supersedes parts of Q25/Q27)

Six buttons with FXBB-style short/long-press doubling, giving twelve functions.

**Split across both boards, deliberately.** FluidNC's native control pins act with no HMI
involvement whatsoever, so **STOP still halts motion if the S3 has crashed or the UART has
dropped**. The other five depend on HMI state — PRESET reads NVS on the S3, ZERO orchestrates the
probe and Z0 validity, BIT CHANGE drives an HMI state machine — so they cannot move to FluidNC
without the fork problem.

| # | Button | Board | Short press | Long press |
| --- | --- | --- | --- | --- |
| 1 | **STOP** | **FluidNC GPIO 21** → `feed_hold_pin` | Feed hold — halt motion, router stays on | Soft reset (`0x18`) |
| 2 | **CYCLE START** | MCP23017 A0 | Start cycle / advance to next pass | — |
| 3 | **ROUTER** | MCP23017 A1 | Toggle router power (`M3`/`M5`) — **LED lit = live, blinking = warming** | — |
| 4 | **BIT CHANGE** | MCP23017 A2 | Rapid to top, lock out motion | Exit, forcing re-probe |
| 5 | **ZERO** | MCP23017 A3 | Probe touch-off (`G38.2`) | Set zero here, no probe |
| 6 | **PRESET** | MCP23017 A4 | Recall active preset height | Save current height to it |
| — | rough/fine switch | MCP23017 A5 | MPG scale (ELE-09) | — |
| — | ROUTER LED | MCP23017 B0 | lit = live, blinking = warming | — |

MCP23017 at **0x20** on the HMI's existing I²C bus (SCL 20 / SDA 19, shared with the GT911 touch
controller at 0x5D — no address conflict). Internal pull-ups, buttons to GND, polled at 20 Hz with
debounce. Ten I/O spare for later.

⚠️ **STOP is a feed hold, not an E-stop.** The E-stop remains the mains-rated mushroom that kills
the contactor. They must be physically unmistakable — E-stop as a red mushroom on yellow, STOP as
a flush round button, mounted well apart. Two red mushrooms with different behaviours is a
dangerous panel.

The touchscreen keeps only genuine second-level work: cycle configuration, preset management,
calibration, diagnostics, fault detail.

### Consequences to carry forward

- **`steps_per_mm: 800` is provisional and must be measured.** It followed from the spec's assumed
  T8 2 mm lead. A commercial lift body uses whatever lead its maker chose, commonly coarser.
  Measure with a dial indicator over a known number of motor revolutions before trusting any depth
  figure. MOT-01's 0.01 mm per full step is contingent on the lift you buy.
- **Travel (MEC-01) is now set by the lift body**, not by choice. Confirm it reaches 75 mm minimum.
- **Motor is comfortably oversized** — the 57HS76 at ~1.9–2.2 N·m will not be the limiting factor,
  so mechanical selection can be driven by rigidity and lead rather than torque.
- **`legacy/src/IOExpander.cpp` is reusable after all.** Previously written off as dropped; the
  MCP23017 returns on the HMI's I²C bus. Port the polling and debounce, drop the board-ID logic.
- **Pin pressure is relieved.** Moving rough/fine and cycle start onto the expander frees `G10` and
  `G13`, taking the HMI from zero spare GPIOs to three.

---

## A · Mechanics and the physical build

1. **[BLOCKING]** Retrofit an existing lift, or new-build carriage? §14 has this open and it
   drives everything below.
2. **[BLOCKING]** Measured carriage mass, including the router? Needed for real torque sizing —
   §2.1 assumes 3–6 kg.
3. Travel: MEC-01 says ≥75 mm with a 90 mm target. Which are we building, and what does the
   mechanics actually allow?
4. Router make and model, and collet size? Affects mass, mounting and the contactor rating.
5. **[BUY]** T8 screw length, and how is it supported — one bearing or two?
6. **[BUY]** Anti-backlash nut: spring-loaded, or a solid nut relying on MOT-07's
   approach-from-below instead?
7. Motor-to-screw coupling: direct, flexible coupling, or belt reduction? A reduction changes
   `steps_per_mm` and the whole speed envelope.

## B · Limits, homing and switches

8. **[BLOCKING]** Which switch type goes in first — mechanical or inductive? Both are supported,
   but bench test 3b needs a starting point.
9. Do the switches mount fixed with a flag on the carriage, or move with the carriage?
10. At the bottom limit, is the bit fully retracted below the table? Machine zero lands there.
11. Home on every power-up (MOT-04 as written), or only when Z0 is invalid?
12. Is a 2 mm pull-off acceptable, or is travel too tight to give that up?
13. During bit-change, hitting the top limit is *expected* (MOT-05). Should that be a silent
    controlled stop, or should it still announce itself?

## C · Motion and feeds

14. Target rapid rate? MOT-08 says ≥10 mm/s.
15. Default plunge rate? MOT-08 allows 1–5 mm/s, default 2–3.
16. Acceleration — start conservative and tune, or do you have a figure in mind?
17. **[BLOCKING]** Motor idle: disable after N seconds of inactivity, or stay energised always?
    Affects heat (ENV-03) versus holding stiffness.
18. Stay at 1/8 microstepping (800 steps/mm), or go finer for smoothness?
19. Which physical direction is positive Z — bit rising? Confirm before homing is configured.

## D · Probe and Z0

20. **[BUY]** Probe plate: bought or made? Measured thickness to 0.01 mm?
21. FW-11 allows Z0 referenced to table top *or* workpiece top. Which is your default?
22. Re-probe on every bit change (FW-09 as written), or offer "trust previous"?
23. Probe feed rates — fast find and slow confirm?
24. If the probe reads shorted at the start of a cycle (FLT-02 self-check), refuse to start, or
    warn and allow override?

## E · Operator interface

25. **[BLOCKING]** What must be on screen at *all* times, no matter which screen you're on?
    Current height, Z0 validity, and what else?
26. How many preset slots, and named or numbered? FXBB had one; the legacy firmware had six.
27. The teachable Target Set ceiling (Phase 4b #2) — what gesture sets it? Long-press on a
    touch target, the cycle-start button, or something else?
28. Units: mm only, as both RevG and FXBB assume? Or is inch ever wanted?
29. Display resolution: 0.01 mm throughout (ELE-08), or 0.001 mm anywhere?
30. Dim or blank the backlight after inactivity? It's a 4.3" panel next to a dust source.
31. Anything on a splash screen — firmware version, machine name, last calibration date?
32. English only, or German? FXBB's manual notes German words overflow small displays.

## F · Canned cycles

33. **[BLOCKING]** Which of the four §7 cycles do you actually want in the first build? All four
    is significantly more HMI work than the standard cut alone.
34. Between passes: auto-advance, or require operator confirmation each time? OPS-01 wants
    confirmation with auto as an option.
35. Default rough depth of cut and finish allowance? FW-03/FW-04 say ≤3 mm and 0.2–0.5 mm.
36. Scribe pass default on or off? FW-05 says on for plywood and veneer.
37. Keyhole cycle in the first build, or later? It's the most complex and the most dangerous.
38. Dovetail cycle in the first build, or later?

## G · Safety, faults and interlocks

39. **[BLOCKING]** Foot switch: hold-to-plunge and release to retract, as the legacy firmware
    did? Or press once down, press again up?
40. Does the HMI get a router on/off control, or is router power only ever commanded by a cycle?
41. FLT-07 wants a fault log of ≥20 events surviving power cycles. Worth the NVS wear, or skip
    for v1?
42. ENV-04's re-touch-off reminder — default 30 min of run time. Want it, and advisory only?
43. **[BLOCKING]** Link loss mid-cycle: stop immediately, or complete the current pass and then
    refuse to continue? Both are defensible.
44. SAF-02 wants a *hardware* bit-change interlock. How do you want to implement that
    physically — a key switch, a guard interlock, or the E-stop itself?

## H · Build sequence and practicalities

45. Bench-test everything on the desk first, or mount to the router table and test in place?
46. **[BUY]** Do you have a dial indicator good to 0.01 mm for ACC-01 to ACC-04?
47. **[BUY]** Enclosure: DIN rail inside a box, or components panel-mounted directly?
48. Where does the HMI physically mount — on the lift, on the fence, or on a pendant arm?
49. What's the first real job you want to cut with it? Useful as a concrete acceptance target.
50. Amend the spec to Rev H now, or after bench testing proves the design? Rev H currently has
    six recorded deviations waiting.
