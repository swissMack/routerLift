# Superseded drawings

Files in `docs/` prefixed `superseded-` describe **earlier designs that are no longer
being built**. They are kept for provenance and to explain how the design got here —
never as a build reference.

| File | Describes | Replaced by |
| --- | --- | --- |
| `superseded-SCHEMATIC.svg` | The pre-RevG **single-ESP32** design: ILI9488 TFT, XPT2046 touch, MCP23017 expander, DM542 driver, one controller doing motion and UI together | `SCHEMATIC-RevH.svg` |
| `superseded-wiring_diagram.svg` / `.png` | The **RevG** wiring: display-only HMI, MPG on the FluidNC ESP32 at GPIO 34/35, TB6600 common anode at +5 V, `ENA±` n/c | `SCHEMATIC-RevH.svg` + `WIRING-RevH.svg` |
| `SCHEMATIC-RevH.svg` | Hand-drawn Rev H schematic | `hardware/` KiCad projects (system.pdf, carrier PDFs) |

## Why they are wrong to build from

`superseded-SCHEMATIC.svg` predates the split architecture entirely. FluidNC does not run
on the ESP32-S3, and the S3 panel board cannot carry the machine's pin budget, so one
controller can no longer do both jobs.

`superseded-wiring_diagram.svg` is closer but wrong in four specific ways, each of which
would cause a real fault:

1. **MPG on FluidNC GPIO 34/35.** The handwheel now goes to the HMI board. Those pins are
   reserved for DEV-01 closure.
2. **TB6600 common anode at +5 V.** Leaves 1.7 V across the input optocoupler in the off
   state, so it never fully turns off — missed steps at rapid, which under DEV-01 is
   silent depth error. Must be +3.3 V.
3. **`ENA±` marked n/c.** Leaves the motor energised at 2.8 A/phase permanently with no way
   for FluidNC to de-energise it. Now wired to GPIO 14.
4. **No STOP button.** STOP now lands on FluidNC GPIO 21 as `feed_hold_pin`.

Its **JC4827W543C** display board is correct. Rev H listed it here as a fifth error, claiming
an ESP32-4827S043; bench bring-up on 2026-09-13 proved the board in hand is the JC4827W543C.

## Superseded documents

These keep their original names (other files link to them) but open with a banner saying they
describe the pre-RevG single-board design.

| File | Describes | Rev H equivalent |
| --- | --- | --- |
| `ARCHITECTURE.md` | v1 module map: `MotorControl`, `Safety`, MCP23017 board-ID, ILI9488/XPT2046 UI, one-loop state machine | `DESIGN-PLAN-RevH.md`, `REVIEW-RevH.md`, `ARCHITECTURE-DIAGRAM.svg` |
| `UX.md` | v1 screens on the 3.5" ILI9488, x1/x10/x100 rate switch | `DESIGN-PLAN-RevH.md` Phase 4 (modules, safety invariants) and 4b; `REVIEW-RevH.md` §10 control panel; `DESIGN-QA.md` display and panel decisions |
| `BENCH-TEST.md` | v1 9-stage bring-up ladder: DM542, MCP23017 board-ID, ILI9488 | `BRINGUP-LOG.md` (what is proven) and the Verification section of `DESIGN-PLAN-RevH.md` (the gated plan) |

The current drawing set is `SCHEMATIC-RevH.svg`, `WIRING-RevH.svg`, `PINOUT.svg` and
`ARCHITECTURE-DIAGRAM.svg`. `BOM.md` carries the full deviations table.
