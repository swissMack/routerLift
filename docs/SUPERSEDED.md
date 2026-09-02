# Superseded drawings

Files in `docs/` prefixed `superseded-` describe **earlier designs that are no longer
being built**. They are kept for provenance and to explain how the design got here —
never as a build reference.

| File | Describes | Replaced by |
| --- | --- | --- |
| `superseded-SCHEMATIC.svg` | The pre-RevG **single-ESP32** design: ILI9488 TFT, XPT2046 touch, MCP23017 expander, DM542 driver, one controller doing motion and UI together | `SCHEMATIC-RevH.svg` |
| `superseded-wiring_diagram.svg` / `.png` | The **RevG** wiring: display-only HMI, MPG on the FluidNC ESP32 at GPIO 34/35, TB6600 common anode at +5 V, `ENA±` n/c | `SCHEMATIC-RevH.svg` + `WIRING-RevH.svg` |

## Why they are wrong to build from

`superseded-SCHEMATIC.svg` predates the split architecture entirely. FluidNC does not run
on the ESP32-S3, and the S3's RGB panel cannot carry the machine's pin budget, so one
controller can no longer do both jobs.

`superseded-wiring_diagram.svg` is closer but wrong in five specific ways, each of which
would cause a real fault:

1. **MPG on FluidNC GPIO 34/35.** The handwheel now goes to the HMI board. Those pins are
   reserved for DEV-01 closure.
2. **TB6600 common anode at +5 V.** Leaves 1.7 V across the input optocoupler in the off
   state, so it never fully turns off — missed steps at rapid, which under DEV-01 is
   silent depth error. Must be +3.3 V.
3. **`ENA±` marked n/c.** Leaves the motor energised at 2.8 A/phase permanently with no way
   for FluidNC to de-energise it. Now wired to GPIO 14.
4. **No STOP button.** STOP now lands on FluidNC GPIO 21 as `feed_hold_pin`.
5. **Display board is a JC4827W543C.** The board in hand is an ESP32-4827S043 with a
   completely different panel interface and pinout.

The current drawing set is `SCHEMATIC-RevH.svg`, `WIRING-RevH.svg`, `PINOUT.svg` and
`ARCHITECTURE-DIAGRAM.svg`. `BOM.md` carries the full deviations table.
