# PCB layout — design

**Date:** 2026-09-14 · **Status:** approved in chat, awaiting spec review

## Goal

Lay out both carrier boards from the existing schematics and deliver fabrication-ready outputs:
routed `.kicad_pcb` files, a clean design rules check, and Gerber + drill zips for JLCPCB. The system
project is documentation only and gets no board.

## Inputs

| Input | Source |
| --- | --- |
| Netlist and footprints | `hardware/motion-carrier/motion-carrier.kicad_sch`, `hardware/panel-carrier/panel-carrier.kicad_sch` (generated, reviewed) |
| Devkit pin order | `hardware/tools/devkit.py`, verified against the HW-394 board on 2026-09-14 |
| Devkit row spacing | **25.4 mm — UNVERIFIED**, user to measure; marked on silkscreen and README |
| DIN-rail clips | Standard snap-on 35 mm DIN-rail PCB mounting clips — **exact hole spacing UNVERIFIED** |

## Method

A generator, `hardware/tools/gen_pcb.py`, runs under KiCad's bundled Python
(`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`,
which provides `pcbnew` 10.0.6):

1. Export the carrier netlist with `kicad-cli sch export netlist`.
2. Create a board: outline, mounting holes, design rules, net classes.
3. Load each footprint from the KiCad stock libraries, assign reference, value and nets, and place it
   from a per-board placement table (`hardware/tools/pcb_motion.py`, `hardware/tools/pcb_panel.py`).
4. Add keep-outs, silkscreen labels, and ground zones on both layers.
5. Export Specctra DSN, route with Freerouting (headless, Java 21), import the SES.
6. Refill zones, add GND stitching vias, save.
7. Run `kicad-cli pcb drc` with schematic parity; export Gerbers, drill files, a PDF and 3D renders.

Freerouting 2.x is downloaded from its official GitHub releases into the scratchpad (not committed).
Routing is not deterministic, so **the routed `.kicad_pcb` is committed and becomes the editable
source**. The generator is for the first layout or a full rebuild; hand edits in KiCad are allowed
afterwards.

## Fabrication rules (JLCPCB, 2-layer, 1.6 mm FR-4, HASL)

| Rule | Value |
| --- | --- |
| Default track / clearance | 0.25 mm / 0.25 mm |
| Power net class (`+5V`, `+3V3`, `GND`) | 0.6 mm tracks |
| Via | 0.6 mm pad, 0.3 mm drill |
| Board edge clearance | 0.5 mm |
| Mounting holes | M3, 3.2 mm plated, 7 mm diameter keep-out |
| Ground | Zones on F.Cu and B.Cu, stitched |
| Silkscreen min text | 1.0 mm height, 0.15 mm stroke |

## Motion carrier (~110 × 75 mm, DIN-rail clips)

- ESP32 devkit: two 1×15 socket rows, 25.4 mm apart, centred. The antenna end overhangs the board
  edge; a copper-free keep-out covers any board area under the antenna.
- All screw terminals along one long edge in wiring order: J3 5 V in, J4 TB6600, J5 relay, J6 limits,
  J7 probe/foot/STOP. Every terminal pin labelled on silkscreen with its net name.
- Five conditioning channels in a row between the terminals and the ESP32, each channel's
  R/R/BAT54S/C grouped behind its terminal pins.
- J8 link header on the short edge nearest the panel cable.
- Four M3 holes on the two terminal-free edges for DIN-rail clips.
- Silkscreen: board name, revision, "devkit row spacing 25.4 mm — verify", "antenna this edge".

## Panel carrier (~70 × 50 mm, M3 standoffs)

- J1 (P3) and J2 (P4) MX1.25 headers on one edge, labelled P3/P4 with pin 1 marked.
- U1 74LVC14 beside J4 (MPG); U2 MCP23017 beside J6 (buttons, 8-way).
- C1 and C2 within 3 mm of their chip's power pins; R1/R2 I²C pull-ups near J1.
- J3 link and J5 5 V input on the opposite edge; J7 LED terminal near U2.
- R3/R4 footprints present, silkscreen "DNP".
- One M3 hole in each corner.

## Verification (per board)

1. `kicad-cli pcb drc --schematic-parity --severity-error --exit-code-violations` → 0 errors,
   0 unconnected items, parity clean.
2. Gerber + drill export zipped as `hardware/<board>/fab/<board>-jlcpcb.zip`; layer set F/B.Cu,
   F/B.Mask, F/B.SilkS, Edge.Cuts, drill (Excellon).
3. Top and bottom 3D renders and a board PDF, reviewed at high resolution for placement, silkscreen
   legibility and copper-free antenna area.
4. `hardware/tools/verify.sh` extended to run the PCB DRC on both boards.

## Deliverables and commits

One commit per board (generator + placement table + routed board + fab outputs), one for the
generator core with its tests, and one for `verify.sh`/README updates.

## Out of scope

The PCB for the system project; BOM/CPL files for JLCPCB assembly (hand-soldered build); enclosure
mechanical design.
