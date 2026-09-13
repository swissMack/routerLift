# routerLift

Open-firmware automated router lift for a workshop router table. A 4.3" touch
panel with a CNC-style handwheel drives a stepper-actuated lift body, with
motion handled by stock [FluidNC](https://github.com/bdring/FluidNC).

Specification: `docs/Router_Lift_Requirement_Specification_RevG.md`, amended by
the Rev H design set.

## Architecture — two boards

Motion and the operator interface run on separate controllers. FluidNC does not
run on the ESP32-S3, and the S3 board cannot carry the machine's full pin
budget, so one board cannot do both.

```
  ESP32-S3 touch panel                 classic ESP32
  ┌──────────────────┐   UART/GRBL   ┌──────────────────┐
  │  hmi/  (our C++) │ ────────────► │ stock FluidNC    │   TB6600 ─► stepper
  │  LVGL, handwheel │ ◄──────────── │ firmware/*.yaml  │   NPN limits, probe
  └──────────────────┘   status @10Hz└──────────────────┘   SSR ─► router
```

**The HMI has no motion authority.** Soft limits, hard limits, homing and
probing are all enforced by FluidNC. A bug in our firmware can produce a *wrong
cutting depth*; it must never produce an *unsafe move*. Keeping FluidNC stock
means the safety-critical parts are not ours to get wrong — any proposal that
needs FluidNC source edits forfeits that.

| Directory | Contents |
| --- | --- |
| `firmware/` | FluidNC machine definition — `config.yaml` only, **no source** |
| `hmi/` | PlatformIO ESP32-S3 project: LVGL UI, handwheel, buttons, GRBL sender |
| `legacy/` | The retired v1.x single-ESP32 firmware. Reference only, not built |
| `docs/` | Spec, Rev H design set, wiring, protocol, bench tests, mechanics |

## Hardware

**Motion board** — classic ESP32 running unmodified FluidNC. TB6600 driver at
1/8 microstepping (1600 pulse/rev), 24–36 V. NPN NC inductive limit switches,
`G38.2` probe for tool zeroing, `Relay` spindle SSR for router power with a
2500 ms spin-up gate.

**Operator panel** — ESP32-4827S043 board (ESP32-S3-WROOM-1-N4R8, 4 MB flash,
8 MB octal PSRAM). 4.3" 480×272 RGB parallel panel via Arduino_GFX, GT911
capacitive touch, LVGL 8.4. Six panel buttons and the rough/fine selector sit on
an MCP23017 sharing the GT911's I²C bus — the RGB panel consumes twenty GPIOs,
so the expander is what makes a physical control panel possible at all. MPG
handwheel decoded on the S3's PCNT peripheral.

STOP is deliberately *not* on the panel: it is wired to FluidNC's own
`feed_hold_pin`, so it halts motion even if the HMI has crashed.

Full pin map and wiring: `docs/HARDWARE.md`, `docs/WIRING-RevH.svg`,
`docs/SCHEMATIC-RevH.svg`, `docs/PINOUT.svg`.

## Status

| Half | State |
| --- | --- |
| `firmware/config.yaml` | Written. Seven items still to verify against the installed FluidNC release |
| `hmi/` increments 1–3 | Built and compiling — link, handwheel, buttons, display, touch, main screen, Z0 probe, presets |
| `hmi/` increment 4 | Cycles (standard → bit-change → dovetail → keyhole). Not started |
| `hmi/` increment 5 | Fault log, diagnostics, runtime hours. Not started |
| Mechanics | Lift body **not yet bought**. See `docs/MECHANICS-RevH.md` |

HMI flash use is 21.8% of 4 MB, RAM 22.5%.

Increment 3 is enough to pass bench-test steps 1, 2, 4, 5 and the probe half of
step 7 (`docs/BENCH-TEST.md`).

### Nothing has been cut yet

Two numbers are provisional because the lift body is unchosen, and both follow
from the screw lead:

- `firmware/config.yaml` → `steps_per_mm: 800` — a placeholder assuming a 2 mm
  lead, from a machine that was never built
- `hmi/include/config.h` → `MpgCfg::SCREW_LEAD_MM = 2.0`

**Until `steps_per_mm` is measured against a dial indicator, every depth this
machine cuts is wrong by an unknown factor** — and wrong invisibly, because
there is no stall detection to contradict a bad number. The commissioning
procedure is in `firmware/README.md`.

One design question is also open: the foot switch needs both press and release
edges for dead-man behaviour, and FluidNC's `macro0_pin` may only fire on
assert. The proposed split (press on FluidNC, release mirrored to an HMI
expander input) is written up in `firmware/README.md` and not yet verified.

## Build

Only the HMI is built from this repo. FluidNC is flashed from its own release.

```sh
git clone git@github.com:swissMack/routerLift.git
cd routerLift
pio run -e hmi           # compile
pio run -e hmi -t upload # flash the S3 panel
pio device monitor       # serial console at 115200
```

Libraries resolve on first build: ESP32Encoder, GFX Library for Arduino, LVGL
8.4, TAMC_GT911.

For the motion board, flash stock FluidNC to a classic ESP32 and upload
`firmware/config.yaml` to its filesystem — see `firmware/README.md`.

## Documentation

| File | Contents |
| --- | --- |
| [docs/Router_Lift_Requirement_Specification_RevG.md](docs/Router_Lift_Requirement_Specification_RevG.md) | The requirement spec |
| [docs/DESIGN-PLAN-RevH.md](docs/DESIGN-PLAN-RevH.md) | The RevG pivot, phase by phase |
| [docs/UART-PROTOCOL.md](docs/UART-PROTOCOL.md) | HMI ↔ FluidNC command vocabulary |
| [docs/MECHANICS-RevH.md](docs/MECHANICS-RevH.md) | Lift body selection and stepper drive design |
| [docs/LIFT-COMPARISON.md](docs/LIFT-COMPARISON.md) | The four candidate lift bodies, compared |
| [docs/BOM.md](docs/BOM.md) | Bill of materials |
| [docs/HARDWARE.md](docs/HARDWARE.md) | Pin map and wiring detail |
| [docs/BENCH-TEST.md](docs/BENCH-TEST.md) | Staged bring-up — each step passes before the next part is fitted |
| [docs/UX.md](docs/UX.md) | Interaction model |
| [docs/DESIGN-QA.md](docs/DESIGN-QA.md) | The design Q&A that settled the constants |
| [hmi/README.md](hmi/README.md) | HMI modules, build gotchas, Z0 validity rules |
| [firmware/README.md](firmware/README.md) | FluidNC setup, pre-power-up checks, commissioning |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Code style, commit conventions |

`docs/SUPERSEDED.md` lists the drawings the Rev H set replaced.
`docs/reference/FXBB-original/` holds the FXBB FräsLift V3 documentation this
project draws on.

## Safety

This machine drives a high-RPM router. Read `firmware/README.md` before first
power-up — five of its checks are destructive or silently wrong if got wrong,
including PSU voltage (48 V destroys the TB6600), TB6600 common anode at 3.3 V
not 5 V, and NPN-not-PNP limit sensors.

Z0 — the reference every cut depth is measured from — is owned entirely by the
HMI, and **there is no override anywhere** on probe validity. That is
deliberate: a wrong reference does not fail visibly, it produces a
plausible-looking cut at the wrong depth. See `hmi/README.md`.

The author accepts no liability for misuse. Test with the router unpowered
first.
