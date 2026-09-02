# Workshop visit — lift body survey

One trip should be enough. **Item 2 is the one that matters most** — it unblocks `steps_per_mm`,
`SCREW_LEAD_MM`, and every depth figure in the design.

---

## 1 · Identify it

- [ ] Brand and model, from the casting, a plate, or the insert plate underside
- [ ] Any serial or part number
- [ ] Photograph: whole lift, the crank/drive end, the underside, the plate

## 2 · Screw lead ★ THE CRITICAL MEASUREMENT

Everything depends on this. Two ways, do both if you can:

**Turns method** (no special tools):
- [ ] Mark the crank and a fixed reference
- [ ] Wind the carriage to the bottom, then turn **exactly 10 full turns** up
- [ ] Measure the travel with calipers — record it: `_______ mm`
- [ ] Lead = travel ÷ 10

**Direct method:**
- [ ] If the screw is visible, measure thread pitch with calipers or a pitch gauge

Likely values: 2.0, 2.5, 3.0 mm, or imperial (1/8" = 3.175 mm, 1/10" = 2.54 mm). If it comes
out near an imperial number, say so — that changes `steps_per_mm` to a non-round figure.

> With 1/8 microstepping the motor gives 1600 pulses/rev, so
> `steps_per_mm = 1600 ÷ lead_mm`. A 2 mm lead gives the 800 currently assumed;
> a 3.175 mm lead would give 504.

## 3 · Drive interface — how the motor attaches

- [ ] Does the crank/handle come off? How is it retained — grub screw, pin, circlip?
- [ ] Shaft **diameter**: `_______ mm`
- [ ] Shaft **form**: round / hex / square / keyed / D-flat — and across-flats if not round
- [ ] Free shaft **length** once the handle is off: `_______ mm`
- [ ] Is there anything to bolt a motor bracket to — a flange, boss, tapped holes?
- [ ] Photograph the drive end with the handle removed

This decides the coupling and the motor mount, which are the only fabrication in the build.

## 4 · Travel

- [ ] Full travel, hard stop to hard stop: `_______ mm`  (MEC-01 wants ≥75 mm)
- [ ] At the **bottom** of travel, is the bit fully below the table surface?
- [ ] At the **top**, is there enough clearance to change a bit?

## 5 · Self-locking check

- [ ] Wind to mid-travel, let go of the crank. Does the carriage hold, or creep down?

Holds = self-locking, as MEC-02 assumes, and the design is fine. Creeps = the motor must stay
energised, and `idle_ms: 255` becomes mandatory rather than a preference.

## 6 · Backlash

- [ ] Wind up, stop. Reverse the crank and count how much free rotation before the carriage moves
- [ ] Rough figure: `_______ degrees` or `_______ mm of travel`

Informs whether MOT-07's approach-from-below is sufficient on its own.

## 7 · Switch mounting

- [ ] Somewhere fixed to mount two microswitches, and something on the carriage to trip them?
- [ ] Room for a **hard mechanical stop just beyond each switch**?
- [ ] Photograph candidate spots

## 8 · The router itself

- [ ] Make and model
- [ ] Collet size(s)
- [ ] Nameplate **amps or watts** — sizes the contactor (PWR-03 wants ≥2× nameplate)
- [ ] Approximate mass of router + carriage: `_______ kg`  (§2.1 assumed 3–6 kg)

## 9 · Table

- [ ] Insert plate opening size
- [ ] Where could the operator panel mount, and where would the handwheel fall to hand?

---

## What changes when you get back

| Measurement | Updates |
| --- | --- |
| Screw lead | `firmware/config.yaml` `steps_per_mm`, `hmi/include/config.h` `SCREW_LEAD_MM` |
| Travel | `config.yaml` `max_travel_mm` |
| Self-locking? | Confirms or forces `idle_ms: 255` |
| Router amps | Contactor rating in `docs/BOM.md` |
| Shaft form | Coupling and motor-mount design — the only fabrication |
| Mass | Confirms the 57HS76 is oversized as expected |

Also closes the last eight open questions in `docs/DESIGN-QA.md` (A2–A7, Q9, Q10, Q12).
