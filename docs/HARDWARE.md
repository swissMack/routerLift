# Hardware

## Bill of materials

| Item | Notes |
| --- | --- |
| ESP32 DevKit V1 (WROOM-32) | Any ESP32 board with the listed GPIOs broken out |
| 3.5" ILI9488 SPI TFT, 480×320, with XPT2046 touch | Most commonly sold combined |
| 5 V 4-terminal MPG, 100 PPR | A, B, +V, GND |
| 3-position rotary switch (x1 / x10 / x100) | SP3T, one common + three throws |
| MCP23017 I/O expander | I²C addr 0x20 |
| DM542 stepper driver | Set microsteps to give 1000 steps/rev (or update config) |
| NEMA 23 stepper motor | 1.8°/step native |
| Ball-screw spindle, 4 mm lead | Match `DEFAULT_SPINDLE_PITCH_MM` |
| 698 RS bearing | Between motor shaft and ball screw — eliminates axial play |
| 2× NPN inductive sensors (top + bottom endstops) | Active-LOW; 24 V common |
| 1× NPN inductive sensor (brass-stamp pickup) | Same family as endstops |
| Solid-state relay | Rated for your router's continuous current |
| Foot switch | Momentary, normally open |
| 24 V PSU + 5 V / 3.3 V regulators | Stepper / sensors on 24 V; logic on regulated rails |
| 2× PC817 opto-isolators OR 1× 74HCT14 hex Schmitt inverter | MPG signal level shifting |

## Pin map (ESP32 → external)

| Function | GPIO | Notes |
| --- | --- | --- |
| Stepper STEP | 25 | to DM542 PUL+ |
| Stepper DIR | 26 | to DM542 DIR+ |
| Stepper ENABLE | 27 | to DM542 ENA+ (active-LOW) |
| MPG A | 32 | via opto/HCT, 3.3 V output |
| MPG B | 33 | via opto/HCT, 3.3 V output |
| Router relay (SSR) | 16 | drives SSR control input |
| I²C SDA | 21 | to MCP23017 + future devices |
| I²C SCL | 22 | to MCP23017 + future devices |
| TFT SCK | 18 | shared SPI bus |
| TFT MOSI | 23 | shared SPI bus |
| TFT MISO | 19 | shared SPI bus |
| TFT CS | 15 | dedicated |
| TFT DC | 2 | dedicated |
| TFT RST | 4 | dedicated |
| TOUCH CS | 5 | dedicated, shares SCK/MOSI/MISO with TFT |
| TOUCH IRQ | 17 | optional; polled in v1, hooked for v2 |

## MCP23017 pin map

| Function | Port.Pin | Wiring |
| --- | --- | --- |
| Endstop bottom | A.0 | NPN sensor open-collector to GND (sensor +V from 24 V; signal to MCP via 10 kΩ pull-down to 3.3 V or interface optocoupler) |
| Endstop top | A.1 | same |
| Brass-stamp pickup | A.2 | same |
| Foot switch | A.3 | momentary to GND |
| Board ID bit 0 | B.0 | jumper to GND on function board |
| Board ID bit 1 | B.1 | jumper to GND on function board |
| Board ID bit 2 | B.2 | jumper to GND on function board |
| Board ID bit 3 | B.3 | jumper to GND on function board |
| Rate switch x1 | B.4 | switch common to GND, throw to B.4 |
| Rate switch x10 | B.5 | throw to B.5 |
| Rate switch x100 | B.6 | throw to B.6 |

## MPG level-shifter circuits

The ESP32 GPIO pins are 3.3 V and **not 5 V tolerant**. The 5 V signals from
the MPG must be level-shifted before reaching GPIO 32/33. Two recommended
approaches:

### Option A — PC817 opto-isolation (recommended for workshop noise)

```
  MPG +V (5 V) ─┬─[330 Ω]─┐
                │         │
                │      ┌──┴─── PC817 LED anode
   MPG A ───────┴──────┤
                       └──── PC817 LED cathode → GND
                       
                        ┌─── ESP32 3.3 V
                        │
                       [10 kΩ]
                        │
   PC817 collector ─────┼─── ESP32 GPIO32
                        │
   PC817 emitter ───────┴─── GND
```

One opto per channel (A and B). Signal is inverted — set
`MPG::SIGNALS_INVERTED = true` in `config.h`.

Galvanically isolates the ESP32 ground from the stepper/MPG ground.
Recommended in workshops where the router and stepper introduce ground
bounce.

### Option B — 74HCT14 hex Schmitt inverter (cheap, no isolation)

74HCT family runs on 3.3 V VCC and tolerates 5 V on inputs because of TTL
thresholds. Use two inverters per channel (chain) for a non-inverted output:

```
   ESP32 3.3 V ── HCT14 VCC
   GND          ── HCT14 GND
   MPG A (5 V) ─→ U1A ─→ U1B ─→ ESP32 GPIO32   (double-inverted = pass-through)
   MPG B (5 V) ─→ U1C ─→ U1D ─→ ESP32 GPIO33
```

Set `MPG::SIGNALS_INVERTED = false`. Add 100 nF decoupling on VCC.

### Why not a voltage divider?

Resistor dividers work in theory but the MPG outputs are typically
open-collector at the source, and the ESP32 pin capacitance forms an RC
low-pass with the divider that distorts the quadrature signal at high
spin rates. Use opto or HCT.

## Rate switch wiring

Standard SP3T rotary switch:

```
                ┌── B.4 (x1)
                │
  Common ── GND ┼── B.5 (x10)
                │
                └── B.6 (x100)
```

MCP internal pull-ups idle the lines HIGH. The selected position pulls one
line LOW. `IOExpander::readRateMultiplier()` returns 1, 10, 100, or 0
(invalid).

## Power architecture

```
  24 V PSU ─┬──→ Stepper driver, NPN sensors
            ├──→ Buck → 5 V → MPG, opto LED side, TFT backlight
            └──→ Buck → 3.3 V → ESP32, MCP23017, opto transistor side
```

Keep stepper and logic grounds connected at a single star point near
the PSU to minimise loop area.
