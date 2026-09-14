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

    def test_mounting_hole_has_no_net(self):
        b = self.build()
        hole = [f for f in b.board.GetFootprints() if f.GetReference().startswith("H")][0]
        self.assertTrue(list(hole.Pads()))
        for p in hole.Pads():
            self.assertEqual(p.GetNetCode(), 0)
            self.assertEqual(p.GetNetname(), "")

    def test_mounting_hole_records_its_centre(self):
        b = self.build()
        self.assertEqual(b.holes, [(35.0, 5.0)])

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
class GeometryTest(unittest.TestCase):
    def test_hole_rectangle_accepts_a_rectangle_in_any_order(self):
        holes = [(93.0, 56.5), (4.0, 4.0), (4.0, 56.5), (93.0, 4.0)]
        self.assertEqual(pcbkit.hole_rectangle(holes), (4.0, 4.0, 93.0, 56.5))

    def test_hole_rectangle_rejects_the_old_motion_pattern(self):
        with self.assertRaises(ValueError):
            pcbkit.hole_rectangle([(4.0, 4.0), (85.0, 4.0), (4.0, 62.0), (136.0, 62.0)])

    def test_hole_rectangle_rejects_wrong_count_and_duplicates(self):
        with self.assertRaises(ValueError):
            pcbkit.hole_rectangle([(4.0, 4.0), (8.0, 4.0), (4.0, 8.0)])
        with self.assertRaises(ValueError):
            pcbkit.hole_rectangle([(4.0, 4.0), (8.0, 4.0), (4.0, 8.0), (4.0, 8.0)])

    def test_rect_gap(self):
        self.assertEqual(pcbkit.rect_gap((0, 0, 1, 1), (0.5, 0.5, 2, 2)), 0.0)
        self.assertAlmostEqual(pcbkit.rect_gap((0, 0, 1, 1), (4, 0, 5, 1)), 3.0)
        self.assertAlmostEqual(pcbkit.rect_gap((0, 0, 1, 1), (4, 5, 5, 6)), 5.0)

    def test_carrier_hole_patterns_are_rectangles(self):
        import pcb_motion
        import pcb_panel
        self.assertEqual(pcbkit.hole_rectangle(pcb_motion.HOLES), (4.0, 4.0, 93.0, 56.5))
        self.assertEqual(pcbkit.hole_rectangle(pcb_panel.HOLES), (4.0, 4.0, 76.0, 58.0))

    def test_freerouting_jar_is_the_pinned_version_or_an_error(self):
        self.assertEqual(pcbkit.pinned_freerouting_version(), "v2.1.0")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "freerouting-9.9.9.jar").write_text("")   # a newer jar must not be picked
            with self.assertRaises(FileNotFoundError):
                pcbkit.freerouting_jar(d, "v2.1.0")
            (Path(d) / "freerouting-2.1.0.jar").write_text("")
            self.assertEqual(pcbkit.freerouting_jar(d, "v2.1.0").name, "freerouting-2.1.0.jar")


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

    def test_save_preserves_unrelated_pro_keys_across_repeated_load_save_cycles(self):
        comps, pads = read_netlist(TEXT)
        b = pcbkit.BoardBuilder("tiny", 40.0, 30.0)
        b.place(comps["R1"], pads, 10.0, 10.0)
        pcbkit.apply_rules(b.board)
        with tempfile.TemporaryDirectory() as d:
            pcb = Path(d) / "tiny.kicad_pcb"
            pro = Path(d) / "tiny.kicad_pro"
            pro.write_text(json.dumps({"schematic": {"x": 1}, "meta": {"filename": "tiny.kicad_pro"}}))
            b.save(pcb)
            # Same cycle autoroute() and stitch_ground() run: load, re-apply rules, save. Twice.
            for _ in range(2):
                loaded = pcbnew.LoadBoard(str(pcb))
                pcbkit.apply_rules(loaded)
                pcbkit._save_board(loaded, pcb)
            after = json.loads(pro.read_text())
        self.assertEqual(after.get("schematic"), {"x": 1})
        classes = {c["name"]: c for c in after["net_settings"]["classes"]}
        self.assertEqual(classes["Power"]["track_width"], pcbkit.POWER_TRACK_WIDTH)
        self.assertEqual(classes["Default"]["clearance"], pcbkit.CLEARANCE)


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
