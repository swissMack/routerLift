# PCB Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate, autoroute and verify routed KiCad boards for the motion and panel carriers, with JLCPCB-ready Gerber zips.

**Architecture:** `pcb_netlist.py` (stdlib) reads the carrier netlist exported by `kicad-cli`. `pcbkit.py` (KiCad's bundled Python, `pcbnew`) builds a board: outline, holes, footprints with nets, keep-outs, ground zones, silkscreen, then Specctra DSN → Freerouting → SES, zone fill and stitching vias. One placement module per board (`pcb_motion.py`, `pcb_panel.py`) holds coordinates. `gen_pcb.py` is the CLI. `kicad-cli` runs DRC with schematic parity and exports fab files.

**Tech Stack:** KiCad 10.0.6 bundled Python 3.9.13 with `pcbnew`; system Python 3.9.6 for stdlib code and tests; `kicad-cli`; Freerouting 2.4.1 (`freerouting-2.4.1.jar`, Java 21); `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-14-pcb-layout-design.md`

## Global Constraints

- JLCPCB 2-layer, 1.6 mm FR-4. Default track/clearance 0.25/0.25 mm. Power class (`+5V`, `+3V3`, `GND`) tracks 0.6 mm. Via 0.6 mm pad / 0.3 mm drill. Board-edge copper clearance 0.5 mm. Silkscreen text ≥1.0 mm high, 0.15 mm stroke.
- M3 mounting holes: `MountingHole:MountingHole_3.2mm_M3_Pad`, board-only (not in schematic), no net.
- Ground zones on F.Cu and B.Cu, stitched with vias.
- Motion carrier: devkit rows **25.4 mm apart — UNVERIFIED**; antenna end overhangs the board edge with a copper-free rule area on board under it; all screw terminals on one long edge in order J3, J4, J5, J6, J7; every terminal pin's net name on silkscreen; four M3 holes on terminal-free edges for standard DIN-rail PCB clips (hole spacing **UNVERIFIED**).
- Panel carrier: M3 hole in each corner; C1/C2 within 3 mm of their chip's power pins; R3/R4 placed, silkscreen "DNP".
- Board sizes in the spec are approximate ("~"); a placement that needs a larger board to keep the spec's edge rules is allowed and must be recorded in the report.
- Each board: `kicad-cli pcb drc --schematic-parity --severity-error --exit-code-violations` → 0 violations.
- The routed `.kicad_pcb` is committed and becomes hand-editable; schematics remain generated-only.
- Python 3.9: no `match`, no `X | Y`. Stdlib only outside `pcbnew`.
- `KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`, `K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. `import pcbnew` prints a harmless `wxApp` assert line on stderr.
- Conventional Commits; commit messages end with the session attribution lines.

## File Structure

| File | Responsibility |
| --- | --- |
| `hardware/tools/pcb_netlist.py` | Export and parse a schematic netlist: components, pad → net |
| `hardware/tools/pcbkit.py` | `BoardBuilder` on `pcbnew`: outline, holes, footprints, rule areas, zones, silk, project rules, autoroute, stitching, save |
| `hardware/tools/pcb_motion.py` | Motion carrier dimensions and placement |
| `hardware/tools/pcb_panel.py` | Panel carrier dimensions and placement |
| `hardware/tools/gen_pcb.py` | CLI: build → route → DRC → fab outputs for one board |
| `hardware/tools/get_freerouting.sh` | Download the Freerouting jar into `hardware/tools/.cache/` |
| `hardware/tools/kisch.py` (modify) | `Project.write` preserves existing `.kicad_pro` keys |
| `hardware/tools/tests/test_pcb_netlist.py`, `test_pcbkit.py` | Tests (`test_pcbkit` skips without `pcbnew`) |
| `hardware/<board>/<board>.kicad_pcb`, `fab/<board>-jlcpcb.zip`, `<board>-pcb.pdf`, `<board>-top.png`, `<board>-bottom.png` | Outputs |

---

### Task 1: Netlist reader, project-file preservation, Freerouting fetch

**Files:**
- Create: `hardware/tools/pcb_netlist.py`, `hardware/tools/get_freerouting.sh`, `hardware/tools/tests/test_pcb_netlist.py`, `hardware/tools/tests/fixtures/tiny.net`
- Modify: `hardware/tools/kisch.py` (`Project.write`), `hardware/tools/tests/test_kisch.py`, `.gitignore`

**Interfaces:**
- Produces: `Component(ref, value, footprint, dnp)`; `read_netlist(text) -> (OrderedDict[str, Component], Dict[Tuple[str, str], str])`; `export_netlist(sch_path, kicad_cli) -> str`; `refs_on_net(pads, net, prefix="") -> List[str]` (natural-sorted); `pads_of(pads, ref) -> Dict[str, str]`.
- `Project.write()` keeps every existing top-level key of `<name>.kicad_pro` and only sets `meta`.

- [ ] **Step 1: Fixture** `hardware/tools/tests/fixtures/tiny.net`:

```
(export (version "E")
  (components
    (comp (ref "R1") (value "10k") (footprint "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"))
    (comp (ref "R2") (value "4.7k") (footprint "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")
      (property (name "dnp") (value "")))
    (comp (ref "R10") (value "1k") (footprint "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")))
  (nets
    (net (code "1") (name "/SIG") (class "Default")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "1") (pintype "passive"))
      (node (ref "R10") (pin "1") (pintype "passive")))
    (net (code "2") (name "+3V3") (class "Default")
      (node (ref "R1") (pin "1") (pintype "passive")))
    (net (code "3") (name "unconnected-(R2-Pad2)") (class "Default")
      (node (ref "R2") (pin "2") (pintype "passive")))
    (net (code "4") (name "GND") (class "Default")
      (node (ref "R10") (pin "2") (pintype "passive")))))
```

- [ ] **Step 2: Failing tests** `hardware/tools/tests/test_pcb_netlist.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcb_netlist import pads_of, read_netlist, refs_on_net

TEXT = (Path(__file__).parent / "fixtures" / "tiny.net").read_text()


class NetlistTest(unittest.TestCase):
    def test_components(self):
        comps, _ = read_netlist(TEXT)
        self.assertEqual(list(comps), ["R1", "R2", "R10"])
        self.assertEqual(comps["R1"].value, "10k")
        self.assertTrue(comps["R1"].footprint.startswith("Resistor_THT:"))
        self.assertTrue(comps["R2"].dnp)
        self.assertFalse(comps["R1"].dnp)

    def test_net_names_kept_exactly(self):
        _, pads = read_netlist(TEXT)
        self.assertEqual(pads[("R1", "2")], "/SIG")
        self.assertEqual(pads[("R1", "1")], "+3V3")
        self.assertEqual(pads[("R2", "2")], "unconnected-(R2-Pad2)")

    def test_helpers(self):
        _, pads = read_netlist(TEXT)
        self.assertEqual(refs_on_net(pads, "/SIG"), ["R1", "R2", "R10"])
        self.assertEqual(refs_on_net(pads, "/SIG", prefix="R1"), ["R1", "R10"])
        self.assertEqual(pads_of(pads, "R10"), {"1": "/SIG", "2": "GND"})
```

Add to `hardware/tools/tests/test_kisch.py`:

```python
class ProjectFilePreservationTest(unittest.TestCase):
    def test_existing_pro_keys_survive_regeneration(self):
        import json
        s = Sheet("p", "p", lib())
        s.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": "A", "2": "A"})
        with tempfile.TemporaryDirectory() as d:
            pro = Path(d) / "p.kicad_pro"
            pro.write_text(json.dumps({"board": {"design_settings": {"x": 1}}, "meta": {"version": 0}}))
            Project("p", s, d).write()
            data = json.loads(pro.read_text())
        self.assertEqual(data["board"], {"design_settings": {"x": 1}})
        self.assertEqual(data["meta"], {"filename": "p.kicad_pro", "version": 1})
```

Run: `python3 -m unittest discover -s hardware/tools/tests -v` → Expected: `No module named 'pcb_netlist'` and the preservation test failing on `KeyError: 'board'`.

- [ ] **Step 3: Implement** `hardware/tools/pcb_netlist.py`:

```python
"""Read a KiCad (kicadsexpr) netlist: components and which net each pad is on."""
import collections
import re
import subprocess
import tempfile
from pathlib import Path

from kisch import find, findall, parse

Component = collections.namedtuple("Component", "ref value footprint dnp")


def _natural(ref):
    m = re.match(r"([A-Za-z#]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def read_netlist(text):
    tree = parse(text)
    comps = collections.OrderedDict()
    for c in findall(find(tree, "components"), "comp"):
        fp = find(c, "footprint")
        dnp = any(str(find(p, "name")[1]) == "dnp" for p in findall(c, "property"))
        ref = str(find(c, "ref")[1])
        comps[ref] = Component(ref, str(find(c, "value")[1]), str(fp[1]) if fp else "", dnp)
    pads = {}
    for net in findall(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1])
        for node in findall(net, "node"):
            pads[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return comps, pads


def export_netlist(sch_path, kicad_cli):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "board.net"
        subprocess.run([kicad_cli, "sch", "export", "netlist", "--format", "kicadsexpr",
                        "-o", str(out), str(sch_path)], check=True, capture_output=True)
        return out.read_text(encoding="utf-8")


def refs_on_net(pads, net, prefix=""):
    return sorted({ref for (ref, _), n in pads.items() if n == net and ref.startswith(prefix)},
                  key=_natural)


def pads_of(pads, ref):
    return {pad: net for (r, pad), net in pads.items() if r == ref}
```

In `kisch.py` `Project.write`, replace the two lines that build and write `pro` with:

```python
        pro_path = self.outdir / (self.name + ".kicad_pro")
        pro = json.loads(pro_path.read_text()) if pro_path.exists() else {}
        pro["meta"] = {"filename": self.name + ".kicad_pro", "version": 1}
        pro_path.write_text(json.dumps(pro, indent=2) + "\n")
```

Confirm the committed `.kicad_pro` files still regenerate byte-identical: `python3 hardware/tools/gen_schematics.py && git diff --stat hardware/*/*.kicad_pro hardware/*/*.kicad_sch` → empty. If `json.dumps` key order differs from the committed files, keep `pro` insertion order (`meta` stays where it was) so they stay identical.

- [ ] **Step 4: Freerouting fetch** `hardware/tools/get_freerouting.sh`:

```sh
#!/bin/sh
# Download the Freerouting jar used by gen_pcb.py into hardware/tools/.cache/.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)/.cache"
VERSION="${FREEROUTING_VERSION:-v2.4.1}"
mkdir -p "$DIR"
if ls "$DIR"/freerouting-*.jar >/dev/null 2>&1; then echo "have $(ls "$DIR"/freerouting-*.jar)"; exit 0; fi
gh release download "$VERSION" -R freerouting/freerouting --pattern 'freerouting-*.jar' -D "$DIR"
ls "$DIR"/freerouting-*.jar
```

Append to `.gitignore`:

```
hardware/tools/.cache/
hardware/**/fab/gerbers/
hardware/**/*.dsn
hardware/**/*.ses
hardware/**/*-drc.rpt
hardware/**/*.kicad_pcb.bak
hardware/**/*-backups/
```

Run `chmod +x hardware/tools/get_freerouting.sh && hardware/tools/get_freerouting.sh` → prints `.../freerouting-2.4.1.jar`. Run `java -jar hardware/tools/.cache/freerouting-2.4.1.jar --help 2>&1 | head -40` and record in the report the exact flags for: input DSN, output SES, max passes, and headless/no-GUI. Task 2 uses them.

- [ ] **Step 5: Tests pass; commit**

```bash
python3 -m unittest discover -s hardware/tools/tests -v
git add hardware/tools/pcb_netlist.py hardware/tools/get_freerouting.sh hardware/tools/kisch.py hardware/tools/tests .gitignore
git commit -m "feat(hardware): read netlists for PCB generation and fetch Freerouting"
```

---

### Task 2: `pcbkit` board builder

**Files:**
- Create: `hardware/tools/pcbkit.py`, `hardware/tools/tests/test_pcbkit.py`

**Interfaces:**
- Consumes: `pcb_netlist.Component`, pad→net dict.
- Produces (all coordinates mm, origin = board top-left, y down):
  - `BoardBuilder(name, width, height)`; `.board` (`pcbnew.BOARD`); `.fps` dict ref → footprint
  - `.place(comp, pads, x, y, rot=0)` → footprint; pads get nets by `(ref, pad number)`
  - `.mounting_hole(x, y)`
  - `.rule_area(x0, y0, x1, y1)` — no copper, tracks, vias or pours on all copper layers
  - `.ground_zones()` — GND zone on F.Cu and B.Cu over the whole board, 0.5 mm inset
  - `.silk(text, x, y, size=1.0, rot=0)`
  - `.courtyard_mm(ref) -> (x0, y0, x1, y1)` in board coordinates
  - `.save(path)`; `write_project_rules(pro_path)`; `autoroute(pcb_path, jar, flags) -> None`; `stitch_ground(pcb_path, pitch=10.0) -> int` (vias added)
  - `NET_CLASS_POWER = ("+5V", "+3V3", "GND")`

- [ ] **Step 1: Failing tests** `hardware/tools/tests/test_pcbkit.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import pcbnew  # noqa: F401
    import pcbkit
except ImportError:
    pcbkit = None
from pcb_netlist import read_netlist

TEXT = (Path(__file__).parent / "fixtures" / "tiny.net").read_text()


@unittest.skipIf(pcbkit is None, "needs KiCad's bundled python (pcbnew)")
class BoardBuilderTest(unittest.TestCase):
    def build(self):
        comps, pads = read_netlist(TEXT)
        b = pcbkit.BoardBuilder("tiny", 40.0, 30.0)
        b.place(comps["R1"], pads, 10.0, 10.0)
        b.place(comps["R10"], pads, 10.0, 20.0)
        b.mounting_hole(35.0, 5.0)
        return b

    def test_pads_get_nets(self):
        b = self.build()
        nets = {p.GetNumber(): p.GetNetname() for p in b.fps["R10"].Pads()}
        self.assertEqual(nets, {"1": "/SIG", "2": "GND"})

    def test_courtyard_inside_board(self):
        b = self.build()
        x0, y0, x1, y1 = b.courtyard_mm("R1")
        self.assertTrue(0 < x0 < x1 < 40 and 0 < y0 < y1 < 30)

    def test_mounting_hole_is_board_only(self):
        b = self.build()
        hole = [f for f in b.board.GetFootprints() if f.GetReference().startswith("H")][0]
        self.assertTrue(hole.GetAttributes() & pcbnew.FP_BOARD_ONLY)

    def test_save_round_trip_and_rules(self):
        b = self.build()
        b.ground_zones()
        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "tiny.kicad_pcb"
            pcbkit.write_project_rules(Path(d) / "tiny.kicad_pro")
            b.save(pcb)
            loaded = pcbnew.LoadBoard(str(pcb))
            pro = json.loads((Path(d) / "tiny.kicad_pro").read_text())
        self.assertEqual(len(loaded.Zones()), 2)
        classes = {c["name"]: c for c in pro["net_settings"]["classes"]}
        self.assertEqual(classes["Power"]["track_width"], 0.6)
        self.assertEqual(classes["Default"]["clearance"], 0.25)
```

Run: `$KPY -m unittest discover -s hardware/tools/tests -v` → Expected: `No module named 'pcbkit'` errors in `test_pcbkit`; other tests pass. Also run with system `python3` → `test_pcbkit` skipped.

- [ ] **Step 2: Implement** `hardware/tools/pcbkit.py`:

```python
"""Build KiCad boards with pcbnew. Run under KiCad's bundled python.

Coordinates are millimetres from the board's top-left corner, y down.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pcbnew

FP_DIR = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
ORIGIN = (100.0, 100.0)  # where the board sits on the KiCad page
NET_CLASS_POWER = ("+5V", "+3V3", "GND")
MM = pcbnew.FromMM


def _load_fp(lib_id):
    lib, name = lib_id.split(":", 1)
    fp = pcbnew.FootprintLoad(str(FP_DIR / (lib + ".pretty")), name)
    if fp is None:
        raise KeyError("footprint not found: " + lib_id)
    return fp


class BoardBuilder:
    def __init__(self, name, width, height):
        self.name, self.w, self.h = name, float(width), float(height)
        self.board = pcbnew.BOARD()
        self.nets, self.fps = {}, {}
        self._holes = 0
        rect = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_RECT)
        rect.SetStart(self.p(0, 0))
        rect.SetEnd(self.p(self.w, self.h))
        rect.SetLayer(pcbnew.Edge_Cuts)
        rect.SetWidth(MM(0.1))
        self.board.Add(rect)

    def p(self, x, y):
        return pcbnew.VECTOR2I(MM(ORIGIN[0] + x), MM(ORIGIN[1] + y))

    def net(self, name):
        if name not in self.nets:
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.nets[name] = item
        return self.nets[name]

    def place(self, comp, pads, x, y, rot=0):
        fp = _load_fp(comp.footprint)
        fp.SetReference(comp.ref)
        fp.SetValue(comp.value)
        self.board.Add(fp)
        fp.SetPosition(self.p(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            netname = pads.get((comp.ref, pad.GetNumber()))
            if netname:
                pad.SetNet(self.net(netname))
        self.fps[comp.ref] = fp
        return fp

    def mounting_hole(self, x, y):
        self._holes += 1
        fp = _load_fp("MountingHole:MountingHole_3.2mm_M3_Pad")
        fp.SetReference("H%d" % self._holes)
        fp.SetValue("M3")
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM)
        self.board.Add(fp)
        fp.SetPosition(self.p(x, y))
        self.fps[fp.GetReference()] = fp
        return fp

    def _outline_zone(self, zone, x0, y0, x1, y1):
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            pt = self.p(x, y)
            outline.Append(pt.x, pt.y)

    def rule_area(self, x0, y0, x1, y1):
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        self._outline_zone(z, x0, y0, x1, y1)
        self.board.Add(z)
        return z

    def ground_zones(self):
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(self.board)
            z.SetLayer(layer)
            z.SetNet(self.net("GND"))
            z.SetLocalClearance(MM(0.3))
            z.SetMinThickness(MM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            self._outline_zone(z, 0.5, 0.5, self.w - 0.5, self.h - 0.5)
            self.board.Add(z)

    def silk(self, text, x, y, size=1.0, rot=0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(text)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(0.15))
        t.SetPosition(self.p(x, y))
        t.SetTextAngleDegrees(rot)
        self.board.Add(t)
        return t

    def courtyard_mm(self, ref):
        box = self.fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        return (pcbnew.ToMM(box.GetX()) - ORIGIN[0], pcbnew.ToMM(box.GetY()) - ORIGIN[1],
                pcbnew.ToMM(box.GetRight()) - ORIGIN[0], pcbnew.ToMM(box.GetBottom()) - ORIGIN[1])

    def save(self, path):
        pcbnew.SaveBoard(str(path), self.board)


def write_project_rules(pro_path):
    """Merge JLCPCB rules and net classes into the project file the schematic already uses."""
    pro_path = Path(pro_path)
    pro = json.loads(pro_path.read_text()) if pro_path.exists() else {}
    board = pro.setdefault("board", {})
    ds = board.setdefault("design_settings", {})
    ds["rules"] = {
        "min_clearance": 0.25, "min_track_width": 0.25, "min_via_diameter": 0.6,
        "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.5,
        "min_hole_to_hole": 0.25, "min_text_height": 1.0, "min_text_thickness": 0.15,
    }
    ds["track_widths"] = [0.0, 0.25, 0.6]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}]
    pro["net_settings"] = {
        "classes": [
            {"name": "Default", "clearance": 0.25, "track_width": 0.25,
             "via_diameter": 0.6, "via_drill": 0.3},
            {"name": "Power", "clearance": 0.25, "track_width": 0.6,
             "via_diameter": 0.6, "via_drill": 0.3},
        ],
        "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in NET_CLASS_POWER],
        "meta": {"version": 3},
    }
    pro.setdefault("meta", {"filename": pro_path.name, "version": 1})
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")


def autoroute(pcb_path, jar, flags):
    """Export DSN, run Freerouting, import SES, refill zones, save in place.

    flags: callable(dsn, ses) -> list of Freerouting CLI args (from Task 1's --help record).
    """
    board = pcbnew.LoadBoard(str(pcb_path))
    with tempfile.TemporaryDirectory() as d:
        dsn, ses = Path(d) / "board.dsn", Path(d) / "board.ses"
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError("DSN export failed")
        subprocess.run(["java", "-jar", str(jar)] + flags(dsn, ses), check=True)
        if not ses.exists():
            raise RuntimeError("Freerouting produced no SES file")
        if not pcbnew.ImportSpecctraSES(board, str(ses)):
            raise RuntimeError("SES import failed")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(pcb_path), board)


def stitch_ground(pcb_path, pitch=10.0, margin=1.0):
    """Add GND vias on a grid wherever both GND zones are filled around the point."""
    board = pcbnew.LoadBoard(str(pcb_path))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gnd = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]
    front = [z for z in gnd if z.GetLayer() == pcbnew.F_Cu]
    back = [z for z in gnd if z.GetLayer() == pcbnew.B_Cu]
    box = board.GetBoardEdgesBoundingBox()
    net = board.FindNet("GND")
    added = 0
    x = box.GetX() + MM(pitch / 2)
    while x < box.GetRight():
        y = box.GetY() + MM(pitch / 2)
        while y < box.GetBottom():
            probes = [pcbnew.VECTOR2I(x + dx, y + dy) for dx, dy in
                      ((0, 0), (MM(margin), 0), (-MM(margin), 0), (0, MM(margin)), (0, -MM(margin)))]
            if all(any(z.HitTestFilledArea(pcbnew.F_Cu, pt) for z in front) and
                   any(z.HitTestFilledArea(pcbnew.B_Cu, pt) for z in back) for pt in probes):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(x, y))
                via.SetWidth(MM(0.6))
                via.SetDrill(MM(0.3))
                via.SetNet(net)
                board.Add(via)
                added += 1
            y += MM(pitch)
        x += MM(pitch)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(pcb_path), board)
    return added
```

`pcbnew` API names above were checked on 10.0.6 for `ZONE.SetIsRuleArea/SetDoNotAllowTracks/SetLocalClearance/SetMinThickness/HitTestFilledArea`, `ZONE_FILLER`, `FP_BOARD_ONLY`, `SHAPE_T_RECT`, `FootprintLoad`, `GetCourtyard`. For any other call that raises `AttributeError` or `TypeError` (e.g. `SetDoNotAllowPads`, `FP_EXCLUDE_FROM_BOM`, `GetBoardEdgesBoundingBox`, `SetWidth` on vias), find the 10.0.6 equivalent with `$KPY -c "import pcbnew; print([m for m in dir(pcbnew.ZONE) if 'Allow' in m])"` and record the substitution in the report.

- [ ] **Step 3: Tests pass under both interpreters**

```bash
$KPY -m unittest discover -s hardware/tools/tests -v 2>&1 | grep -v wxApp
python3 -m unittest discover -s hardware/tools/tests -v
```

Expected: all pass under `$KPY`; under `python3` the `BoardBuilderTest` cases report `skipped`.

- [ ] **Step 4: Autoroute smoke test** (no commit of output): build the tiny board in the scratchpad, route it, confirm tracks exist.

```bash
SP=/private/tmp/claude-501/-Users-mackmood-Documents-GitHub-routerLift/31e286fe-3534-4235-a845-54bd93e39f06/scratchpad/pcbkit-smoke
mkdir -p $SP && $KPY - <<'EOF' 2>&1 | grep -v wxApp
import sys; sys.path.insert(0, "hardware/tools")
from pathlib import Path
import pcbnew, pcbkit
from pcb_netlist import read_netlist
SP = Path("/private/tmp/claude-501/-Users-mackmood-Documents-GitHub-routerLift/31e286fe-3534-4235-a845-54bd93e39f06/scratchpad/pcbkit-smoke")
comps, pads = read_netlist(Path("hardware/tools/tests/fixtures/tiny.net").read_text())
b = pcbkit.BoardBuilder("tiny", 40, 30)
b.place(comps["R1"], pads, 10, 10); b.place(comps["R2"], pads, 25, 10); b.place(comps["R10"], pads, 10, 20)
pcbkit.write_project_rules(SP / "tiny.kicad_pro"); b.save(SP / "tiny.kicad_pcb")
jar = next(Path("hardware/tools/.cache").glob("freerouting-*.jar"))
FLAGS = lambda dsn, ses: ["-de", str(dsn), "-do", str(ses), "-mp", "20", "--gui.enabled=false"]  # replace with Task 1's recorded flags
pcbkit.autoroute(SP / "tiny.kicad_pcb", jar, FLAGS)
print("tracks", len(pcbnew.LoadBoard(str(SP / "tiny.kicad_pcb")).GetTracks()))
EOF
```

Expected: `tracks N` with N > 0.

- [ ] **Step 5: Commit**

```bash
git add hardware/tools/pcbkit.py hardware/tools/tests/test_pcbkit.py
git commit -m "feat(hardware): add pcbkit, a pcbnew board builder with autorouting"
```

---

### Task 3: `gen_pcb.py` and the motion carrier board

**Files:**
- Create: `hardware/tools/gen_pcb.py`, `hardware/tools/pcb_motion.py`
- Create (generated, committed): `hardware/motion-carrier/motion-carrier.kicad_pcb`, `hardware/motion-carrier/fab/motion-carrier-jlcpcb.zip`, `hardware/motion-carrier/motion-carrier-pcb.pdf`, `hardware/motion-carrier/motion-carrier-top.png`, `hardware/motion-carrier/motion-carrier-bottom.png`
- Modify: `hardware/motion-carrier/motion-carrier.kicad_pro` (rules merged in)

**Interfaces:**
- Consumes: `pcb_netlist.export_netlist/read_netlist/refs_on_net/pads_of`, `pcbkit.*`.
- Produces: `pcb_motion.build(builder_cls, comps, pads) -> BoardBuilder`; `gen_pcb.py <board> [--no-route]`; board modules expose `NAME`, `build(comps, pads)`.

- [ ] **Step 1: `gen_pcb.py`**

```python
"""Generate, route and check a carrier board.

$KPY hardware/tools/gen_pcb.py motion-carrier [--no-route]
"""
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcbkit
import pcb_motion
import pcb_panel
from pcb_netlist import export_netlist, read_netlist

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
HW = Path(__file__).resolve().parents[1]
BOARDS = {"motion-carrier": pcb_motion, "panel-carrier": pcb_panel}
FAB_LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"


def freerouting_flags(dsn, ses):
    # Flags recorded from `java -jar freerouting-2.4.1.jar --help` in Task 1.
    return ["-de", str(dsn), "-do", str(ses), "-mp", "30", "--gui.enabled=false"]


def cli(*args):
    subprocess.run([KICAD_CLI] + [str(a) for a in args], check=True)


def main(argv):
    name = argv[1]
    route = "--no-route" not in argv
    outdir = HW / name
    pcb = outdir / (name + ".kicad_pcb")
    comps, pads = read_netlist(export_netlist(outdir / (name + ".kicad_sch"), KICAD_CLI))
    builder = BOARDS[name].build(comps, pads)
    pcbkit.write_project_rules(outdir / (name + ".kicad_pro"))
    builder.save(pcb)
    if route:
        jar = next((HW / "tools" / ".cache").glob("freerouting-*.jar"))
        pcbkit.autoroute(pcb, jar, freerouting_flags)
        print("stitching vias:", pcbkit.stitch_ground(pcb))
    cli("pcb", "drc", "--schematic-parity", "--severity-error", "--exit-code-violations",
        "-o", outdir / (name + "-drc.rpt"), pcb)
    gerbers = outdir / "fab" / "gerbers"
    gerbers.mkdir(parents=True, exist_ok=True)
    cli("pcb", "export", "gerbers", "--layers", FAB_LAYERS, "-o", str(gerbers) + "/", pcb)
    cli("pcb", "export", "drill", "--format", "excellon", "-o", str(gerbers) + "/", pcb)
    with zipfile.ZipFile(outdir / "fab" / (name + "-jlcpcb.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerbers.iterdir()):
            z.write(f, f.name)
    cli("pcb", "export", "pdf", "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts",
        "-o", outdir / (name + "-pcb.pdf"), pcb)
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "-w", "1600", "-h", "1200",
            "-o", outdir / ("%s-%s.png" % (name, side)), pcb)
    print("ok", pcb)


if __name__ == "__main__":
    main(sys.argv)
```

Before relying on it, run `$K pcb export gerbers --help`, `$K pcb export drill --help`, `$K pcb export pdf --help`, `$K pcb render --help` and correct any flag names that differ in 10.0.6. Record corrections in the report. Until `pcb_panel.py` exists (Task 4), create it as a stub containing `NAME = "panel-carrier"` and `def build(comps, pads): raise NotImplementedError`.

- [ ] **Step 2: `pcb_motion.py`**

```python
"""Motion carrier placement. Board 140 x 80 mm; terminals on the bottom edge."""
from pcb_netlist import pads_of, refs_on_net
import pcbkit

NAME = "motion-carrier"
W, H = 140.0, 80.0
TERMINALS = ["J3", "J4", "J5", "J6", "J7"]           # left to right along the bottom edge
TERMINAL_ROT = 0                                     # 0 or 180 - confirm from the render
TERMINAL_GAP = 2.0
EDGE_MARGIN = 1.0
ROW_SPACING = 25.4                                    # devkit rows - UNVERIFIED
DEVKIT_PIN1_X = W - 3.0                              # pin 1 (antenna end) near the right edge
DEVKIT_TOP_ROW_Y = 12.0
ANTENNA_KEEPOUT = (W - 6.0, 6.0, W, 44.0)
HOLES = [(4.0, 4.0), (4.0, H - 18.0), (W - 4.0, H - 18.0), (W - 20.0, 4.0)]
CHANNELS = ["HOME", "TOP", "PROBE", "FOOT", "DRV_ALM"]
FIELD_TERMINAL_PIN = {"HOME": ("J6", "1"), "TOP": ("J6", "3"), "DRV_ALM": ("J6", "5"),
                      "PROBE": ("J7", "1"), "FOOT": ("J7", "3")}


def channel_parts(pads, channel):
    """(pull-up R, series R, BAT54S, C) for one conditioning channel, found by nets."""
    field, gpio = "/%s_FIELD" % channel, "/%s_IN" % channel
    series = [r for r in refs_on_net(pads, field, "R") if r in refs_on_net(pads, gpio, "R")][0]
    pullup = [r for r in refs_on_net(pads, field, "R") if r != series][0]
    diode = refs_on_net(pads, gpio, "D")[0]
    cap = refs_on_net(pads, gpio, "C")[0]
    return pullup, series, diode, cap


def build(comps, pads):
    b = pcbkit.BoardBuilder(NAME, W, H)

    # Terminals: measure each courtyard at the origin, then move it so the courtyard sits
    # EDGE_MARGIN inside the bottom edge. Wire entries must face that edge: TERMINAL_ROT is
    # 0 or 180 - confirm from the 3D render in Step 4.
    x = 6.0
    for ref in TERMINALS:
        fp = b.place(comps[ref], pads, 0, 0, rot=TERMINAL_ROT)
        x0, _, _, y1 = b.courtyard_mm(ref)
        fp.SetPosition(b.p(x - x0, (H - EDGE_MARGIN) - y1))
        cx0, cy0, cx1, _ = b.courtyard_mm(ref)
        for pad in fp.Pads():
            px = pcbkit.pcbnew.ToMM(pad.GetPosition().x) - pcbkit.ORIGIN[0]
            label = pad.GetNetname().lstrip("/").replace("_FIELD", "")
            b.silk(label, px, cy0 - 3.0, size=1.0, rot=90)
        x = cx1 + TERMINAL_GAP
    if x > W - 1.0:
        raise ValueError("terminals need a board at least %.1f mm wide" % (x + 1.0))

    # Devkit sockets, rotated so pin 1 is at the right (antenna) end.
    b.place(comps["J1"], pads, DEVKIT_PIN1_X, DEVKIT_TOP_ROW_Y, rot=270)
    b.place(comps["J2"], pads, DEVKIT_PIN1_X, DEVKIT_TOP_ROW_Y + ROW_SPACING, rot=270)
    b.rule_area(*ANTENNA_KEEPOUT)
    b.silk("ESP32 ANTENNA >", W - 16.0, 3.0)
    b.silk("DEVKIT ROWS 25.4 mm - VERIFY", DEVKIT_PIN1_X - 20.0, DEVKIT_TOP_ROW_Y + ROW_SPACING / 2)

    # Conditioning channels: a block above each channel's field terminal pin.
    for ch in CHANNELS:
        pullup, series, diode, cap = channel_parts(pads, ch)
        tref, tpin = FIELD_TERMINAL_PIN[ch]
        pad = [p for p in b.fps[tref].Pads() if p.GetNumber() == tpin][0]
        px = pcbkit.pcbnew.ToMM(pad.GetPosition().x) - pcbkit.ORIGIN[0]
        b.place(comps[pullup], pads, px - 1.8, 52.0, rot=90)
        b.place(comps[series], pads, px + 1.8, 52.0, rot=90)
        b.place(comps[diode], pads, px - 2.0, 45.0, rot=0)
        b.place(comps[cap], pads, px + 2.5, 45.0, rot=90)
        b.silk(ch, px, 41.5, size=1.0)

    b.place(comps["J8"], pads, 5.0, 28.0, rot=90)
    b.silk("LINK GND TX RX", 9.0, 22.0, size=1.0)
    for hx, hy in HOLES:
        b.mounting_hole(hx, hy)
    b.silk("routerLift motion carrier Rev H", 30.0, 3.0, size=1.2)
    b.ground_zones()
    return b
```

Placement numbers above are a starting point, not a result: Step 4 iterates them until DRC is clean and the render reads well. The spec estimated ~110 × 75 mm; five terminals on one edge need ≈130 mm, so the board starts at 140 × 80 mm (allowed by the Global Constraints). Every change of board size, hole position or channel geometry goes into the report.

- [ ] **Step 3: Generate without routing and inspect**

```bash
$KPY hardware/tools/gen_pcb.py motion-carrier --no-route 2>&1 | grep -v wxApp
tail -25 hardware/motion-carrier/motion-carrier-drc.rpt
```

Expected before routing: only `unconnected_items` errors (plus nothing else). Fix every other error (courtyard overlaps, clearance to edge, silk over pads, parity mismatches) by moving parts in `pcb_motion.py`. Parity errors mean the board's footprints/nets differ from the schematic — fix the builder, never the schematic.

- [ ] **Step 4: Visual placement check**

Read `hardware/motion-carrier/motion-carrier-top.png` with the Read tool. Check: terminal wire entries face the bottom edge (else set `TERMINAL_ROT = 180`), devkit pin-1 end at the right edge, antenna keep-out under the antenna end, net labels readable and not over pads, holes clear of parts. Regenerate until correct.

- [ ] **Step 5: Route, check, export**

```bash
$KPY hardware/tools/gen_pcb.py motion-carrier 2>&1 | grep -v wxApp | tail -5
tail -15 hardware/motion-carrier/motion-carrier-drc.rpt
```

Expected: `** Found 0 DRC violations **`, `** Found 0 unconnected pads **`, parity clean, and `ok .../motion-carrier.kicad_pcb`. If Freerouting leaves nets unrouted, first loosen placement around the unrouted area, then raise max passes; do not relax clearance or track rules. Read the regenerated `-top.png` and `-bottom.png` and the first page of `-pcb.pdf` to confirm the routing and ground fill look sane (no tracks under the antenna, power tracks visibly wider).

- [ ] **Step 6: Tests and commit**

```bash
$KPY -m unittest discover -s hardware/tools/tests 2>&1 | tail -3
python3 hardware/tools/gen_schematics.py && git diff --stat hardware/*/*.kicad_sch   # must be empty
git add hardware/tools/gen_pcb.py hardware/tools/pcb_motion.py hardware/tools/pcb_panel.py \
  hardware/motion-carrier/motion-carrier.kicad_pcb hardware/motion-carrier/motion-carrier.kicad_pro \
  hardware/motion-carrier/fab/motion-carrier-jlcpcb.zip hardware/motion-carrier/motion-carrier-pcb.pdf \
  hardware/motion-carrier/motion-carrier-top.png hardware/motion-carrier/motion-carrier-bottom.png
git commit -m "feat(hardware): lay out and route the motion carrier PCB"
```

---

### Task 4: Panel carrier board

**Files:**
- Modify: `hardware/tools/pcb_panel.py` (replace stub)
- Create (generated, committed): `hardware/panel-carrier/panel-carrier.kicad_pcb`, `fab/panel-carrier-jlcpcb.zip`, `panel-carrier-pcb.pdf`, `panel-carrier-top.png`, `panel-carrier-bottom.png`; modify `panel-carrier.kicad_pro`

**Interfaces:**
- Consumes: `pcbkit`, `pcb_netlist`, `gen_pcb.py` from Task 3.

- [ ] **Step 1: `pcb_panel.py`**

```python
"""Panel carrier placement. Board 80 x 55 mm; M3 hole in each corner."""
import pcbkit

NAME = "panel-carrier"
W, H = 80.0, 55.0
TOP_TERMINALS = ["J3", "J4", "J5"]        # link, MPG, 5 V in - top edge, left to right from x=9
BOTTOM_TERMINALS = ["J6", "J7"]           # buttons, LED - bottom edge
HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
TERMINAL_ROT_TOP = 180                    # entries face the top edge - confirm from render
TERMINAL_ROT_BOTTOM = 0                   # entries face the bottom edge - confirm from render


def _edge_row(b, comps, pads, refs, rot, bottom, start_x=9.0, gap=2.0, margin=1.0):
    x = start_x
    for ref in refs:
        fp = b.place(comps[ref], pads, 0, 0, rot=rot)
        x0, y0, x1, y1 = b.courtyard_mm(ref)
        dy = (H - margin - y1) if bottom else (margin - y0)
        fp.SetPosition(b.p(x - x0, dy))
        x = b.courtyard_mm(ref)[2] + gap
    if x > W - 7.5:
        raise ValueError("edge row too wide for %.1f mm board: ends at %.1f" % (W, x))


def build(comps, pads):
    b = pcbkit.BoardBuilder(NAME, W, H)
    _edge_row(b, comps, pads, TOP_TERMINALS, TERMINAL_ROT_TOP, bottom=False)
    _edge_row(b, comps, pads, BOTTOM_TERMINALS, TERMINAL_ROT_BOTTOM, bottom=True)
    b.place(comps["J1"], pads, 4.0, 20.0, rot=90)
    b.silk("P3 (1=IO6)", 8.0, 16.0)
    b.place(comps["J2"], pads, 4.0, 34.0, rot=90)
    b.silk("P4 (1=GND)", 8.0, 30.0)
    b.place(comps["R1"], pads, 14.0, 22.0, rot=90)
    b.place(comps["R2"], pads, 17.5, 22.0, rot=90)
    b.place(comps["U1"], pads, 32.0, 24.0, rot=0)
    b.place(comps["C1"], pads, 32.0, 17.5, rot=0)
    b.place(comps["R3"], pads, 42.0, 22.0, rot=90)
    b.place(comps["R4"], pads, 45.5, 22.0, rot=90)
    b.silk("DNP", 43.75, 16.5)
    b.place(comps["U2"], pads, 58.0, 30.0, rot=90)
    b.place(comps["C2"], pads, 58.0, 22.0, rot=0)
    b.place(comps["R5"], pads, 70.0, 30.0, rot=90)
    for hx, hy in HOLES:
        b.mounting_hole(hx, hy)
    b.silk("routerLift panel carrier Rev H", 30.0, H / 2 + 8.0, size=1.2)
    b.ground_zones()
    return b
```

The coordinates are a starting point. Requirements to verify and iterate on: every footprint's courtyard inside the board and clear of the holes' courtyards; C1 within 3 mm (edge to edge) of U1 pins 7/14 and C2 within 3 mm of U2 VDD/VSS — measure with `b.courtyard_mm` and pad positions, and assert it in `build()` so a regression fails; terminal pins labelled on silkscreen with their net names (use the same per-pad label approach as `pcb_motion.py`).

- [ ] **Step 2: Generate unrouted, fix DRC, visual check**

```bash
$KPY hardware/tools/gen_pcb.py panel-carrier --no-route 2>&1 | grep -v wxApp
tail -25 hardware/panel-carrier/panel-carrier-drc.rpt
```

Expected: only unconnected items. Read `panel-carrier-top.png`; confirm terminal entries face their edges (adjust `TERMINAL_ROT_*`), P3/P4 pin 1 marks visible, DNP label by R3/R4.

- [ ] **Step 3: Route, check, export**

```bash
$KPY hardware/tools/gen_pcb.py panel-carrier 2>&1 | grep -v wxApp | tail -5
tail -15 hardware/panel-carrier/panel-carrier-drc.rpt
```

Expected: 0 violations, 0 unconnected, parity clean. Read the top/bottom renders and PDF.

- [ ] **Step 4: Commit**

```bash
git add hardware/tools/pcb_panel.py hardware/panel-carrier/panel-carrier.kicad_pcb \
  hardware/panel-carrier/panel-carrier.kicad_pro hardware/panel-carrier/fab/panel-carrier-jlcpcb.zip \
  hardware/panel-carrier/panel-carrier-pcb.pdf hardware/panel-carrier/panel-carrier-top.png \
  hardware/panel-carrier/panel-carrier-bottom.png
git commit -m "feat(hardware): lay out and route the panel carrier PCB"
```

---

### Task 5: Verify script and documentation

**Files:**
- Modify: `hardware/tools/verify.sh`, `hardware/README.md`, `CLAUDE.md` (Key paths `hardware/` row)

- [ ] **Step 1: `verify.sh`** — after the ERC/PDF loop and before `check_pins.py`, add:

```sh
for p in motion-carrier panel-carrier; do
  if [ -f "$HW/$p/$p.kicad_pcb" ]; then
    "$KICAD_CLI" pcb drc --schematic-parity --severity-error --exit-code-violations \
      -o "$HW/$p/$p-drc.rpt" "$HW/$p/$p.kicad_pcb"
  fi
done
```

Run `hardware/tools/verify.sh` → last line `verify: OK`. Restore re-exported schematic PDFs: `git checkout -- hardware/*/*.pdf` (board PDFs are only written by `gen_pcb.py`, not by `verify.sh`).

- [ ] **Step 2: `hardware/README.md`** — add a "PCBs" section:

```markdown
## PCBs

Boards are generated once, then **the routed `.kicad_pcb` is the source** — edit it in KiCad's PCB
Editor freely. Rebuilding from scratch overwrites hand edits:

    hardware/tools/get_freerouting.sh                                   # once
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      hardware/tools/gen_pcb.py motion-carrier                          # or panel-carrier

`verify.sh` runs DRC with schematic parity on both boards. Fabrication zips for JLCPCB (2-layer,
1.6 mm, HASL) are in `<board>/fab/<board>-jlcpcb.zip`.

| Board | Size | Mounting |
| --- | --- | --- |
| motion carrier | 140 × 80 mm | 4× M3 for standard DIN-rail PCB clips |
| panel carrier | 80 × 55 mm | 4× M3 corners, standoffs |
```

Correct the sizes to whatever Tasks 3–4 actually produced. Add to "Open items": `ESP32 devkit row spacing assumed 25.4 mm — measure before ordering boards.` and `DIN-rail clip hole spacing — check against the clips bought.`

- [ ] **Step 3: `CLAUDE.md`** — change the `hardware/` row to: `` | `hardware/` | KiCad schematics (generated) and routed PCBs with JLCPCB fab zips — see hardware/README.md | ``

- [ ] **Step 4: Commit**

```bash
git add hardware/tools/verify.sh hardware/README.md CLAUDE.md
git commit -m "docs(hardware): document the PCBs and check them in verify.sh"
```
