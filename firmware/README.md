# Motion controller — stock FluidNC

This directory contains **no source code**. The motion controller runs an unmodified FluidNC
binary; `config.yaml` is the entire machine definition.

That is deliberate and worth protecting. Homing, soft limits, hard limits, probing and step
generation are the safety-critical parts of this machine, and keeping FluidNC stock means they
are not ours to get wrong. Any proposal that requires editing FluidNC's source forfeits this.

---

## Flashing and configuration

1. Flash stock FluidNC to the ESP32 (**classic ESP32, not S3** — FluidNC does not run on the S3).
   Easiest: **installer.fluidnc.com** in Chrome or Edge (Web Serial), WiFi build.
2. Upload `config.yaml` to the board's filesystem — from the installer's file browser / terminal
   (`$Xmodem/Receive=/localfs/config.yaml`, confirm the `Received N bytes` count matches the local
   file), or via the FluidNC web UI at `192.168.0.1` on the `FluidNC` access point.
3. `$Config/Filename=config.yaml` if it is not the default.
4. **Restart with `$Bye`** — `$CD` shows the config loaded at the last boot, not the file on disk.
5. Read the boot log from the first line. Any `[MSG:ERR:` line, or `Board None` with a
   1000 mm Z axis, means the YAML did not parse and FluidNC fell back to defaults — the safe
   non-configured state. `$CD` dumps what was actually loaded.

**YAML parser gotchas (FluidNC v4.1.0):**
- The spindle section key is `Relay:` — `relay_spindle:` is silently ignored.
- Never put a comment on a section-header line, and never use `'` or `"` inside comments. An
  apostrophe in a comment on `Relay:` broke parsing of the whole file.

Flashed: **FluidNC v4.1.0 (esp32-wifi)**, 2026-09-13, on a 30-pin USB-C ESP32-WROOM-32 devkit
(CH340, 4 MB flash).

### Bare-board acceptance (passed 2026-09-13)

Board on USB only, nothing else connected:

| Check | Expected |
| --- | --- |
| Boot log | `Machine routerLift`, `Board ESP32 devkit v1`, no `ERR` lines |
| Z axis | `Axis Z (-0.001,65.001)`, `stepstick Step:gpio.26 Dir:gpio.27 Disable:gpio.14` |
| Relay | `Relay Spindle Ena:NO_PIN Out:gpio.4` |
| HMI link | `UART1 Tx:gpio.17 Rx:gpio.16 … Baud:115200`, report interval 100 |
| Limits, unwired | `ALARM: Hard Limit` and `Pn:Z` — correct, NC wiring reads open as tripped |
| Limits, D33 + D25 jumpered to GND | `?` shows no `Pn:Z`; after `$Bye` only `ALARM:14` (Unhomed, from `must_home`) |

`E (…) esp_core_dump_flash: No core dump partition found!` appears on every boot. It is harmless
— FluidNC's partition table has no core-dump area.

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
| 1 | ✅ `uart1:` / `uart_channel1:` key names — **verified v4.1.0** | Without a second channel the HMI shares the USB port and the debug console is lost |
| 2 | ✅ `report_interval_ms` exists — **verified v4.1.0** (boots at 100 ms); rate on the wire still to confirm with the HMI | The HMI's whole display depends on it; fallback is polling `?` |
| 3 | Soft-limit envelope sign convention | We home negative and work positive — the less common orientation. Prove with `$J=` at both ends |
| 4 | `macro0_pin` edge behaviour | Decides the foot-switch question above |
| 5 | Macro length limits, and whether `$Macro0` can be rewritten over the wire | The press-half plan depends on it |
| 6 | Homing pull-off failure raises a distinct alarm code | So the HMI can say "stuck switch", not just "limit" |
| 7 | `Relay` spindle reports non-zero `S` in status | The ROUTER LED depends on reading it |

---

## Commissioning: measuring `steps_per_mm`

**`steps_per_mm: 1066.67` in `config.yaml` is derived, not measured.** It comes from the sauter
FML-P's published 1.5 mm lead and the TB6600 at 1600 pulse/rev (1600 / 1.5). Confirm it on the
real lift before trusting any depth.

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
| `steps_per_mm` | **1066.67 — derived from FML-P spec, not yet measured** | `docs/MECHANICS-RevH.md` |
| `max_rate_mm_per_min` | 720 (12 mm/s) | Q14 |
| `acceleration_mm_per_sec2` | 100 | Q16 |
| `max_travel_mm` | 65 — provisional, FML-P published travel | MEC-01 |
| `idle_ms` | 255, never disable | Q17 |
| Homing seek / feed | 600 / 60 mm/min | Q14–16 |
| `pulloff_mm` | 2.0 mechanical, ~3.0 inductive | Q12 |
| Positive direction | Bit rising, home at bottom | Q19 |
| Microstepping | 1/8, 1600 pulse/rev | Q18 |
| `spinup_ms` | 2500 | SAF-03 gate |
| `must_home` | true, no exceptions | Q11 |

Plunge feed (2 mm/s, 120 mm/min) is not in this file — it is a `G1 F` value the HMI sends per
move, since it varies by cycle.
