# KiCad schematics — design

**Date:** 2026-09-13 · **Status:** approved in chat, awaiting spec review

## Goal

Replace the hand-drawn `docs/SCHEMATIC-RevH.svg` with KiCad schematics that are (a) a whole-system
reference drawing and (b) layout-ready schematics for two carrier PCBs. Schematics only — PCB layout
is a separate task.

## Sources of truth

The schematics transcribe an already-verified design; they introduce no new electronics.

| Fact | Source |
| --- | --- |
| Motion GPIOs | `firmware/config.yaml` |
| Panel GPIOs, MCP23017 bits | `hmi/include/pins.h` |
| Circuits, part values, topology | `docs/WIRING-RevH.md`, `docs/BOM.md` blocks A–H |

Where the BOM is undecided (e.g. contactor coil voltage), the schematic labels the part
**UNVERIFIED** rather than choosing a value.

## Method

A Python generator, `hardware/tools/gen_schematics.py`, writes the `.kicad_sch` files (KiCad 9
format) using KiCad's stock symbol libraries. All GPIO assignments live in one table in the
generator. `hardware/tools/check_pins.py` parses the generated schematics and fails if any GPIO
differs from `pins.h` or `config.yaml`. Hand edits in KiCad are not preserved — change the
generator and regenerate.

## Projects (`hardware/`)

### 1. `motion-carrier/` — fabricated, DIN rail in the enclosure

- ESP32-WROOM-32 30-pin devkit on 2× 1×15 female headers.
- **Input conditioning sub-sheet, instantiated ×5** — HOME→33, TOP→25, PROBE→32, FOOT→13,
  DRV_ALM→35: `+3V3 — 4.7 kΩ — wire node — 10 kΩ — GPIO node (BAT54S to 3V3/GND + 100 nF) — GPIO`.
  Pull-up on the wire side (else a closed switch reads ≈2.2 V).
- STOP → GPIO 21 direct (internal pull-up), to GND.
- Outputs: TB6600 PUL−/DIR−/ENA− ← GPIO 26/27/14, PUL+/DIR+/ENA+ ← 3V3; relay module IN ← GPIO 4,
  plus 5 V/GND.
- Terminals (5 mm screw): 5 V in, TB6600, relay, each sensor with a GND/shield terminal, STOP, FOOT.
- Link header to panel: TX 17, RX 16, GND. **No 3V3 pin** (the two 3.3 V rails never join).
- GPIO 34 no-connect (reserved).

### 2. `panel-carrier/` — fabricated, behind the display

- MX1.25 4-pin headers matching the display's P3 (IO6·IO7·IO15·IO16) and P4 (GND·3.3V·IO17·IO18).
- 74LVC14 on panel 3.3 V + 100 nF: two stages per channel, MPG A→GPIO 6, B→GPIO 7
  (non-inverting); unused gates' inputs tied to GND.
- MCP23017 at 0x20 (A0–A2 to GND) + 100 nF; 4.7 kΩ pull-ups on SDA 15 / SCL 16.
  Port A inputs A0 CYCLE START, A1 ROUTER, A2 BIT CHANGE, A3 ZERO, A4 PRESET, A5 ROUGH/FINE,
  A6 FOOT MIRROR (dashed/unverified), A7 spare; B0 → ROUTER LED via series resistor.
- Terminals: MPG (5 V from buck, GND, A, B), buttons, LED, 5 V in.
- Link terminal: UART from P4 passed to the motion-carrier link header.

### 3. `system/` — documentation only

- **Sheet `mains`:** RCD → E-stop NC (breaks L to PSU and contactor) → fuse → PSU and relay contact →
  bit-change key switch → contactor coil A1/A2; RC snubber; router socket from T1; PE bonding.
- **Sheet `low-voltage`:** PSU 24–36 V → buck 5 V → star ground; TB6600 + motor; sensors, probe,
  foot pedal, STOP; MPG; display board; both carriers as blocks with their connectors and the
  cables between them.

## Parts assumptions

Through-hole resistors and caps, SOT-23 BAT54S, SOIC-14 74LVC14, SOIC-28 MCP23017, 5 mm screw
terminals. Footprints assigned on the carriers only.

## Verification

1. `kicad-cli sch erc` — zero errors on both carriers (the system project is checked but warnings
   about off-board modules are acceptable).
2. `kicad-cli sch export pdf` for all three; each sheet visually reviewed.
3. `check_pins.py` passes.

## Deliverables and commits

One commit each: generator + motion carrier; panel carrier; system project; README/CLAUDE.md
key-paths update marking `SCHEMATIC-RevH.svg` superseded.
