#!/usr/bin/env bash
# Regenerate routerLift-Design-Review-RevH.docx from REVIEW-RevH.md + the SVG diagrams.
# Run from docs/.  Requires: Google Chrome (SVG render), pandoc.
set -euo pipefail
cd "$(dirname "$0")"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[[ -x "$CHROME" ]] || { echo "Chrome not found at $CHROME"; exit 1; }
command -v pandoc >/dev/null || { echo "pandoc not installed"; exit 1; }

mkdir -p .render

# Chrome renders SVG faithfully. Do NOT use qlmanage - it stretches to a square,
# and ImageMagick has no SVG delegate here (needs librsvg).
render() {  # name width height
  "$CHROME" --headless --disable-gpu --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=2 --window-size="$2,$3" \
    --screenshot="$PWD/.render/$1.png" "file://$PWD/$1.svg" >/dev/null 2>&1
  echo "  rendered $1.png"
}
render ARCHITECTURE-DIAGRAM 1500 1035
render PINOUT               1560 1080
render WIRING-RevH          1560 1120
render SCHEMATIC-RevH       1720 1290

# Landscape A4 reference doc - pandoc takes page size and styles from it.
python3 - <<'PY'
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.section import WD_ORIENT
d = Document(); s = d.sections[0]
s.orientation = WD_ORIENT.LANDSCAPE
s.page_width, s.page_height = Cm(29.7), Cm(21.0)
s.left_margin = s.right_margin = Cm(1.6)
s.top_margin = s.bottom_margin = Cm(1.4)
n = d.styles['Normal']; n.font.name, n.font.size = 'Calibri', Pt(10.5)
n.paragraph_format.space_after = Pt(6)
for i, sz in ((1,20),(2,15),(3,12)):
    st = d.styles[f'Heading {i}']; st.font.name, st.font.size = 'Calibri', Pt(sz)
d.save('.render/reference.docx')
PY

pandoc REVIEW-RevH.md \
  --reference-doc=.render/reference.docx \
  --toc --toc-depth=2 --resource-path=. \
  -o routerLift-Design-Review-RevH.docx

echo "wrote routerLift-Design-Review-RevH.docx"
