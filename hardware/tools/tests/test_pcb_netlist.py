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
        self.assertEqual(comps["R10"].datasheet, "https://example.com/r10.pdf")
        self.assertEqual(comps["R1"].datasheet, "")
        self.assertEqual(comps["R10"].description, "Test resistor")

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
