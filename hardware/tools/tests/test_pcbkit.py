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

FIXTURES = Path(__file__).parent / "fixtures"
TEXT = (FIXTURES / "tiny.net").read_text()
ROUTABLE_TEXT = (FIXTURES / "routable.net").read_text()

CACHE = Path(__file__).resolve().parents[1] / ".cache"
JAR = next(CACHE.glob("freerouting-*.jar"), None) if CACHE.exists() else None


def flags(dsn, ses):
    return ["-de", str(dsn), "-do", str(ses), "-mp", "20", "--gui.enabled=false"]


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

    def test_save_round_trip_and_zones(self):
        b = self.build()
        b.ground_zones()
        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "tiny.kicad_pcb"
            b.save(pcb)
            loaded = pcbnew.LoadBoard(str(pcb))
        self.assertEqual(len(loaded.Zones()), 2)

    def test_rule_area_forbids_pour_tracks_and_vias(self):
        b = self.build()
        z = b.rule_area(30.0, 10.0, 40.0, 30.0)
        self.assertTrue(z.GetIsRuleArea())
        self.assertTrue(z.GetDoNotAllowZoneFills())
        self.assertTrue(z.GetDoNotAllowTracks())
        self.assertTrue(z.GetDoNotAllowVias())

    def test_dnp_and_datasheet_match_the_schematic(self):
        comps, pads = read_netlist(TEXT)
        b = self.build()
        b.place(comps["R2"], pads, 20.0, 10.0)
        self.assertTrue(b.fps["R2"].IsDNP())
        self.assertFalse(b.fps["R1"].IsDNP())
        self.assertEqual(b.fps["R10"].GetField(pcbnew.FIELD_T_DATASHEET).GetText(),
                         "https://example.com/r10.pdf")
        self.assertEqual(b.fps["R10"].GetField(pcbnew.FIELD_T_DESCRIPTION).GetText(),
                         "Test resistor")

    def test_footprints_keep_their_library_nickname(self):
        b = self.build()
        self.assertEqual(str(b.fps["R1"].GetFPID().GetLibNickname()), "Resistor_THT")

    def test_stitch_ground_skips_avoid_rectangles(self):
        b = pcbkit.BoardBuilder("stitch", 40.0, 30.0)
        b.ground_zones()
        pcbkit.apply_rules(b.board)
        with tempfile.TemporaryDirectory() as d:
            free, blocked = Path(d) / "free.kicad_pcb", Path(d) / "blocked.kicad_pcb"
            b.save(free)
            b.save(blocked)
            self.assertGreater(pcbkit.stitch_ground(free), 0)
            self.assertEqual(pcbkit.stitch_ground(blocked, avoid=[(0, 0, 40, 30)]), 0)


@unittest.skipIf(pcbkit is None, "needs KiCad's bundled python (pcbnew)")
class ApplyRulesTest(unittest.TestCase):
    def test_rules_reach_the_live_board_after_save_and_load(self):
        comps, pads = read_netlist(TEXT)
        b = pcbkit.BoardBuilder("tiny", 40.0, 30.0)
        b.place(comps["R1"], pads, 10.0, 10.0)
        b.place(comps["R10"], pads, 10.0, 20.0)
        pcbkit.apply_rules(b.board)
        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "tiny.kicad_pcb"
            b.save(pcb)
            loaded = pcbnew.LoadBoard(str(pcb))

        # GetAllNetClasses() keys are pcbnew.wxString, not plain str -- pcbnew's
        # wxString.__eq__ does not compare equal to a Python str of the same
        # text, so normalize with str() before indexing.
        classes = {str(name): nc for name, nc in loaded.GetAllNetClasses().items()}
        self.assertAlmostEqual(pcbnew.ToMM(classes["Power"].GetTrackWidth()), 0.6)
        self.assertAlmostEqual(pcbnew.ToMM(classes["Default"].GetTrackWidth()), 0.25)

        # +3V3 (R1 pin 1) and GND (R10 pin 2) both match a NET_CLASS_POWER pattern.
        v3v3 = loaded.FindNet("+3V3")
        gnd = loaded.FindNet("GND")
        self.assertIsNotNone(v3v3)
        self.assertIsNotNone(gnd)
        self.assertEqual(v3v3.GetNetClassName(), "Power")
        self.assertEqual(gnd.GetNetClassName(), "Power")

    def test_save_preserves_unrelated_pro_keys_across_reruns(self):
        comps, pads = read_netlist(TEXT)
        b = pcbkit.BoardBuilder("tiny", 40.0, 30.0)
        b.place(comps["R1"], pads, 10.0, 10.0)
        pcbkit.apply_rules(b.board)
        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "tiny.kicad_pcb"
            pro = Path(d) / "tiny.kicad_pro"
            pro.write_text(json.dumps({"schematic": {"x": 1}, "meta": {"filename": "tiny.kicad_pro"}}))
            b.save(pcb)
            after = json.loads(pro.read_text())
        self.assertEqual(after.get("schematic"), {"x": 1})
        classes = {c["name"]: c for c in after["net_settings"]["classes"]}
        self.assertEqual(classes["Power"]["track_width"], 0.6)
        self.assertEqual(classes["Default"]["clearance"], 0.25)


@unittest.skipUnless(pcbkit is not None and JAR is not None,
                      "needs pcbnew and a cached hardware/tools/.cache/freerouting-*.jar")
class FullFlowTest(unittest.TestCase):
    def test_power_nets_route_wide_default_nets_route_at_least_default_width(self):
        comps, pads = read_netlist(ROUTABLE_TEXT)
        b = pcbkit.BoardBuilder("routable", 50.0, 40.0)
        b.place(comps["R1"], pads, 10.0, 10.0)
        b.place(comps["R2"], pads, 35.0, 10.0)
        b.place(comps["R3"], pads, 10.0, 30.0)
        b.ground_zones()
        pcbkit.apply_rules(b.board)

        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "routable.kicad_pcb"
            pro = Path(d) / "routable.kicad_pro"
            # Stands in for the ~670 lines of real, schematic-derived settings a
            # real carrier's .kicad_pro already carries before pcbkit ever runs.
            pro.write_text(json.dumps({"schematic": {"x": 1}}))
            b.save(pcb)

            pcbkit.autoroute(pcb, JAR, flags)
            added = pcbkit.stitch_ground(pcb)
            self.assertGreater(added, 0)

            loaded = pcbnew.LoadBoard(str(pcb))
            after = json.loads(pro.read_text())

        power_tracks = [t for t in loaded.GetTracks()
                         if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "+3V3"]
        default_tracks = [t for t in loaded.GetTracks()
                           if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "/SIG"]
        self.assertTrue(power_tracks, "expected at least one routed +3V3 (Power) track")
        for t in power_tracks:
            self.assertAlmostEqual(pcbnew.ToMM(t.GetWidth()), 0.6, places=3)
        for t in default_tracks:
            self.assertGreaterEqual(pcbnew.ToMM(t.GetWidth()), 0.25 - 1e-6)

        # The pre-seeded arbitrary top-level key survived the whole
        # save -> autoroute -> stitch_ground pipeline, each of which saves.
        self.assertEqual(after.get("schematic"), {"x": 1})
        classes = {c["name"]: c for c in after["net_settings"]["classes"]}
        self.assertEqual(classes["Power"]["track_width"], 0.6)
