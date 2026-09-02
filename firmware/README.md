# Motion controller — stock FluidNC

This directory contains **no source code**. The motion controller runs an unmodified FluidNC
binary; `config.yaml` is the entire machine definition.

That is deliberate and worth protecting. Homing, soft limits, hard limits, probing and step
generation are the safety-critical parts of this machine, and keeping FluidNC stock means they
are not ours to get wrong. Any proposal that requires editing FluidNC's source forfeits this.

---

## Flashing and configuration

1. Flash stock FluidNC to the ESP32 (**classic ESP32, not S3** — FluidNC does not run on the S3).
2. Upload `config.yaml` to the board's filesystem — over USB with `$LocalFS/Upload`, or via the
   FluidNC web UI if WiFi is enabled.
3. `$Config/Filename=config.yaml` if it is not the default.
4. `$$` to confirm it parsed. A YAML error leaves the board in a safe non-configured state rather
   than running with half a machine definition.

Record the FluidNC version actually flashed here when it is done: `__________`

---

## ⚠ Before first power-up

Five things that are destructive or silently wrong if got wrong. All are in
`docs/WIRING-RevH.svg` too.

| # | Check |
| --- | --- |
| 1 | **PSU is 24–36 V.** A 48 V supply destroys the TB6600 instantly (abs max ≈40–42 V) |
| 2 | **TB6600 common anode is +3.3 V, not +5 V.** At 5 V the input opto never fully turns off → missed steps at rapid → silent depth error under DEV-01 |
| 3 | **Limit sensors are NPN, never PNP.** A PNP sensor sources 24 V into the GPIO. `LJ12A3-4-Z/BY` = NPN NC; any `/A…` suffix is PNP |
| 4 | **Switches wired NC**, so a broken wire faults the machine rather than silently disabling the limit |
| 5 | **Two red buttons, two meanings.** The E-stop mushroom kills mains; STOP is a flush feed-hold button. Mount them apart |

---

## ⚠ Unresolved: the foot switch needs both edges

**This is the one genuine problem found while writing the config, and it is not yet solved.**

The agreed behaviour (Q39) is **hold to plunge, release to retract** — dead-man, so stepping off
returns the cutter. That needs two events: press *and* release.

FluidNC's `macro0_pin` fires a macro when the pin is **asserted**. Whether it does anything on
release is unverified, and if it does not, a macro pin alone cannot implement dead-man behaviour.

There is a second problem even for the press half. A macro is a fixed G-code string, but the
plunge target is a per-job value that lives in the HMI. FluidNC cannot know it.

### The plan, pending verification

**Press half.** The HMI rewrites the macro whenever the target depth changes:

```
$Macro0=G90 G21 G1 Z<target> F120
```

The foot switch then plunges **locally on the motion board**, with no link involvement and no
latency — which is exactly why the switch belongs on this board.

**Release half.** Wire the same foot-switch contact to a **spare MCP23017 input on the HMI**
(A6 — ten I/O are free). The HMI sees the release edge and sends the park move. One switch, two
readers, no ambiguity about which owns the plunge.

### Consequences to accept or reject at review

- If the link is dead, the plunge still works but the automatic retract does not. Link loss
  already triggers a feed hold, so the cutter stops — but it stops **at depth**, not retracted.
- That is weaker dead-man behaviour than a single-board design gives. It is a direct cost of the
  split architecture and should be judged deliberately, not discovered on the bench.

### Alternatives if verification rules the mirrored approach out

1. Move the foot switch entirely to the HMI expander — both edges are then trivial, but every
   plunge crosses the link and gains latency.
2. Change the semantics to press-down / press-up toggle — solvable with one edge, but it is a
   mode, and losing track of it means the cutter stays up when you think it is down. Q39
   deliberately rejected this.

---

## Items to verify against the installed release

Everything in `config.yaml` marked ⚠, plus these. All are from working knowledge of FluidNC
rather than from the docs of the specific build in hand.

| # | Item | Why it matters |
| --- | --- | --- |
| 1 | `uart1:` / `uart_channel1:` key names | Without a second channel the HMI shares the USB port and the debug console is lost |
| 2 | `report_interval_ms` exists and reaches ~10 Hz | The HMI's whole display depends on it; fallback is polling `?` |
| 3 | Soft-limit envelope sign convention | We home negative and work positive — the less common orientation. Prove with `$J=` at both ends |
| 4 | `macro0_pin` edge behaviour | Decides the foot-switch question above |
| 5 | Macro length limits, and whether `$Macro0` can be rewritten over the wire | The press-half plan depends on it |
| 6 | Homing pull-off failure raises a distinct alarm code | So the HMI can say "stuck switch", not just "limit" |
| 7 | `relay_spindle` reports non-zero `S` in status | The ROUTER LED depends on reading it |

---

## Commissioning: measuring `steps_per_mm`

**`steps_per_mm: 800` in `config.yaml` is a placeholder, not a measurement.** It assumes a 2 mm
lead screw described in RevG §2.1 for a machine that was never built.

1. Fit a dial indicator (0.01 mm) against the carriage.
2. `$J=G91 G21 Z10 F300` and note indicated travel — or command a known number of motor
   revolutions, which is more precise.
3. `steps_per_mm = 1600 / (mm travelled per motor revolution)`
4. Update `config.yaml`, re-upload, and repeat to confirm.
5. Record the measured value and date here: `__________`

Until this is done, every depth this machine cuts is wrong by an unknown factor — and wrong in a
way nothing detects, because DEV-01 leaves no stall sensing to contradict a bad number.

---

## Settled values and where they came from

| Setting | Value | Decided in |
| --- | --- | --- |
| `steps_per_mm` | **800 — PROVISIONAL** | placeholder, must be measured |
| `max_rate_mm_per_min` | 720 (12 mm/s) | Q14 |
| `acceleration_mm_per_sec2` | 100 | Q16 |
| `max_travel_mm` | 90 — provisional, set by the lift body | MEC-01 |
| `idle_ms` | 255, never disable | Q17 |
| Homing seek / feed | 600 / 60 mm/min | Q14–16 |
| `pulloff_mm` | 2.0 mechanical, ~3.0 inductive | Q12 |
| Positive direction | Bit rising, home at bottom | Q19 |
| Microstepping | 1/8, 1600 pulse/rev | Q18 |
| `spinup_ms` | 2500 | SAF-03 gate |
| `must_home` | true, no exceptions | Q11 |

Plunge feed (2 mm/s, 120 mm/min) is not in this file — it is a `G1 F` value the HMI sends per
move, since it varies by cycle.
