# routerLift — Design and Implementation Plan

**Document** RTL-DESIGN-001 · **Revision** H (draft) · **Date** 2 September 2026 · **Status** Issued for first review

| | |
| --- | --- |
| **Supersedes** | Requirement Specification RevG (RTL-SPEC-001), Annexes B.8–B.10 |
| **Companion documents** | `SCHEMATIC-RevH.svg`, `WIRING-RevH.svg`, `PINOUT.svg`, `ARCHITECTURE-DIAGRAM.svg`, `BOM.md`, `DESIGN-QA.md` |
| **Repository** | `github.com/swissMack/routerLift` @ `c46ee84` |
| **Purpose of this issue** | Review of the design before any firmware is written and before mechanical parts are ordered |

---

## 1. Purpose and status

This document describes the design and implementation plan for an ESP32-based automated router lift, and is issued for first review. **No firmware has been written and no mechanical parts have been bought.** The electronics are largely in hand; the machine itself does not yet exist.

The design departs from Requirement Specification RevG in several recorded ways. Those departures are listed in section 5 and are the most important thing for a reviewer to challenge.

### What is settled

The controller architecture, the I/O split, the communication protocol, the safety model, and the physical control panel are all decided and documented here.

### What is open

The mechanics. Which commercial lift body will be motorised is unknown, and that decision sets the screw lead, the travel and the achievable resolution. **`steps_per_mm` is currently a placeholder derived from an assumption, not a measurement.**

---

## 2. Executive summary

A single ESP32 cannot do this job. FluidNC — the motion firmware chosen for its proven homing, soft limits, probing and jog handling — does not run on the ESP32-S3, and the ESP32-S3 display board's RGB parallel panel consumes 20 GPIOs, leaving it unable to carry the machine's pin budget. The design therefore uses **two controllers**:

- A **standard ESP32 running stock FluidNC** for all motion and all safety enforcement. It is configured entirely by one YAML file; we write no code for it.
- An **ESP32-S3 on a 4.3" touch panel** as the operator interface, running our firmware. It acts as a GRBL sender over a UART link.

The governing principle is that **the HMI proposes and FluidNC disposes**. Soft limits, hard limits, homing and probing are enforced on the motion side. A fault in our HMI firmware can produce a wrong cutting depth; it cannot produce an unsafe move. The emergency stop is mains-rated hardware in series with the supply and is invisible to both controllers.

The design is more capable than the commercial FXBB FräsLift V3 it is modelled on — multi-pass cycles, probing, router interlocks, plural fault codes — but is honestly inferior in three respects: handwheel latency, a link-loss failure mode a single-board design cannot have, and the need for a computer to change commissioning values. These are discussed in section 11.

---

## 3. Architecture

![Architecture — ownership, the safety boundary, and what crosses the link](.render/ARCHITECTURE-DIAGRAM.png){width=10.05in}

### 3.1 Why two controllers

| | |
| --- | --- |
| **Forced by** | FluidNC does not run on the ESP32-S3, and the S3's RGB panel consumes 20 GPIOs |
| **Gained** | Motion stays a stock, proven binary configured by one file. Homing, limits, probing and jogging are not ours to get wrong |
| **Paid** | Handwheel latency through a UART hop, and a link-loss failure mode that a single-board design cannot have |

### 3.2 The division of responsibility

**The HMI (ESP32-S3) decides what should happen.** It holds the cut depth, the pass schedule, the presets, and the Z0-validity state. It converts handwheel detents and button presses into GRBL commands.

**FluidNC decides whether it may happen.** It rejects any move outside the commissioned envelope regardless of what the HMI asked for, enforces limits in the stepper interrupt, and continues to work standalone if the HMI is dead.

**The E-stop crosses neither boundary.** It is an NC mains contact breaking the live feed to both the PSU and the router contactor. Neither controller can see it, override it, or fail to honour it.

---

## 4. Decisions taken

| Decision | Choice | Rationale |
| --- | --- | --- |
| Controller architecture | Split: FluidNC ESP32 + ESP32-S3 HMI | Forced — see 3.1 |
| Old firmware | Retired to `legacy/`, kept unbuilt as reference | Preserves menu structure and NVS patterns worth porting |
| Display board | ESP32-4827S043, RGB parallel | The board in hand. **Not** what RevG records |
| I/O split | Operator inputs on the S3; every safety-relevant input on FluidNC | Keeps safety off the UART link |
| UART protocol | GRBL / G-code, HMI as sender | Keeps FluidNC stock — no fork, no custom build |
| Soft limits | Commissioning-only in `config.yaml` | An operator must not be able to widen their own envelope |
| Motor idle current | Permanently energised (`$Stepper/IdleTime = 255`) | Maximum holding stiffness; ENA wired so this stays changeable |
| Foot switch | Hold to plunge, release to retract | Dead-man behaviour |
| Link loss mid-cycle | Immediate feed hold, Z0 invalidated | No auto-resume; re-home and re-probe |
| Canned cycles in v1 | All four | Owner's decision, full spec scope |
| Mechanics | Motorise a commercial manual lift body | Rigidity and guides bought in rather than engineered |

---

## 5. Deviations from RevG — for review

These are the changes a reviewer should scrutinise most closely. Each was made for a stated engineering reason, and each will need a Rev H amendment to the specification.

| # | RevG says | This design does | Why |
| --- | --- | --- | --- |
| 1 | Display is a JC4827W543C with NV3041A QSPI panel (Annex B.10) | **ESP32-4827S043 with ILI6485 RGB parallel panel** | The board in hand. The RGB bus takes 20 GPIOs versus ~6 for QSPI, which drives the whole pin strategy and forces sacrificing the TF card |
| 2 | Handwheel is a ZS61, 60 mm dial (Annex B.8) | **ZS80, 80 mm dial** | The unit in hand. Same 100 PPR and electricals, so scaling is unchanged; rim travel per detent improves from 1.88 mm to 2.51 mm |
| 3 | HMI is display-only, no motion authority (ELE-11) | **HMI owns the handwheel, buttons and cycle logic** | A display-only HMI cannot host the operator controls the machine needs. ELE-11's *safety* invariant is preserved; its *scope* wording is not |
| 4 | TB6600 common anode at +5 V (Annex B.9) | **+3.3 V** | At 5 V the ESP32's logic high leaves 1.7 V across the input optocoupler, above its LED drop, so it never fully turns off. Causes missed steps at rapid — silent depth error under DEV-01 |
| 5 | `ENA±` not connected (Annex B.9) | **Wired to GPIO 14** | Without it the motor holds 2.8 A/phase indefinitely with no way to de-energise, against ENV-03 |
| 6 | MPG on FluidNC GPIO 34/35 (Annex B.9) | **HMI GPIO 11/12 behind a 74HCT14** | Follows the I/O split. Flips `MPG::SIGNALS_INVERTED` to `false`, since a two-stage Schmitt buffer is non-inverting where the assumed PC817 optos were not |
| 7 | Soft limits operator-editable (legacy `Settings.cpp`) | **Commissioning-only** | Prevents an operator widening their own protection, and keeps a safety-relevant setting out of HMI write access |

**Consequential reservation:** GPIO 34 and 35, freed by deviation 6, are reserved rather than reused — 35 as `DRIVER_ALARM`, so that closing DEV-01 later is a configuration edit and not a rewire.

---

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## 6. Pin assignment

![Pin assignment for both controllers. Greyed pins are committed by the display board and unavailable](.render/PINOUT.png){width=9.88in}

The asymmetry is the point: the motion controller has roughly nine spare GPIOs, while the display board has three, one of which is a boot strap. This is why the panel buttons go on an I²C expander rather than on pins.

---

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## 7. Schematic

![Complete schematic, blocks A–H](.render/SCHEMATIC-RevH.png){width=9.12in}

---

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## 8. Wiring and installation

![Physical wiring, cable schedule, and pre-power-up checks](.render/WIRING-RevH.png){width=9.53in}

---

## 9. Endstops, limits and safety

Three independent layers, owned by three different things. Nothing in the HMI appears in any of them.

| Layer | Mechanism | Owner |
| --- | --- | --- |
| E-stop | NC mains contact breaking L to PSU and contactor | Hardware only — no GPIO, no firmware path |
| Hard limits | `limit_neg_pin: gpio.33`, `limit_pos_pin: gpio.25` | FluidNC — alarm state, motion halted in the ISR |
| Soft limits | Envelope from `mpos_mm` and `max_travel_mm` | FluidNC — move rejected before execution |

### 9.1 Three tiers of limit

A distinction worth holding clearly, because conflating them leads to a design mistake:

| Tier | Set by | Where | Changes |
| --- | --- | --- | --- |
| Hard limits | Physical switch position | Bolted to the machine | Never |
| Soft limits | Commissioning — travel and home reference | `config.yaml` | Once, at build |
| Job ceilings | Operator — presets and a teachable ceiling | HMI, in NVS | Every job |

Job ceilings can only ever be *narrower* than the commissioned envelope, so the operator retains the useful affordance without being able to weaken the protection.

### 9.2 Why the limits carry unusual weight here

DEV-01 records that the TB6600 has no stall detection, so FLT-01 is unimplementable on this build. Open-loop stepping with no stall sensing lets position error accumulate **silently** — a step missed during a heavy plunge does not announce itself, it quietly shifts everything after it. Soft limits cannot catch this, because FluidNC trusts its own step count.

**The bottom switch is the only thing that ever discovers the drift.** Two consequences: the switches are primary protection here rather than a backstop, and the Z0-invalidation discipline of FW-09 must be strict, because a limit hit tells you something slipped but never how much.

### 9.3 Dual sensor support

Both mechanical and inductive switches have been bought, and the design accepts either with no configuration change. Wired normally-closed, both present identically:

| | Idle | At limit | Wire break |
| --- | --- | --- | --- |
| Mechanical NC, COM→GND | contact closed, LOW | opens, pull-up, HIGH | floats HIGH — reads as triggered |
| Inductive NPN NC | transistor conducting, LOW | turns off, pull-up, HIGH | floats HIGH — reads as triggered |

Both fail safe; for the inductive sensor a severed *supply* wire also faults the machine. One common conditioning circuit — 10 kΩ series, 4k7 pull-up to 3V3, BAT54S clamp, 100 nF — serves all five inputs, satisfies ELE-04's debounce and EMI requirement in hardware, and survives an accidentally fitted PNP sensor that would otherwise destroy the ESP32.

---

## 10. Physical control panel

Six buttons with short and long press, giving twelve functions, deliberately split across both boards.

| Button | Board | Short press | Long press |
| --- | --- | --- | --- |
| **STOP** | **FluidNC GPIO 21** (`feed_hold_pin`) | Feed hold; router stays on | Soft reset |
| CYCLE START | MCP23017 A0 | Start cycle / advance pass | — |
| ROUTER | MCP23017 A1 | Toggle router power | — |
| BIT CHANGE | MCP23017 A2 | Rapid to top, lock out | Exit, forcing re-probe |
| ZERO | MCP23017 A3 | Probe touch-off | Set zero here, no probe |
| PRESET | MCP23017 A4 | Recall active preset | Save current height |

**STOP is on the motion board on purpose.** FluidNC's native control pins act with no HMI involvement, so STOP halts motion even if the S3 has crashed or the UART has dropped. The other five depend on HMI state and cannot move without forking FluidNC.

**STOP is a feed hold, not an emergency stop.** The E-stop remains the mains-rated mushroom. The two must be physically unmistakable and mounted apart — two red mushrooms with different behaviours is a dangerous panel.

The expander costs no GPIOs, sharing the touch controller's existing I²C bus, and frees two pins that were previously committed.

---

## 11. Honest comparison with the FXBB FräsLift V3

The FXBB is a shipping commercial product and the reference for this design. Where it is better, that is worth knowing before committing.

| | FXBB | This design |
| --- | --- | --- |
| Handwheel immediacy | Encoder to step generator on one MCU — sub-millisecond | Encoder → S3 → UART → FluidNC planner. **Real added latency on the primary interaction** |
| Failure modes | One board, no link to lose | A UART link that can drop mid-cycle |
| Field configuration | All 15 settings changed at the machine | `config.yaml` edited from a computer |
| Dust tolerance | Three physical buttons, no touch | Touch panel for second-level functions |
| Hazard surface | Never touches mains | Contactor, relay, mains wiring and compliance |
| Proven | Years in the field, with a manual and fault table | Unbuilt, never compiled |
| Depth cycles | None | Scribe/rough/finish scheduler, dovetail, keyhole, bit-change |
| Memory | One volatile slot | Named presets in NVS |
| Probing | None | Two-touch probe with plate thickness |
| Router control | None | Relay with interlocks |
| Fault handling | One code, `ENDSTOP ERR` | Plural codes with Z0 invalidation |

**Mitigations adopted from FXBB.** A one-revolution look-ahead clamp on jog distance, so a fast wheel spin cannot queue a long move; live derived values while calibrating; an approaching-limit warning; and its stuck-switch diagnostic. The handwheel latency has no software fix and must be judged on the bench.

---

## 12. Implementation plan

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1 | Repo restructure — bespoke firmware retired to `legacy/`, new `firmware/` and `hmi/` trees | **Complete** (`01511d2`) |
| 2 | `firmware/config.yaml` — FluidNC machine definition | Not started. Blocked only on `steps_per_mm` |
| 3 | `docs/UART-PROTOCOL.md` — the HMI/controller protocol | Not started |
| 4 | `hmi/` — ESP32-S3 firmware: LVGL UI, GRBL sender, handwheel, buttons, cycles | Not started |
| 5 | Rev H specification amendment | Not started — seven deviations pending |

Phases 2 and 3 can proceed immediately. Phase 4 is the bulk of the work. Phase 5 should follow bench testing so that the specification records what was proven rather than what was intended.

---

## 13. Verification plan

Each step gates the next. No router and no cutter until the final steps.

1. **Build** — `pio run -e hmi` compiles; `legacy/` is not built.
2. **Panel bring-up** — LVGL renders at 480×272 and touch tracks. Highest technical risk.
3. **FluidNC standalone** — over USB, with the motor on the bench and the router unplugged: `$$` reads back, `$H` homes, top limit faults, `G38.2` probes, `M3`/`M5` clicks the relay.
4. **Both sensor types** — meter the conditioning circuit, confirm 0–3.3 V swing with the inductive sensor on 24 V, then **pull the signal wire and confirm it faults rather than going quiet**.
5. **Link** — status tracks position live; handwheel moves the axis.
6. **Link loss** — pull the cable mid-jog; motion must stop and must never start.
7. **Cycles dry-run** — all four, air-cutting, router unplugged.
8. **Acceptance** — ACC-01 to ACC-04 repeatability with a dial indicator, then ACC-06, 07, 10, 11.

Only then: router at lowest speed with no bit in the collet, then production cuts with the E-stop within reach.

---

## 14. Risks and open items

| Risk | Impact | Mitigation |
| --- | --- | --- |
| **`steps_per_mm` is an assumption** | Every depth figure is provisional | Measure the actual lead with a dial indicator before trusting any cut |
| RGB panel and LVGL on ~6 free pins | Bring-up failure or display corruption | Vendor demo is the working reference; fallback is moving UART to 43/44 and losing the console |
| FluidNC key names unverified | `config.yaml` may not load as written | Check the second-UART and macro keys against the installed release |
| Cycle logic lives in the HMI | An HMI bug can give a wrong depth | Accepted — FluidNC independently enforces limits, homing and probing, so it cannot give an unsafe move |
| Handwheel latency | Poor feel on the primary control | Tune report rate and jog chunk size; judge at bench step 5 |
| DEV-01 open | No stall detection; silent step loss | GPIO 35 reserved so a closed-loop driver closes it as a config edit |

### Open questions for the reviewer

1. Which commercial lift body? This is the critical path — it fixes the screw lead, the travel, and the achievable resolution.
2. Are the deviations in section 5 accepted, in particular the ELE-11 rewording?
3. Should the specification be amended to Rev H now, or after bench testing?
4. Is the handwheel latency trade acceptable in principle, given it cannot be removed without forking FluidNC?

Forty-four further questions across mechanics, motion, probing, interface and cycles are open in `DESIGN-QA.md`.
