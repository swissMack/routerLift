#!/bin/sh
# Regenerate every KiCad project, run ERC, export PDFs, cross-check pins.
set -eu
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
HW="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m unittest discover -s "$HW/tools/tests"
python3 "$HW/tools/gen_schematics.py"
for p in motion-carrier panel-carrier system; do
  "$KICAD_CLI" sch erc --severity-error --exit-code-violations \
    -o "$HW/$p/$p-erc.rpt" "$HW/$p/$p.kicad_sch"
  "$KICAD_CLI" sch export pdf -o "$HW/$p/$p.pdf" "$HW/$p/$p.kicad_sch"
done
for p in motion-carrier panel-carrier; do
  if [ -f "$HW/$p/$p.kicad_pcb" ]; then
    "$KICAD_CLI" pcb drc --schematic-parity --severity-all --exit-code-violations \
      -o "$HW/$p/$p-drc.rpt" "$HW/$p/$p.kicad_pcb"
  fi
done
python3 "$HW/tools/check_pins.py"
echo "verify: OK"
