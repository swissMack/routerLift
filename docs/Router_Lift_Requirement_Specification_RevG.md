# Requirement Specification

*Stepper-Motor-Driven Router Lift for Repeatable Cut Depths*

Document: RTL-SPEC-001 Revision: G Date: 20 July 2026

Author: Tarik Mackmood Status: Draft for Review

## Revision History

| Rev | Date     | Author                       | Description                                                                                                                                                                                                                                                                                                                                  |
|---|---|---|---|
| A       | 9 July 2026  | Tarik Mackmood                   | Initial draft for review.                                                                                                                                                                                                                                                                                                                        |
| B       | 9 July 2026  | Tarik Mackmood / Claude (review) | Gap-fill and engineering review: new PWR, FLT, ENV, MNT sections; SAF-03/OPS-01 contradiction resolved; MOT-06, ELE-01, FW-09 strengthened; ACC-09–12 added. Full detail in Annex A.1.                                                                                                                                                           |
| C       | 9 July 2026  | Tarik Mackmood / Claude (review) | As-built motor and driver configuration added (Annex B): 57HS76-3004A08 motor, HLTNC TB6600 driver, wiring map and DIP settings. TB6600 vs ELE-01/FLT-01 recorded as accepted first-build deviation DEV-01. Design baseline supply range constrained for TB6600. Full detail in Annex A.2.                                                       |
| D       | 19 July 2026 | Tarik Mackmood / Claude (review) | MPG handwheel integrated as the fine-adjustment input (ZS61-type, 100 PPR, 4-wire 5 V): ELE-07 upgraded to Mandatory, new ELE-09 (rough/fine selector and scaling) and ELE-10 (electrical interface), FW-06 updated, new FW-12 (preset trim save-back), Annex B.8 as-built record. DEV-01 unaffected and remains open. Full detail in Annex A.3. |
| E       | 19 July 2026 | Tarik Mackmood / Claude (review) | System architecture figure added to §2. As-built data aligned with the bench setup reference: full motor part number HLTNC 57HS76-3004A08-D21-22, TB6600 supply range DC 9–42 V confirmed, ENA terminals left unconnected as-built. Full detail in Annex A.4.                                                                                    |
| F       | 19 July 2026 | Tarik Mackmood / Claude (review) | Wiring diagram added as Figure 2 (new Annex B.9): all terminal-level connections including MPG level shifting, TB6600 common-anode signal wiring, motor coil colours, sensor inputs, DC power, and the E-stop/contactor mains chain. Proposed FluidNC GPIO assignments recorded. Full detail in Annex A.5.                                       |
| G       | 20 July 2026 | Tarik Mackmood / Claude (review) | Touch HMI integrated: Guition JC4827W543C (ESP32-S3) added as operator display over UART in a split architecture — motion control remains on the FluidNC ESP32 because FluidNC does not run on the ESP32-S3. New ELE-11; Annex B.10 as-built record; Figures 1 and 2 updated; controller-platform open item closed. Full detail in Annex A.6.    |

# 1. Introduction

## 1.1 Purpose

This document specifies the requirements for automating the height adjustment of a router mounted in a router table, using a stepper-motor-driven lift. The objective is repeatable, programmable cut depths: multi-pass depth scheduling with a light finishing pass, scribe/scoring passes, joint-fitting to hundredths of a millimetre, and safe canned cycles for dovetail, keyhole, and bit-change operations.

## 1.2 Scope

The specification covers the lift mechanism, motor and drive electronics, position referencing, control firmware, operating modes and canned cycles, safety interlocks, power and electrical installation, fault handling, environmental and maintainability requirements, and acceptance tests. It applies equally to a retrofit of an existing manual lift and a new-build lift. Router selection, table construction, and fence automation are out of scope.

## 1.3 Priority Notation

M = Mandatory (system fails its purpose without it). S = Should have (strongly recommended). C = Could have (optional enhancement).

## 1.4 Definitions

| Term                         | Definition                                                                                                                                                                                                      |
|---|---|
| **Machine zero**                 | Repeatable lift reference position established by homing against the bottom limit switch.                                                                                                                           |
| **Z0 (cutting zero)**            | Bit-tip reference: the lift height at which the bit tip is flush with the reference surface (table or workpiece top, FW-11), established by touch-off. All cut depths are relative to Z0.                           |
| **Touch-off**                    | Procedure that detects contact between the bit tip and a probe plate to establish Z0. Required after every bit change.                                                                                              |
| **Pass**                         | One feed of the workpiece over the bit at a fixed height.                                                                                                                                                           |
| **Roughing increment (R)**       | Height increase per roughing pass.                                                                                                                                                                                  |
| **Finish allowance (F)**         | Material intentionally left by roughing, removed by the final light pass.                                                                                                                                           |
| **Final depth (D)**              | Target cut depth relative to Z0.                                                                                                                                                                                    |
| **Sneak-up mode**                | Fine jog mode (0.05 mm increments) used to fit joints to actual stock.                                                                                                                                              |
| **Canned cycle**                 | Pre-programmed sequence of lift moves and operator prompts.                                                                                                                                                         |
| **Stall / missed-step event**    | Loss of synchronism between commanded and actual motor position, detected by driver load measurement (e.g., StallGuard) or position feedback.                                                                       |
| **Probe-plate offset**           | Calibrated thickness of the touch-off plate, applied automatically so Z0 refers to the true reference surface (FW-10).                                                                                              |
| **Between-pass repositioning**   | A lift move commanded by an active canned cycle between feed passes, initiated only by operator cycle-advance confirmation (OPS-01, SAF-03).                                                                        |
| **MPG (manual pulse generator)** | A handwheel-operated incremental encoder used as an operator jog input. Each detent commands a configured height increment (ELE-09). An MPG is an input device only — it does not measure carriage or bit position. |
| **HMI (touch display)**          | The operator touch screen (ELE-11) that renders status and non-safety soft controls. The HMI has no motion authority; interlocks and Z0 validity are enforced by the motion controller.                             |

# 2. System Overview

The system raises and lowers the router carriage on a self-locking lead screw driven by a stepper motor under microcontroller control. Repeatability is achieved through discipline, not exotic hardware: a homing switch gives a repeatable machine zero, a touch-off probe re-references the bit tip after every bit change, and every commanded height is approached from below so lead-screw backlash never appears in the cut. Figure 1 shows the complete as-built architecture: operator inputs and sensors feed the controller; the controller commands the drive chain; and the hardware safety chain (E-stop and router contactor) gates power independently of firmware.

![Router lift system architecture block diagram](./media/cb8912e3a235d60346d2d3ce5947eae8ecb27893.png "Figure 1")

*Figure 1 — Router lift system architecture (as-built, Rev G)*

## 2.1 Design Baseline

The reference architecture assumed throughout this specification:

  - Trapezoidal (ACME) lead screw, T8 profile, 2 mm lead, self-locking, with anti-backlash nut.

  - NEMA 23 stepper motor, ≥ 1.5 N·m holding torque, 200 full steps/rev → 0.01 mm per full step.

  - Trinamic-class driver (TMC2209/5160 or external Leadshine-type), 24–48 V supply. As-built first build: HLTNC TB6600 under deviation DEV-01 — supply shall then be limited to 24–36 V (TB6600 absolute maximum ≈ 40–42 V; a 48 V supply would destroy it). See Annex B.

  - ESP32 or Arduino-class controller running GRBL or FluidNC (homing, soft limits, and probing supplied by the motion firmware). As-built decision (Rev G): split architecture — FluidNC on a standard ESP32 for motion, with a Guition JC4827W543C ESP32-S3 touch display as HMI over UART (ELE-11, Annex B.10). FluidNC does not run on the ESP32-S3, so the display board cannot host the motion firmware.

  - Bottom homing switch, top limit switch, touch-off probe plate, router power relay/contactor.

Alternative components are acceptable provided all requirements below are met. In particular, a ball screw may replace the ACME screw only if a brake or equivalent anti-back-drive measure satisfies MEC-07.

# 3. Mechanical Requirements (MEC)

| ID     | Requirement                                                                                                                                                                                              | Priority |
|---|---|---|
| **MEC-01** | Vertical travel shall be at least 75 mm (target 90 mm), sufficient to bury the bit fully below the table and to raise the collet nut fully above the table plate for above-table bit changes.                | M            |
| **MEC-02** | The drive screw shall be self-locking under router vibration with the motor unpowered (e.g., trapezoidal/ACME T8, 2 mm lead). A ball screw is permitted only with a brake or holding measure meeting MEC-07. | M            |
| **MEC-03** | Mechanical backlash shall be minimised with an anti-backlash nut; residual backlash shall be masked by firmware single-direction approach (FW-07).                                                           | M            |
| **MEC-04** | The lift shall carry the router and carriage (3–6 kg) through full travel and shall deliver sufficient thrust to plunge a keyhole bit into hardwood at 2–3 mm/s (OPS-03).                                    | M            |
| **MEC-05** | The carriage shall run on rigid guides (e.g., two hardened rods with linear bearings) with no perceptible play; deflection under normal cutting load shall not measurably alter cut depth.                   | M            |
| **MEC-06** | The screw, guides, and switches shall be protected from chips and fine dust (bellows, wipers, sealed bearings). Control electronics shall be mounted outside the router cabinet (see also ENV-02).           | M            |
| **MEC-07** | Commanded position shall not drift under sustained router vibration, whether holding via screw self-locking or motor holding current.                                                                        | M            |

# 4. Motion and Positioning Requirements (MOT)

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Priority |
|---|---|---|
| **MOT-01** | Positioning resolution shall be ≤ 0.01 mm per full step (achieved by 200 steps/rev with 2 mm screw lead, or equivalent).                                                                                                                                                                                                                                                                                                                                                                                                                                                   | M            |
| **MOT-02** | Bidirectional repeatability at any commanded height, using the standard from-below approach, shall be within ±0.05 mm; target ±0.02 mm.                                                                                                                                                                                                                                                                                                                                                                                                                                    | M            |
| **MOT-03** | Microstepping may be used for smoothness and noise only; positional accuracy shall be based on full steps and shall not rely on microstep linearity.                                                                                                                                                                                                                                                                                                                                                                                                                       | S            |
| **MOT-04** | A bottom limit switch shall provide machine zero. Homing shall be required at power-up before any cycle or preset can execute.                                                                                                                                                                                                                                                                                                                                                                                                                                             | M            |
| **MOT-05** | A top limit switch shall bound the bit-change rapid move (OPS-11); approach to it shall use a controlled deceleration, never a mechanical crash stop.                                                                                                                                                                                                                                                                                                                                                                                                                      | M            |
| **MOT-06** | A touch-off probe input (conductive touch plate on the table) shall establish Z0 to within ±0.02 mm as a single-button operation, using a two-touch procedure: a fast find touch followed by a slow confirming touch at reduced feed. Because the lowest point of a fluted bit depends on spindle orientation, the procedure shall either instruct the operator to rotate the spindle so a cutting edge is at bottom dead centre, or support multi-touch averaging across spindle orientations. The probe-plate thickness shall be applied as a calibrated offset (FW-10). | M            |
| **MOT-07** | Every final positioning move shall approach the target from below (raising into position) so backlash never appears in cut depth. Overshoot-and-return shall be applied automatically to downward moves.                                                                                                                                                                                                                                                                                                                                                                   | M            |
| **MOT-08** | Rapid traverse shall be at least 10 mm/s; programmed plunge moves shall be rate-controlled and configurable in the range 1–5 mm/s (default 2–3 mm/s).                                                                                                                                                                                                                                                                                                                                                                                                                      | S            |
| **MOT-09** | Soft limits shall prevent commanded motion beyond calibrated travel.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | M            |
| **MOT-10** | Closed-loop position feedback (encoder-equipped stepper or linear scale/DRO) may be added for verification; the baseline open-loop design with homing and touch-off shall meet MOT-02 without it.                                                                                                                                                                                                                                                                                                                                                                          | C            |

# 5. Electronics and Control Hardware (ELE)

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Priority |
|---|---|---|
| **ELE-01** | Stepper driver shall be a TMC2209/5160-class or external industrial driver, powered at 24–48 V DC, sized with ≥ 30% torque margin over the worst-case plunge load. The margin shall be assessed at the maximum commanded speed (MOT-08 rapid) and the selected supply voltage using the motor/driver speed–torque curve — not from holding torque alone, which overstates available torque at speed. Note: the first build deviates from this requirement — see accepted deviation DEV-01, Annex B.7.                                                                                                                           | M            |
| **ELE-02** | The controller shall provide homing, soft limits, and probe (touch-off) support natively, e.g., GRBL or FluidNC on ESP32/Arduino-class hardware.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | M            |
| **ELE-03** | Operator interface shall provide: jog up/down, selectable increment (including 0.05 mm sneak-up), preset recall, cycle start/advance, and a display of absolute height relative to Z0. Display and soft controls are rendered on the touch HMI (ELE-11); safety-relevant controls remain physical (E-stop per SAF-01; cycle-advance and rough/fine button per ELE-09).                                                                                                                                                                                                                                                          | M            |
| **ELE-04** | All switch and probe inputs shall be debounced and noise-hardened (shielded cable, twisted pairs, opto-isolation or equivalent) against EMI from the router's universal motor. No phantom triggers shall occur with the router running.                                                                                                                                                                                                                                                                                                                                                                                         | M            |
| **ELE-05** | Router mains power shall be switched through a relay/contactor controllable by the lift controller, enabling the hardware interlocks in Section 8 (rating per PWR-03).                                                                                                                                                                                                                                                                                                                                                                                                                                                          | M            |
| **ELE-06** | Motor holding current shall be configurable; if the screw is fully self-locking, idle current reduction is permitted.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | S            |
| **ELE-07** | An MPG (manual pulse generator) handwheel shall be provided as the primary fine-adjustment input, in addition to jog buttons. As-built device: ZS61-type 100 PPR handwheel encoder — see Annex B.8.                                                                                                                                                                                                                                                                                                                                                                                                                             | M            |
| **ELE-08** | The display shall show heights in millimetres with 0.01 mm resolution, and shall clearly indicate the Z0-validity state, the active Z0 reference surface (FW-11), the current operating mode, and the active MPG scale (ELE-09).                                                                                                                                                                                                                                                                                                                                                                                                | M            |
| **ELE-09** | A rough/fine selector button shall set the MPG scale. Defaults: rough = 0.1 mm per detent (10 mm per handwheel revolution at 100 PPR), fine = 0.01 mm per detent (1 mm per revolution); both values operator-configurable. The active scale shall be indicated on the display (ELE-08). MPG motion shall obey the same interlocks as jog inputs: inhibited while the router is powered (SAF-03) and during any feed pass (OPS-02). When a handwheel adjustment ends with net downward motion, the firmware shall automatically re-approach the final height from below (MOT-07) before the height is used for cutting or saved. | M            |
| **ELE-10** | The MPG electrical interface: 5 V single-ended quadrature (A/B), 4-wire (VCC, 0 V, A, B), input frequency capability ≥ 5 kHz with 4× quadrature decoding and glitch filtering. Being single-ended, the MPG cable shall be shielded and routed away from mains and motor wiring per ELE-04; no phantom counts shall occur with the router running (verified in ACC-07).                                                                                                                                                                                                                                                          | M            |
| **ELE-11** | A touch HMI (as-built: Guition JC4827W543C, Annex B.10) shall render the display functions of ELE-08 and may provide soft controls for non-safety functions (preset selection and naming, pass-list display, configuration, scheduler entry). The HMI connects to the motion controller over UART and shall be non-safety-critical: all motion authority, interlocks, soft limits, and Z0-validity enforcement remain in the motion controller (ELE-02). HMI failure, disconnection, or reboot shall not initiate, sustain, or block the stopping of motion, and cycle-advance shall remain available from a physical control.  | M            |

# 6. Firmware — Depth Management (FW)

| ID    | Requirement                                                                                                                                                                                                                                                                                                                                                                  | Priority |
|---|---|---|
| **FW-01** | All cutting heights shall be referenced to Z0 established by touch-off. Machine zero (homing) alone shall not be sufficient to run cutting cycles.                                                                                                                                                                                                                               | M            |
| **FW-02** | A pass scheduler shall accept final depth D, roughing increment limit R, and finish allowance F, and generate: optional scribe pass, equalised roughing passes to depth D − F (each ≤ R), and one finish pass at exactly D. Increments shall be equalised so no undersized final roughing pass occurs.                                                                           | M            |
| **FW-03** | Default roughing limits: R ≤ 3 mm and ≤ half the bit diameter in hardwood; up to bit diameter in softwood/MDF; 1.5–2 mm for large-diameter (panel-raising) bits. Values shall be operator-configurable.                                                                                                                                                                          | M            |
| **FW-04** | Finish allowance F shall be configurable 0.2–0.5 mm (default 0.3 mm). The finish pass exists to remove deflection, burning, and tearout from the roughed surface.                                                                                                                                                                                                                | M            |
| **FW-05** | A scribe/scoring first pass of 0.2–0.5 mm shall be available to sever surface fibres before roughing; default ON for plywood, veneer, and cross-grain profiles.                                                                                                                                                                                                                  | M            |
| **FW-06** | A sneak-up jog mode with 0.05 mm increments shall be provided for fitting joints to measured stock, operable via the increment buttons or the MPG handwheel in fine scale (ELE-09).                                                                                                                                                                                              | M            |
| **FW-07** | Backlash strategy: firmware shall enforce the from-below approach of MOT-07 for every cutting height, including preset recall and cycle steps.                                                                                                                                                                                                                                   | M            |
| **FW-08** | Named presets (per bit / per joint) shall be storable relative to Z0 and retained across power cycles. Presets shall be locked (not deleted) whenever Z0 is invalid, and unlocked by a successful touch-off.                                                                                                                                                                     | M            |
| **FW-09** | The controller shall track Z0 validity. The following events shall invalidate Z0 and block all cutting cycles and presets until touch-off is repeated: bit-change mode entry, homing loss, E-stop actuation, supply brownout or power loss (FLT-04), a detected stall or missed-step event (FLT-01), a watchdog reset (FLT-03), or any other fault affecting position integrity. | M            |
| **FW-10** | The firmware shall store the measured touch-off plate thickness as a calibrated parameter and apply it automatically during touch-off, so that Z0 refers to the true reference surface rather than the top of the plate.                                                                                                                                                         | M            |
| **FW-11** | The Z0 reference surface shall be selectable between the table surface and the workpiece top surface, and the active reference shall be clearly displayed (ELE-08), since joint depths are commonly specified from the workpiece surface.                                                                                                                                        | S            |
| **FW-12** | After recalling a preset, MPG fine adjustments (ELE-09) shall be applied as a displayed trim relative to the preset value. An explicit save action shall be required to write the trimmed height back to the preset (per OPS-06); trims shall never be saved implicitly. The display shall show both the preset value and the current trim.                                      | M            |

# 7. Operating Modes and Canned Cycles (OPS)

## 7.1 Standard Cut Cycle — Scribe / Rough / Finish

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                 | Priority |
|---|---|---|
| **OPS-01** | The standard cycle shall execute: home (if not homed) → touch-off (if Z0 invalid) → scribe pass → equalised roughing passes to D − F → finish pass at D. The lift shall advance to the next height only on operator confirmation (cycle-advance button) after each completed feed pass; an auto-advance option may be provided. Between-pass repositioning with the router running is permitted under the conditions of SAF-03. | M            |
| **OPS-02** | During any feed pass the lift shall be motion-locked: jog, preset, and cycle inputs shall be ignored until the pass is confirmed complete.                                                                                                                                                                                                                                                                                      | M            |
| **OPS-03** | Worked example (10 mm groove, R = 3 mm, F = 0.2 mm, scribe 0.3 mm): scribe at 0.3, then 9.5 mm remaining to D − F = 9.8 requires 4 equalised passes of 2.375 mm → roughing at 2.68 / 5.05 / 7.43 / 9.8 → finish at 10.0. The scheduler shall display the full pass list before starting.                                                                                                                                        | S            |

## 7.2 Dovetail Sequence

A dovetail bit undercuts (wider at the bottom), so incremental depth passes in the same slot are impossible: an intermediate-depth pass cuts a different profile, and the bit cannot be raised into an existing narrower slot, nor retracted mid-cut without destroying the work.

| ID     | Requirement                                                                                                                                                                                                                                      | Priority |
|---|---|---|
| **OPS-04** | The dovetail cycle shall be a two-bit sequence: (a) hog waste with a straight bit using the standard incremental scheduler, leaving ≈ 0.5 mm; (b) enter bit-change mode; (c) touch off the dovetail bit; (d) make a single full-depth dovetail pass. | M            |
| **OPS-05** | The firmware shall refuse incremental depth passes for a slot flagged as a dovetail profile, and shall lock all lift motion for the duration of the dovetail pass.                                                                                   | M            |
| **OPS-06** | Dovetail fit shall be adjustable in 0.05–0.1 mm height steps, and the dialled-in height shall be storable as a named per-bit preset so future joints repeat identically.                                                                             | M            |

## 7.3 Keyhole Cycle

A keyhole bit cuts a T-slot: it cannot exit sideways or be lifted out mid-slot, and must leave through the hole it entered. Unlike the dovetail, it enters vertically — a plunge the motorised lift performs under control.

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                    | Priority |
|---|---|---|
| **OPS-07** | The keyhole canned cycle shall execute: operator confirms workpiece clamped against fence between stops and router running → controlled plunge (raise) into the stationary workpiece at the configured plunge rate to full depth → optional dwell for chip clearing → operator feeds workpiece the slot length to the stop → operator feeds back to the exact entry point → operator confirms → lift lowers the bit clear → prompt to stop router. | M            |
| **OPS-08** | Plunge rate (default 2–3 mm/s), target depth, and dwell shall be programmable per keyhole preset.                                                                                                                                                                                                                                                                                                                                                  | M            |
| **OPS-09** | The retract move shall be blocked until the operator confirms return to the entry point.                                                                                                                                                                                                                                                                                                                                                           | M            |

## 7.4 Bit-Change Mode

| ID     | Requirement                                                                                                                                                                                               | Priority |
|---|---|---|
| **OPS-10** | Bit-change mode shall refuse to start unless the router is confirmed off, and on entry shall open the router power interlock (ELE-05) so the router cannot be powered while the mode is active.               | M            |
| **OPS-11** | On entry the lift shall rapid to maximum travel — collet nut fully above the table — decelerating into the top limit switch (MOT-05), then lock out all motion inputs while the operator works on the collet. | M            |
| **OPS-12** | Exit shall require explicit operator confirmation, after which the lift rapids down, Z0 is invalidated (FW-09), and a touch-off is forced before any preset or cycle can run.                                 | M            |
| **OPS-13** | The height in use before the change shall be remembered, and a “return to previous height” action offered after successful re-zeroing.                                                                        | S            |

# 8. Safety and Interlock Requirements (SAF)

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Priority |
|---|---|---|
| **SAF-01** | An emergency stop shall remove power from both the router and lift motion. E-stop shall be hardware-actuated, not firmware-only. Recovery behaviour per FLT-06.                                                                                                                                                                                                                                                                                                                                         | M            |
| **SAF-02** | The bit-change interlock (OPS-10) shall be enforced in hardware via the router power relay; a software check alone is not acceptable.                                                                                                                                                                                                                                                                                                                                                                   | M            |
| **SAF-03** | Lift motion shall be inhibited while the router is powered, with exactly two exceptions: (a) the explicitly programmed keyhole plunge/retract moves of OPS-07; and (b) between-pass repositioning within an active canned cycle, initiated only by the operator's cycle-advance confirmation (OPS-01), with the OPS-02 motion-lock enforced during every feed pass. Manual jogging, sneak-up moves, MPG handwheel input (ELE-09), and preset recall shall remain inhibited while the router is powered. | M            |
| **SAF-04** | Height changes shall occur only between passes, never during a feed (OPS-02, OPS-05).                                                                                                                                                                                                                                                                                                                                                                                                                   | M            |
| **SAF-05** | No cycle or preset shall execute without valid homing and valid Z0 (FW-09, MOT-04).                                                                                                                                                                                                                                                                                                                                                                                                                     | M            |
| **SAF-06** | The lift shall hold position under full router vibration with no operator input (MEC-07); loss of holding shall be treated as a fault that invalidates Z0.                                                                                                                                                                                                                                                                                                                                              | M            |
| **SAF-07** | Firmware shall never command motion into hard limits; all rapids shall decelerate into switch positions and soft limits shall bound normal operation (MOT-05, MOT-09).                                                                                                                                                                                                                                                                                                                                  | M            |

# 9. Power and Electrical Installation (PWR)

Requirements governing the mains and low-voltage electrical installation. These support the interlocks of Section 8 and the EMI immunity of ELE-04.

| ID     | Requirement                                                                                                                                                                                                                                                        | Priority |
|---|---|---|
| **PWR-01** | The DC power supply (24–48 V) shall be sized with ≥ 50% continuous current margin over the worst-case combined draw of motor, driver, and controller, and shall be fused on the mains side.                                                                            | M            |
| **PWR-02** | All mains wiring (power supply, router contactor circuit) shall comply with local wiring regulations. All exposed conductive parts, including the lift frame and electronics enclosure, shall be protectively earthed. The router circuit shall be RCD/GFCI-protected. | M            |
| **PWR-03** | The router relay/contactor shall be rated for the router's full-load current and the inrush of its universal motor (recommended ≥ 2× nameplate current, appropriate inductive utilisation category), with arc suppression across the contacts.                         | M            |
| **PWR-04** | Low-voltage control wiring shall be physically segregated from mains wiring, using distinct, keyed connectors such that miswiring is mechanically impossible.                                                                                                          | M            |
| **PWR-05** | Supply undervoltage (brownout) shall be monitored by the controller and reported to the fault handler (FLT-04).                                                                                                                                                        | S            |

# 10. Fault Handling and Recovery (FLT)

Requirements defining detection of, response to, and recovery from faults. The unifying rule: any event that casts doubt on the position reference invalidates Z0 (FW-09), and recovery is always explicit — the system never resumes motion on its own.

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                             | Priority |
|---|---|---|
| **FLT-01** | Stall / missed-step detection (e.g., Trinamic StallGuard or equivalent load measurement, or position feedback where fitted) shall be active during all programmed moves. A detected stall shall stop motion immediately, raise a fault, and invalidate Z0 (FW-09). Note: the selected TB6600 driver provides no stall detection — see accepted deviation DEV-01, Annex B.7. | M            |
| **FLT-02** | Before each touch-off the probe circuit shall be self-checked: a probe input already asserted (stuck or shorted probe) shall abort the touch-off with a distinct error rather than recording a false Z0.                                                                                                                                                                    | M            |
| **FLT-03** | A watchdog shall reset the controller to a safe state (motion stopped, router contactor open) on firmware lockup. A watchdog reset shall invalidate Z0 (FW-09).                                                                                                                                                                                                             | M            |
| **FLT-04** | Power loss or brownout during operation shall be treated as loss of position reference: on restart the system shall require homing and touch-off before any cycle or preset can run, and shall never resume an interrupted move or cycle automatically.                                                                                                                     | M            |
| **FLT-05** | Every fault shall be reported with a distinct, human-readable code/message, and shall require explicit operator acknowledgement before any further motion is accepted.                                                                                                                                                                                                      | M            |
| **FLT-06** | E-stop recovery: after E-stop release the system shall power up in a safe idle state (no motion, router contactor open), invalidate Z0, require re-homing and touch-off, and shall not resume the interrupted cycle automatically.                                                                                                                                          | M            |
| **FLT-07** | A fault log (at least the last 20 events with fault code) shall be retained across power cycles for diagnosis.                                                                                                                                                                                                                                                              | S            |

# 11. Environment and Duty (ENV)

| ID     | Requirement                                                                                                                                                                                                                                                                    | Priority |
|---|---|---|
| **ENV-01** | The system shall operate over 5–40 °C and ≤ 80% RH non-condensing, in workshop air laden with fine wood dust.                                                                                                                                                                      | M            |
| **ENV-02** | The control-electronics enclosure shall provide ingress protection of at least IP54 against fine wood dust, complementing the mounting requirement of MEC-06.                                                                                                                      | M            |
| **ENV-03** | The system shall sustain an 8-hour working session; motor and driver temperatures shall remain within their rated limits under the loading of ACC-04.                                                                                                                              | S            |
| **ENV-04** | Because thermal growth of the router body and bit over a long session can exceed the 0.02 mm drift budget, the firmware shall offer a configurable re-touch-off reminder (default: after 30 minutes of accumulated router run-time). The reminder shall be advisory, not blocking. | S            |

# 12. Maintainability and Calibration (MNT)

| ID     | Requirement                                                                                                                                                                                                                                  | Priority |
|---|---|---|
| **MNT-01** | Presets, calibration parameters, and configuration shall be stored in non-volatile memory and shall be exportable and restorable by the operator (e.g., SD card, USB, or serial transfer).                                                       | M            |
| **MNT-02** | An operator-executable calibration verification procedure (a subset of ACC-01/ACC-02) shall be provided that requires no disassembly. The documentation shall state a recommended interval (e.g., every 6 months and after any mechanical work). | M            |
| **MNT-03** | A lubrication and inspection schedule for the screw, guides, and dust protection shall be documented; these items shall be accessible without full disassembly of the lift.                                                                      | S            |
| **MNT-04** | Firmware shall be field-updatable with configuration and presets preserved; the firmware version shall be displayed at startup.                                                                                                                  | S            |

# 13. Acceptance Tests (ACC)

| ID     | Requirement                                                                                                                                                                                                                                                 | Priority |
|---|---|---|
| **ACC-01** | Repeatability: cycle 10 times between two heights 20 mm apart using standard approach; dial-indicator spread at each height ≤ 0.05 mm (target 0.02 mm).                                                                                                         | M            |
| **ACC-02** | Backlash masking: approach the same height 5 times from above and 5 from below with firmware compensation active; spread ≤ 0.02 mm.                                                                                                                             | M            |
| **ACC-03** | Touch-off: perform 5 simulated bit changes with re-zeroing; resulting cut-depth spread ≤ 0.05 mm.                                                                                                                                                               | M            |
| **ACC-04** | Drift: run the router loaded for 10 minutes at a fixed height; position drift ≤ 0.02 mm.                                                                                                                                                                        | M            |
| **ACC-05** | Cycles: demonstrate the standard scribe/rough/finish cycle, dovetail two-bit sequence, keyhole plunge cycle, and bit-change mode end-to-end on scrap stock.                                                                                                     | M            |
| **ACC-06** | Interlocks: verify the router cannot be powered while bit-change mode is active; verify E-stop kills router and lift; verify presets are locked after a bit change until touch-off.                                                                             | M            |
| **ACC-07** | EMI: with the router running, exercise jog and probe inputs for 5 minutes; zero phantom triggers.                                                                                                                                                               | M            |
| **ACC-08** | Fit repeatability: cut two dovetail test joints a week apart from the same stored preset; both shall achieve the same fit by feel/measurement.                                                                                                                  | S            |
| **ACC-09** | Fault response: safely obstruct carriage motion at reduced current to trigger a stall; verify immediate stop, fault report, and Z0 invalidation (FLT-01). Short the probe input before a touch-off; verify the touch-off aborts with a distinct error (FLT-02). | M            |
| **ACC-10** | Power-loss recovery: remove supply power mid-move; on restart verify all cycles and presets are blocked until homing and touch-off are completed, and that no move resumes automatically (FLT-04).                                                              | M            |
| **ACC-11** | E-stop recovery: actuate E-stop mid-cycle; verify router and lift power are removed, and that recovery requires re-homing and touch-off with no automatic cycle resumption (FLT-06, SAF-01).                                                                    | M            |
| **ACC-12** | Thermal re-zero: after 30 minutes of accumulated router run-time, verify the re-touch-off reminder appears (ENV-04) and that cut depth after re-zeroing meets the ACC-03 tolerance.                                                                             | S            |

# 14. Open Items for Next Phase

  - Confirm retrofit target (existing lift make/model) or new-build carriage design; measure actual carriage mass for final torque sizing.

  - Controller platform: decided (Rev G) — FluidNC on ESP32 with JC4827W543C touch HMI over UART. Remaining: FluidNC config.yaml pin map, HMI↔controller UART protocol definition, and panel layout including MPG placement and the rough/fine selector button (ELE-09).

  - Detail the firmware state machine for the canned cycles and interlock logic.

  - Decide whether closed-loop feedback (MOT-10) is included in the first build.

  - Select the electronics enclosure and connector hardware meeting PWR-04 and ENV-02.

  - Define the fault-code list and operator messages (FLT-05).

  - Close deviation DEV-01: upgrade to a stall-capable driver (e.g., TMC5160/closed-loop) or add an encoder (MOT-10) so FLT-01 and the stall portion of ACC-09 can be met.

  - Produce the bill of materials. (Wiring diagram: done — Figure 2, Annex B.9.)

# Annex A — Change Log

## A.1 Revision A → B

Every substantive change from Revision A is listed below. Requirements not listed are unchanged.

| Item             | Type  | Change and rationale                                                                                                                                                                                                                                                                                                                                            |
|---|---|---|
| **§1.2 Scope**       | Modified  | Coverage extended to power and electrical installation, fault handling, environmental, and maintainability requirements.                                                                                                                                                                                                                                            |
| **§1.4 Definitions** | Modified  | Added: stall / missed-step event, probe-plate offset, between-pass repositioning. Z0 definition updated for selectable reference surface (FW-11).                                                                                                                                                                                                                   |
| **MOT-06**           | Modified  | ±0.02 mm touch-off made credible: two-touch (fast find / slow confirm) procedure, spindle-orientation instruction or multi-touch averaging for fluted bits, and calibrated probe-plate offset (FW-10).                                                                                                                                                              |
| **ELE-01**           | Modified  | Torque margin now assessed at maximum commanded speed and supply voltage from the speed–torque curve, not holding torque — holding torque overstates torque available at the 300 RPM rapid.                                                                                                                                                                         |
| **ELE-05**           | Modified  | Cross-reference to contactor rating (PWR-03).                                                                                                                                                                                                                                                                                                                       |
| **ELE-08**           | New       | Display units (mm, 0.01 resolution), Z0-validity indication, active reference surface, and mode indication.                                                                                                                                                                                                                                                         |
| **FW-09**            | Modified  | Z0 invalidation list extended: E-stop, power loss/brownout, detected stall, watchdog reset — previously only bit-change, homing loss, and generic fault.                                                                                                                                                                                                            |
| **FW-10**            | New       | Calibrated probe-plate thickness offset.                                                                                                                                                                                                                                                                                                                            |
| **FW-11**            | New       | Selectable Z0 reference surface (table vs workpiece top).                                                                                                                                                                                                                                                                                                           |
| **OPS-01**           | Modified  | Explicit cross-reference to the SAF-03 between-pass repositioning exception.                                                                                                                                                                                                                                                                                        |
| **SAF-01**           | Modified  | Cross-reference to E-stop recovery behaviour (FLT-06).                                                                                                                                                                                                                                                                                                              |
| **SAF-03**           | Modified  | Resolved contradiction with OPS-01: Rev A prohibited all lift motion with the router powered except the keyhole moves, which made the standard cycle's between-pass height changes illegal. Rev B permits between-pass repositioning inside an active cycle on operator cycle-advance only; manual jog and preset recall remain prohibited with the router powered. |
| **§9 PWR (new)**     | New       | PWR-01–05: PSU sizing and fusing, earthing/RCD, contactor rating for universal-motor inrush, mains/SELV segregation, brownout monitoring.                                                                                                                                                                                                                           |
| **§10 FLT (new)**    | New       | FLT-01–07: stall detection, probe self-check, watchdog, power-loss recovery, fault reporting/acknowledgement, E-stop recovery, persistent fault log.                                                                                                                                                                                                                |
| **§11 ENV (new)**    | New       | ENV-01–04: operating environment, IP54 enclosure, 8-hour duty, thermal-growth re-zero reminder.                                                                                                                                                                                                                                                                     |
| **§12 MNT (new)**    | New       | MNT-01–04: config/preset backup-restore, operator calibration check, lubrication schedule, field firmware update.                                                                                                                                                                                                                                                   |
| **ACC-09–12**        | New       | Acceptance tests for stall/probe faults, power-loss recovery, E-stop recovery, and thermal re-zero.                                                                                                                                                                                                                                                                 |
| **Numbering**        | Editorial | Acceptance Tests now §13, Open Items now §14. MOT-05 cross-reference corrected from OPS-04 to OPS-11 (bit-change rapid). MEC-06 cross-references ENV-02.                                                                                                                                                                                                            |
| **§14 Open Items**   | Modified  | Added enclosure/connector selection (PWR-04, ENV-02) and fault-code list definition (FLT-05).                                                                                                                                                                                                                                                                       |

## A.2 Revision B → C

| Item           | Type   | Change and rationale                                                                                                                                                                                                                                                            |
|---|---|---|
| **§2.1 Baseline**  | Modified   | As-built driver noted (HLTNC TB6600, deviation DEV-01); supply range constrained to 24–36 V for the TB6600 — the generic 24–48 V range exceeds its absolute maximum (\~40–42 V).                                                                                                    |
| **ELE-01**         | Note added | Cross-reference to accepted first-build deviation DEV-01 (Annex B.7). Requirement itself unchanged.                                                                                                                                                                                 |
| **FLT-01**         | Note added | Cross-reference to DEV-01: TB6600 has no stall/missed-step detection. Requirement itself unchanged.                                                                                                                                                                                 |
| **Annex B**        | New        | As-built motor and driver configuration: 57HS76-3004A08 motor data, wire-to-terminal mapping, TB6600 terminal functions, DIP switch orientation and settings tables, final configuration (1/8 microstep, 2.8 A), optional 3.0 A setting, safety notes, and deviation record DEV-01. |
| **§14 Open Items** | Modified   | Added: close DEV-01 via stall-capable driver or encoder before FLT-01 / ACC-09 (stall portion) acceptance.                                                                                                                                                                          |
| **Annex A**        | Editorial  | Restructured into A.1 (Rev A→B) and A.2 (Rev B→C).                                                                                                                                                                                                                                  |

## A.3 Revision C → D

| Item             | Type | Change and rationale                                                                                                                                                                                                                |
|---|---|---|
| **§1.4 Definitions** | Modified | Added MPG (manual pulse generator) definition.                                                                                                                                                                                          |
| **ELE-07**           | Modified | Upgraded C → M: MPG handwheel is now the primary fine-adjustment input, as-built ZS61-type 100 PPR (Annex B.8).                                                                                                                         |
| **ELE-08**           | Modified | Display shall also indicate the active MPG scale.                                                                                                                                                                                       |
| **ELE-09**           | New      | Rough/fine selector button and MPG scaling (rough 0.1 mm/detent, fine 0.01 mm/detent, configurable); jog-class interlocks; automatic from-below re-approach after net-downward handwheel motion (preserves MOT-07 backlash discipline). |
| **ELE-10**           | New      | MPG electrical interface: 4-wire 5 V single-ended quadrature, shielded cable, 4× decoding with glitch filtering, EMI verification via ACC-07.                                                                                           |
| **FW-06**            | Modified | Sneak-up mode operable via MPG fine scale as well as increment buttons.                                                                                                                                                                 |
| **FW-12**            | New      | MPG trim on a recalled preset displayed separately; explicit save action required to write back — 'fine-tune between settings' without silent preset corruption.                                                                        |
| **SAF-03**           | Modified | MPG input explicitly listed among inputs inhibited while the router is powered.                                                                                                                                                         |
| **Annex B.8**        | New      | As-built MPG record: ZS61-series 60 mm, 100 PPR, 4-wire 5 V variant; wiring map and datasheet parameters. Explicit note: an MPG is not position feedback — DEV-01 remains open.                                                         |
| **§14 Open Items**   | Modified | Panel-layout item extended with MPG placement and rough/fine button.                                                                                                                                                                    |

## A.4 Revision D → E

| Item        | Type   | Change and rationale                                                                                                                                                                         |
|---|---|---|
| **§2 Overview** | New figure | Figure 1 added: full system architecture block diagram (operator panel, sensors, controller, drive chain, safety chain).                                                                         |
| **Annex B.1**   | Modified   | Motor model completed to HLTNC 57HS76-3004A08-D21-22 per the bench setup reference.                                                                                                              |
| **Annex B.3**   | Modified   | TB6600 supply rating confirmed as DC 9–42 V; installation range 24–36 V unchanged. ENA terminals recorded as unconnected as-built, with optional controller wiring for hard fault-disable noted. |
| **Annex A**     | Editorial  | Added A.4 (Rev D → E).                                                                                                                                                                           |

## A.5 Revision E → F

| Item           | Type  | Change and rationale                                                                                                                                                                                                                                         |
|---|---|---|
| **Annex B.9**      | New       | Figure 2 terminal-level wiring diagram: MPG level shifting (ESP32 not 5 V tolerant), TB6600 common-anode PUL/DIR wiring, motor coil colours, sensor inputs (proposed G32/G33/G25), relay-driven contactor coil, E-stop breaking mains live to PSU and contactor. |
| **§14 Open Items** | Modified  | Wiring-diagram item marked done (Annex B.9); BOM remains open.                                                                                                                                                                                                   |
| **Annex A**        | Editorial | Added A.5 (Rev E → F).                                                                                                                                                                                                                                           |

## A.6 Revision F → G

| Item             | Type  | Change and rationale                                                                                                                                                                                                                                   |
|---|---|---|
| **§1.4 Definitions** | Modified  | Added HMI (touch display) definition.                                                                                                                                                                                                                      |
| **§2.1 Baseline**    | Modified  | Controller decision recorded: split architecture — FluidNC ESP32 for motion, JC4827W543C ESP32-S3 touch display as HMI over UART. Rationale: FluidNC does not run on the ESP32-S3, and the display board's \~10 free IOs cannot carry the full pin budget. |
| **ELE-03**           | Modified  | Display and soft controls rendered on the touch HMI; safety-relevant controls remain physical.                                                                                                                                                             |
| **ELE-11**           | New       | Touch HMI requirement: UART link, non-safety-critical, no motion authority; HMI failure shall not initiate, sustain, or block stopping of motion.                                                                                                          |
| **Annex B.10**       | New       | As-built display record: JC4827W543C specs (ESP32-S3-N4R8, 480×272 IPS, NV3041A/QSPI, GT911 touch, 5 V/260 mA), UART wiring, 5 V-rail budget note.                                                                                                         |
| **Figures 1 & 2**    | Modified  | Touch HMI added to the architecture figure and to the wiring diagram (UART on GPIO16/17; panel buttons moved to spare GPIOs 21/22/13/14).                                                                                                                  |
| **§14 Open Items**   | Modified  | Controller-platform decision closed; added UART protocol definition to remaining work.                                                                                                                                                                     |
| **Annex A**          | Editorial | Added A.6 (Rev F → G).                                                                                                                                                                                                                                     |

# Annex B — Selected Drive Components and Configuration (As-Built)

This annex records the motor and driver actually procured for the first build, their verified wiring, and the driver configuration. It is a record of the as-built state, not a requirement set; where the selection deviates from Sections 5 and 10, the deviation is recorded in B.7.

## B.1 Motor

| Parameter               | Value                                                                                                                                                               |
|---|---|
| **Model**                   | HLTNC 57HS76-3004A08-D21-22 (full part number per setup reference; nameplate on motor body)                                                                             |
| **Frame / size**            | NEMA 23 (57 mm frame), 76 mm body length                                                                                                                                |
| **Type**                    | Bipolar, 4-wire, 2-phase hybrid stepper, 1.8°/step (200 full steps/rev)                                                                                                 |
| **Rated current**           | 3.0 A per phase                                                                                                                                                         |
| **Holding torque**          | Per manufacturer datasheet (typical for 57HS76-3004 class: ≈ 1.8–2.0 N·m — meets the ≥ 1.5 N·m baseline of §2.1). Confirm from datasheet for final torque sizing (§14). |
| **Resolution at 2 mm lead** | 0.01 mm per full step (satisfies MOT-01)                                                                                                                                |

## B.2 Motor Wire to Driver Terminal Mapping

Colour key printed on the motor nameplate; verified against the driver coil terminals.

| Motor wire | Driver terminal | Coil |
|---|---|---|
| **Red**        | A+                  | Coil A   |
| **Green**      | A−                  | Coil A   |
| **Yellow**     | B+                  | Coil B   |
| **Blue**       | B−                  | Coil B   |

To reverse rotation direction, swap the two wires of one coil (e.g., Red ↔ Green) or invert direction in firmware. A motor that buzzes or jitters without rotating has one wire on the wrong coil.

## B.3 Driver and Terminal Functions

Driver: HLTNC TB6600 single-axis stepper driver, opto-isolated step/direction inputs (supports the noise-immunity intent of ELE-04).

| Terminal    | Function                                                                                                                                                          |
|---|---|
| **PUL+ / PUL−** | Step pulse input (one microstep per pulse), from controller step output                                                                                               |
| **DIR+ / DIR−** | Direction input, from controller direction output                                                                                                                     |
| **ENA+ / ENA−** | Enable input. As-built: left unconnected (driver permanently enabled). Optionally wire to the controller so faults (FLT-03/FLT-06) can hard-disable the output stage. |
| **A+ / A−**     | Motor coil A (Red / Green)                                                                                                                                            |
| **B+ / B−**     | Motor coil B (Yellow / Blue)                                                                                                                                          |
| **VCC / GND**   | DC supply input, rated DC 9–42 V (per setup reference) — use 24–36 V for this installation; never connect 48 V                                                        |

## B.4 DIP Switch Orientation and Tables

On this HLTNC unit the switch block is printed “ON↓”: a lever pushed DOWN (toward the number row) is ON; UP is OFF. Always verify against the table printed on the driver case — TB6600 clones differ. Set switches only with power off.

Microstepping (S1–S3):

| Steps/rev             | S1 | S2 | S3 |
|---|---|---|---|
| **200 (full)**            | ON     | ON     | OFF    |
| **800 (1/4)**             | ON     | OFF    | OFF    |
| **1600 (1/8) — selected** | OFF    | ON     | OFF    |
| **3200 (1/16)**           | OFF    | OFF    | ON     |

Phase current (S4–S6):

| Current                                   | S4 | S5 | S6 |
|---|---|---|---|
| **2.5 A**                                     | OFF    | ON     | ON     |
| **2.8 A — selected**                          | OFF    | OFF    | ON     |
| **3.0 A — optional**                          | OFF    | ON     | OFF    |
| **3.5 A — do not use (exceeds motor rating)** | OFF    | OFF    | OFF    |

## B.5 Final Configuration

| Switch | Setting | Lever position |
|---|---|---|
| **1**      | OFF         | up                 |
| **2**      | ON          | down               |
| **3**      | OFF         | up                 |
| **4**      | OFF         | up                 |
| **5**      | OFF         | up                 |
| **6**      | ON          | down               |

Result: 1/8 microstepping, 1600 pulses/rev (800 pulses/mm at the 2 mm screw lead; 0.00125 mm per microstep) at 2.8 A per phase. Positional accuracy remains based on full steps per MOT-03 — microstepping here serves smoothness and noise only. 2.8 A (≈ 93% of the motor's 3.0 A rating) is deliberate: clone TB6600s run hot near their limit, and steppers rarely need full rated current. If more torque is required and the driver runs cool, move to the optional 3.0 A setting: S4 up (OFF), S5 down (ON), S6 up (OFF).

## B.6 Safety and Installation Notes

  - Change DIP switches only with the supply powered off.

  - Provide airflow or a heatsink at 2.8–3.0 A — an overheating TB6600 throttles or misbehaves, which presents as random stalls (and, per FW-09, would cost the position reference).

  - Never connect or disconnect motor wires with the driver powered — this destroys the output stage.

  - Verify the case-printed DIP table against B.4 before first power-up; clone units vary.

## B.7 Deviation Record

| Field          | Detail                                                                                                                                                                                                                                                                 |
|---|---|
| **ID**             | DEV-01                                                                                                                                                                                                                                                                     |
| **Requirement(s)** | ELE-01 (Trinamic-class/industrial driver), FLT-01 (stall detection)                                                                                                                                                                                                        |
| **Deviation**      | First build uses an HLTNC TB6600, a hobby-class driver with no StallGuard-type load measurement, so sensorless stall detection cannot be implemented.                                                                                                                      |
| **Disposition**    | Accepted for the first build. Interim mitigations: conservative feeds, 30%+ torque margin verified at speed, ACC-01–ACC-04 repeatability tests, and strict FW-09 Z0-invalidation on any suspected fault. The stall-simulation portion of ACC-09 is deferred until closure. |
| **Closure path**   | Replace with a stall-capable driver (e.g., TMC5160-class or closed-loop) or fit an encoder (MOT-10). Tracked in §14 Open Items.                                                                                                                                            |

## B.8 MPG Handwheel (Fine-Adjustment Input)

Device: ZS61-series electronic handwheel (60 mm dial), 100 PPR incremental encoder, 4-wire 5 V single-ended voltage-output variant (datasheet family ZS61-5E100S). Implements ELE-07/ELE-09/ELE-10 and the sneak-up input of FW-06.

| Parameter          | Value (datasheet)                                                      |
|---|---|
| **Resolution**         | 100 PPR (100 detents per revolution), quadrature A/B, 90° phase            |
| **Supply / interface** | 5 V DC; 4-wire single-ended: VCC, 0 V, A, B (no A̅/B̅, no Z index)         |
| **Response frequency** | 0–5 kHz                                                                    |
| **Output levels**      | VH ≥ 0.7 × VCC, VL ≤ 0.5 V; rise/fall ≈ 5 µs                               |
| **Environment**        | IP44; operating −10 to +60 °C; anti-vibration 19.6 m/s² (10–200 Hz)        |
| **Mechanical**         | Aluminium alloy body; starting torque 0.015–0.1 N·m (distinct detent feel) |

| Handwheel wire | Signal | Controller connection |
|---|---|---|
| **Red**            | VCC        | \+5 V supply              |
| **Black**          | 0 V        | Ground                    |
| **Green**          | A          | Quadrature input A        |
| **White**          | B          | Quadrature input B        |

Installation notes: the interface is single-ended, so use shielded cable (shield grounded at the controller end only), route away from mains and motor wiring, and verify against phantom counts with the router running (ELE-10, ACC-07). At the fine scale, 5 detents = one 0.05 mm sneak-up increment; one full wheel revolution = 1 mm (fine) or 10 mm (rough).

**Important: this device is an operator input (manual pulse generator), not position feedback. It does not measure carriage or bit position and cannot detect stalls or missed steps. Deviation DEV-01 therefore remains open; closure still requires a stall-capable driver or a motor/carriage-mounted encoder (MOT-10).**

## B.9 Wiring Diagram (As-Built)

Figure 2 shows every terminal-level connection of the first build. GPIO pin numbers are proposed FluidNC assignments and are finalised in config.yaml when the §14 controller-platform decision closes. Key points: the MPG's 5 V outputs pass through a level shifter because ESP32 inputs are not 5 V tolerant; the TB6600 step/direction inputs are wired common-anode (PUL+/DIR+ on the +5 V rail, GPIO sinking PUL−/DIR−); ENA± is unconnected as-built; and the E-stop breaks the mains live feeding both the PSU and the router contactor, satisfying SAF-01 in hardware.

![Router lift terminal-level wiring diagram](./media/6405ae199913514fcaf4131500358a4f35a16d49.png "Figure 2")

*Figure 2 — Terminal-level wiring diagram (as-built, Rev G)*

## B.10 Touch HMI (Operator Display)

Device: Guition JC4827W543C — 4.3-inch IPS touch display module used as the operator HMI (ELE-11), documented from the vendor's GUITION-DISK share and public sources.

| Parameter  | Value                                                                                                           |
|---|---|
| **MCU**        | ESP32-S3-WROOM-1-N4R8: dual-core 240 MHz, 512 KB SRAM, 8 MB PSRAM (OSPI), 4 MB flash (QSPI), Wi-Fi + Bluetooth      |
| **Display**    | 4.3-inch IPS, 480 × 272, 65K colour (RGB565), NV3041A driver on 4-bit QSPI; PWM-dimmable backlight                  |
| **Touch**      | Capacitive, GT911 controller on I²C                                                                                 |
| **Power**      | 5 V, ≈ 260 mA — fed from the 5 V rail; size the DC-DC buck for ≥ 1 A total (HMI + controller + MPG + level shifter) |
| **Interfaces** | UART to motion controller (JST 1.25 connectors); TF-card slot; \~10 free GPIOs                                      |
| **Mechanical** | 120 × 70.2 mm module, panel-mountable                                                                               |
| **UI stack**   | LVGL (v8.4) with Arduino\_GFX / ESP-IDF; vendor examples available (see §14 UART protocol task)                     |

Architecture rationale: FluidNC does not support the ESP32-S3, so this board cannot host the motion firmware; and its \~10 free IOs cannot carry the machine's full pin budget. It therefore serves as HMI only, over UART (controller GPIO16/17 proposed, 3.3 V logic both sides — no level shifting required). Per ELE-11 the HMI carries no motion authority: if it crashes or disconnects, the motion controller's interlocks, limits, and E-stop chain are unaffected.
