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
  └──────────────────┘  status @10Hz └──────────────────┘   relay ─► router
```

The HMI polls status with `?` every 100 ms — FluidNC's automatic report only
fires on change. No status for 500 ms counts as link loss: the HMI sends a feed
hold and invalidates Z0.

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

**Motion board** — classic ESP32 (30-pin USB-C ESP32-WROOM-32 devkit) running
unmodified FluidNC v4.1.0. TB6600 driver at 1/8 microstepping (1600 pulse/rev),
24–36 V, common anode +3.3 V, 1.0–1.4 A/phase. NPN NC inductive limit switches,
`G38.2` probe for tool zeroing, `Relay` spindle output for router power with a
2500 ms spin-up gate. Host lift: sauter FML-P (1.5 mm lead, 65 mm travel).

**Operator panel** — Guition JC4827W543C board (XH-S3E N4R8 module: ESP32-S3,
4 MB flash, 8 MB octal PSRAM). 4.3" 480×272 IPS NV3041A panel over QSPI via
Arduino_GFX, GT911 capacitive touch, LVGL 8.4. The board brings only ten GPIOs
out to connectors, so the panel buttons and the rough/fine selector sit on an
MCP23017 on its own I²C bus (GPIO 15/16) — the touch bus is not brought out.
MPG handwheel decoded on the S3's PCNT peripheral (GPIO 6/7), through a 74LVC14
on 3.3 V (two stages per channel, non-inverting).

STOP is deliberately *not* on the panel: it is wired to FluidNC's own
`feed_hold_pin`, so it halts motion even if the HMI has crashed.

Full pin map and wiring: `docs/HARDWARE.md`, `docs/WIRING-RevH.svg`,
`docs/SCHEMATIC-RevH.svg`, `docs/PINOUT.svg`.

## Status

Bench truth lives in `docs/BRINGUP-LOG.md`. As of 2026-09-13:

| Half | State |
| --- | --- |
| Motion board | ✅ FluidNC v4.1.0 flashed, `config.yaml` parses, bare-board acceptance passed (limits NC-correct). Five items still to verify — `firmware/README.md` |
| Screen board | ✅ Display and touch working on the JC4827W543C |
| UART link (Step B) | ✅ Link up, link-loss feed hold + Z0 invalidation, recovery verified |
| `hmi/` increments 1–3 | Built. Display, touch and link bench-verified; MPG and buttons **not yet wired** (waiting on the level shifters) |
| `hmi/` increment 4 | Cycles (standard → bit-change → dovetail → keyhole). Not started |
| `hmi/` increment 5 | Fault log, diagnostics, runtime hours. Not started |
| Mechanics | Lift body (sauter FML-P) **not yet bought**. See `docs/MECHANICS-RevH.md` |

HMI flash use is ~24% of the 3 MB app slot.

### Nothing has been cut yet

Two numbers come from the sauter FML-P datasheet, not a measurement, and both
follow from its 1.5 mm screw lead:

- `firmware/config.yaml` → `steps_per_mm: 1066.67` (1600 pulse/rev ÷ 1.5 mm),
  with `max_travel_mm: 65`
- `hmi/include/config.h` → `MpgCfg::SCREW_LEAD_MM = 1.5`

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
pio run -e hmi-diag      # bring-up diagnostics build (no I2C, display logging)
pio device monitor       # serial console at 115200
```

Libraries resolve on first build: ESP32Encoder, GFX Library for Arduino, LVGL
8.4, TAMC_GT911. If upload cannot connect because the app has hung, hold BOOT,
tap RST and retry.

For the motion board, flash stock FluidNC from installer.fluidnc.com, upload
`firmware/config.yaml` with `$Xmodem/Receive=/localfs/config.yaml`, and restart
with `$Bye` — see `firmware/README.md`. Its console is also reachable over WiFi:
`telnet routerlift.local 23`.

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
| [docs/BRINGUP-LOG.md](docs/BRINGUP-LOG.md) | What has actually been proven on the bench, session by session |
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
