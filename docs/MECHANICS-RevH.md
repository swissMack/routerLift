# Mechanics — lift selection and drive design

Document: RTL-MECH-001 · Rev A · 2 September 2026

Records how the lift body was chosen and how the stepper couples to it. **Nothing here is
bought yet**, and two questions are outstanding with the manufacturer.

---

## 1. Where this started

The design assumed a T8 ACME screw with a 2 mm lead, from RevG §2.1 — a description of a machine
that was never built. The mechanics were therefore the critical path and every depth figure in the
project was resting on an invented number.

---

## 2. Rejected — JoinTech SmartLift Digital

A SmartLift Digital was inspected. It is **not a suitable host**, for four reasons:

| Finding | Consequence |
| --- | --- |
| Drive is a **nylon pinion on a large ring gear**, not a lead screw | A stepper does not feel resistance and stop. It would strip the gear |
| That gear is a **known failure point** — an owner stripped it in year two | |
| **JoinTech/iTec is out of business** | No spares. Stripping it scraps the lift |
| Drive input is a **hex socket on the top face** | A motor there sits on the work surface |
| Reported as "never really smooth"; the Wixey DRO lost zeroing within a year | Poor basis for a precision machine |

Source: LumberJocks thread *"Not the router lift to buy"* (2011–2017). One detailed failure report
plus corroboration that spares are unavailable. Not a large sample, but enough — the mechanism
description alone disqualifies it.

**The transferable lesson:** a hand-cranked mechanism is designed around an operator who stops
pushing when something binds. A stepper does not. Any host must survive being driven by something
that cannot feel.

---

## 3. Selected — sauter Fräslift FML-P (pending purchase)

German manufacturer, currently trading, full accessory and spares ecosystem.

| Spec | Value | Consequence |
| --- | --- | --- |
| **Travel per revolution** | **1.5 mm** | `steps_per_mm = 1600 ÷ 1.5 =` **1066.67** |
| Full-step resolution | **0.0075 mm** | **Beats MOT-01's ≤0.01 mm** |
| **Max travel** | **65 mm** | ⚠️ **Below MEC-01's ≥75 mm** — see §6 |
| Height adjustment | 5 mm hex **from above** | Not usable for a motor; see §4 |
| Spindle lock | Knurled clamp **under the table** | Clamps a **guide column**, not the screw |
| Clamping neck | Ø 43 mm | European spindle motors — AMB, Suhner, Mafell |
| Max router | 5 kg, 1,100 W | Sizes the contactor (PWR-03) |
| Insert plate | 306 × 229 × 9 mm, R6 corners | Table cutout |
| Lift weight | 2.9 kg | Carriage ≈ 8 kg with motor |
| Price | €378 new · **€329 B-stock** (`II-SA-FML-P`) | B-stock is the sensible buy for a unit being modified |

**The Ø 43 mm clamping neck is a quiet advantage.** It takes continuous-duty spindle motors with
soft start and electronic speed control — the same motors CNC routers use — rather than a
handheld router with a trigger.

---

## 4. The drive interface

The nominal adjustment is a 5 mm hex through the insert plate from above, which is unusable: a
motor there would sit on the work surface. **But the lower end of the spindle carries its own hex
socket**, visible in the manufacturer's underside photograph.

**The screw rotates in place; the nut travels with the carriage.** Confirmed two ways — the top
hex is operated through the *fixed* insert plate, so the drive end cannot move vertically, and the
underside photograph shows the screw driving the router mount up and down.

That gives the good case: **a rigid bracket below the lift, coupled directly to the lower hex.**
No sliding coupling, no right-angle drive, no dismantling of the mechanism.

The spindle lock clamps a guide column rather than the screw, so it will not foul anything mounted
on the screw end. With a motor fitted it becomes either a redundant control to remove, or a
deliberate bit-change interlock to keep.

### Drive train

| Part | Choice | Reasoning |
| --- | --- | --- |
| Coupling | **Zero-backlash jaw (spider) or Oldham** | Backlash goes straight into MOT-02 repeatability. **No universal joints** |
| Drive stub | Hex bit stock into the coupling bore | ⚠️ **Measure the lower socket** — the 5 mm figure is for the upper one |
| Bracket | Rigid, below the lift, coaxial with the screw | The coupling absorbs residual misalignment; it cannot rescue a bad bracket |

**Speed check:** 12 mm/s ÷ 1.5 mm = 480 rpm = 12,800 steps/s at 1/8 microstepping. Comfortable
for the TB6600 and for FluidNC's step generator.

---

## 5. Two findings that change the electrical design

### 5.1 Turn the driver current down — the motor is dangerously oversized

```
F = 8 kg × 9.81                    = 78.5 N
T = F × lead / (2π × η)              η ≈ 0.25, fine trapezoidal lead
  = 78.5 × 0.0015 / 1.571
  = 0.075 N·m        →  call it 0.15 N·m with allowance
```

The 57HS76 delivers about **2 N·m**. That is better than a **10× margin, and it is a hazard rather
than a comfort**: a motor with far more torque than the mechanism needs, with no stall detection
(DEV-01), will destroy the lift if it ever drives into a hard stop.

**Action: set the TB6600 DIP switches to 1.0–1.4 A/phase, not 2.8 A.** That retains a 5–7× margin
and buys three things — far less destructive potential, much less heat (relevant because
`idle_ms: 255` draws current continuously, against ENV-03), and a quieter machine.

This supersedes Annex B.5's 2.8 A setting, which was chosen when the mechanics were unknown.

### 5.2 It is self-locking — MEC-02 holds

A 1.5 mm lead on a ~12 mm screw gives a lead angle of about **2.3°**, well below the ~5.7°
friction angle for steel on bronze. The carriage will not back-drive unpowered.

Consequence: **`idle_ms: 255` becomes a preference rather than a necessity.** If the motor runs hot
during the ACC-04 ten-minute drift test, switching to a timeout is now safe.

---

## 6. Open items

| # | Item | Why it matters |
| --- | --- | --- |
| 1 | **Permissible spindle torque** — asked of Sauter | Sets the current limit and whether a torque limiter is needed |
| 2 | **Is the lower hex also 5 mm?** — asked of Sauter | Sizes the drive stub |
| 3 | **MEC-01 travel: 65 mm vs the specified ≥75 mm** | Every Sauter model shares 65 mm, so this is not avoidable by model choice. MEC-01 was written for an imaginary machine — the requirement probably needs revising down, but that must be a deliberate decision recorded in Rev H |
| 4 | Motor bracket attachment point | Needs the lift in hand |
| 5 | Endstop mounting and trip flag | Needs the lift in hand |
| 6 | Keep or remove the spindle lock | Redundant control, or bit-change interlock |

---

## 7. Values now carried in the code

All marked provisional until the lift is bought and measured. They now derive from a
**published manufacturer specification** rather than an invention, which is a real improvement —
but a measurement still beats a datasheet.

| Where | Value | Was |
| --- | --- | --- |
| `firmware/config.yaml` `steps_per_mm` | **1066.67** | 800 |
| `firmware/config.yaml` `max_travel_mm` | **65** | 90 |
| `hmi/include/config.h` `SCREW_LEAD_MM` | **1.5** | 2.0 |
| TB6600 DIP current | **1.0–1.4 A** | 2.8 A |

The commissioning measurement in `firmware/README.md` still applies and is still the authority:
wind a known number of motor revolutions against a dial indicator and compute
`steps_per_mm = 1600 ÷ (mm per revolution)`.
