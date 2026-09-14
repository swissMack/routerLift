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

## Open items shown on the drawings

- Devkit header rows assume the DOIT 30-pin layout — verify against the board in hand.
- Contactor coil voltage (BOM block A).
- MPG output type — R3/R4 on the panel carrier are DNP until known.
- Foot-switch release mirror (MCP GPA6) — needs a second pedal contact or a shared-contact decision.
