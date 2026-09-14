# Hardware — KiCad schematics (Rev H)

Generated from Python. **Do not edit the `.kicad_sch` files in KiCad** — the next
regeneration overwrites them. Change `tools/*.py` and run:

    hardware/tools/verify.sh     # tests, generate, ERC, PDFs, pin cross-check

After running `verify.sh`, restore unchanged PDFs with `git checkout -- hardware/*/*.pdf` unless the schematics actually changed.

| Project | What | For layout? |
| --- | --- | --- |
| `motion-carrier/` | ESP32 devkit sockets, 5 input conditioners, field terminals, link header | Yes |
| `panel-carrier/` | 74LVC14 MPG shifter, MCP23017 + pull-ups, MX1.25 leads to the display | Yes |
| `system/` | Mains, E-stop, PSU, modules and cabling between them | No — reference |

`tools/check_pins.py` fails if a schematic pin disagrees with `firmware/config.yaml` or
`hmi/include/pins.h`.

## PCBs

Boards are generated once, then **the routed `.kicad_pcb` is the source** — edit it in KiCad's PCB
Editor freely. Rebuilding from scratch overwrites hand edits:

    hardware/tools/get_freerouting.sh                                   # once
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      hardware/tools/gen_pcb.py motion-carrier                          # or panel-carrier

`get_freerouting.sh` fetches v2.1.0 (v2.2+ needs Java 25); override with `FREEROUTING_VERSION=2.4.1 ./get_freerouting.sh` etc.

`verify.sh` runs DRC with schematic parity on both boards. Autorouting gives a different result
each run, so after any regeneration run `kicad-cli pcb drc --schematic-parity --severity-all` and
check for warnings too. Fabrication zips for JLCPCB (2-layer, 1.6 mm, HASL) are in
`<board>/fab/<board>-jlcpcb.zip`.

| Board | Size | Mounting |
| --- | --- | --- |
| motion carrier | 140 × 80 mm | 4× M3 for standard DIN-rail PCB clips |
| panel carrier | 80 × 62 mm | 4× M3 corners, standoffs |

## Open items shown on the drawings

- Contactor coil voltage (BOM block A).
- MPG output type — R3/R4 on the panel carrier are DNP until known.
- Foot-switch release mirror (MCP GPA6) — needs a second pedal contact or a shared-contact decision.
- ESP32 devkit row spacing assumed 25.4 mm — measure before ordering boards.
- DIN-rail clip hole spacing — check against the clips bought.
