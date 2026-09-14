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
