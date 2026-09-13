import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kisch
from kisch import Library, Project, Sheet, find, findall, parse, dump

FIXTURES = Path(__file__).parent / "fixtures"


def lib():
    return Library(symbol_dir=FIXTURES)


class SexprTest(unittest.TestCase):
    def test_roundtrip(self):
        text = '(a "b \\"q\\"" (c 1.5) yes (d "x\\ny"))'
        self.assertEqual(parse(dump(parse(text))), parse(text))

    def test_atoms_are_not_quoted(self):
        self.assertEqual(dump([kisch.Atom("at"), 1.27, 0, "s"]), '(at 1.27 0 "s")')

    def test_bool_dumps_yes_no(self):
        self.assertEqual(dump([kisch.Atom("hide"), True]), "(hide yes)")


class LibraryTest(unittest.TestCase):
    def test_extends_is_flattened(self):
        sym = lib().get("Test:RX")
        self.assertEqual(sym[1], "Test:RX")
        self.assertEqual([s[1] for s in findall(sym, "symbol")], ["RX_0_1", "RX_1_1"])
        values = {p[1]: p[2] for p in findall(sym, "property")}
        self.assertEqual(values["Value"], "RX")
        self.assertEqual(values["Description"], "derived")
        self.assertIsNone(find(sym, "extends"))

    def test_pins_per_unit(self):
        self.assertEqual(set(lib().pins("Test:G2", 1)), {"1", "2"})
        self.assertEqual(set(lib().pins("Test:G2", 2)), {"3", "4"})

    def test_pin_geometry(self):
        pin = lib().pins("Test:R2")["1"]
        self.assertEqual(kisch.pin_point((100, 100), 0, pin), (100, 96.19))
        self.assertEqual(kisch.pin_outward(0, pin), (0, -1))
        self.assertEqual(kisch.pin_point((100, 100), 90, pin), (96.19, 100))
        self.assertEqual(kisch.pin_outward(90, pin), (-1, 0))


class SheetTest(unittest.TestCase):
    def test_every_pin_must_be_assigned(self):
        s = Sheet("t", "t", lib())
        with self.assertRaisesRegex(ValueError, "unassigned"):
            s.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": "N1"})

    def test_pins_by_unique_name(self):
        s = Sheet("t", "t", lib())
        s.place("Test:G2", "U1", "G2", (50.8, 50.8), {"A": "IN", "Y": None}, unit=1)
        self.assertEqual(s.net_pins, {"IN": 1})

    def test_unknown_pin_lists_available(self):
        s = Sheet("t", "t", lib())
        with self.assertRaisesRegex(ValueError, "1=A"):
            s.place("Test:G2", "U1", "G2", (50.8, 50.8), {"Q": "X", "Y": None}, unit=1)


class ProjectTest(unittest.TestCase):
    def test_single_connection_net_rejected(self):
        s = Sheet("p", "p", lib())
        s.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": "A", "2": "B"})
        s.place("Test:R2", "R?", "1k", (76.2, 50.8), {"1": "A", "2": None})
        with self.assertRaisesRegex(ValueError, "B"):
            Project("p", s, "/nonexistent").validate()

    def test_duplicate_fixed_reference_rejected(self):
        child = Sheet("c", "c", lib())
        child.port("P", "passive")
        child.place("Test:R2", "R9", "1k", (50.8, 50.8), {"1": "P", "2": "P"})
        root = Sheet("p", "p", lib())
        root.place("Test:R2", "R?", "1k", (25.4, 25.4), {"1": "X", "2": "Y"})
        root.add_child(child, "a", (101.6, 50.8), {"P": "X"})
        root.add_child(child, "b", (101.6, 76.2), {"P": "Y"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            Project("p", root, "/nonexistent").annotate()

    def test_write_hierarchy(self):
        child = Sheet("c", "child", lib())
        child.port("P", "passive")
        child.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": "P", "2": "P"})
        root = Sheet("p", "root", lib())
        root.place("Test:R2", "R?", "1k", (25.4, 25.4), {"1": "X", "2": "Y"})
        root.add_child(child, "a", (101.6, 50.8), {"P": "X"})
        root.add_child(child, "b", (101.6, 76.2), {"P": "Y"})
        with tempfile.TemporaryDirectory() as d:
            Project("p", root, d).write()
            top = parse((Path(d) / "p.kicad_sch").read_text())
            sub = parse((Path(d) / "c.kicad_sch").read_text())
            self.assertTrue((Path(d) / "p.kicad_pro").exists())
        self.assertEqual([s[1] for s in findall(find(top, "lib_symbols"), "symbol")], ["Test:R2"])
        self.assertEqual(len(findall(top, "sheet")), 2)
        self.assertIsNotNone(find(top, "sheet_instances"))
        self.assertIsNone(find(sub, "sheet_instances"))
        paths = findall(find(find(find(sub, "symbol"), "instances"), "project"), "path")
        self.assertEqual(len(paths), 2)
        refs = sorted(find(p, "reference")[1] for p in paths)
        self.assertEqual(refs, ["R2", "R3"])
        self.assertIn("X", [l[1] for l in findall(top, "label")])
        self.assertEqual({l[1] for l in findall(sub, "hierarchical_label")}, {"P"})

    def test_globals_counted_across_sheets(self):
        a = Sheet("a", "a", lib(), globals=("G",))
        a.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": "G", "2": None})
        root = Sheet("p", "p", lib())
        root.add_child(a, "a", (101.6, 50.8), {})
        with self.assertRaisesRegex(ValueError, "global net G"):
            Project("p", root, "/nonexistent").validate()


class FieldRotationTest(unittest.TestCase):
    """KiCad renders a symbol property's stored angle combined with the parent
    symbol's rotation, but not by simple (parent + stored) % 360 addition - that
    was tried and disproved by rendering a probe schematic in kicad-cli: e.g. a
    stored angle of 0 renders upright at parent rotation 0 AND at 180, while a
    stored angle of 180 renders upside down at both. Empirically (verified by
    rendering all 16 parent x stored combinations of 0/90/180/270 to PDF), text
    renders upright exactly when: stored == 0 and parent % 180 == 0, or
    stored == 90 and parent % 180 == 90. kisch must pick the stored angle that
    satisfies this so field text (references, values - e.g. a power-flag
    "GND"/"+5V") never renders sideways or upside down, which is how two power
    nets a few pins apart on a rotated connector row ended up as overlapping
    garbled text."""

    def _value_angle(self, rot):
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "A", "2": "B"}, rot=rot)
        tree = s.to_sexpr("p", ["/x"], {("/x", s.parts[0]["uuid"]): "R1"}, {}, True)
        sym = find(tree, "symbol")
        self.assertEqual(find(sym, "at")[3], rot)
        value_prop = [p for p in findall(sym, "property") if p[1] == "Value"][0]
        return find(value_prop, "at")[3]

    def test_property_angle_upright_at_0(self):
        self.assertEqual(self._value_angle(0), 0)

    def test_property_angle_upright_at_90(self):
        self.assertEqual(self._value_angle(90), 90)

    def test_property_angle_upright_at_180(self):
        # The regression: a naive counter-rotation ((-rot) % 360) gives 180 here,
        # which kicad-cli renders upside down - confirmed by direct PDF rendering.
        self.assertEqual(self._value_angle(180), 0)

    def test_property_angle_upright_at_270(self):
        self.assertEqual(self._value_angle(270), 90)


class BoxSymbolTest(unittest.TestCase):
    def test_box_pins_on_grid(self):
        sym = kisch.box_symbol("PSU", ["L", "N", "PE"], ["V+", "V-"])
        l = Library(symbol_dir=FIXTURES, extra={"routerlift:PSU": sym})
        pins = l.pins("routerlift:PSU")
        self.assertEqual([p.name for p in pins.values()], ["L", "N", "PE", "V+", "V-"])
        for p in pins.values():
            self.assertAlmostEqual((p.y / 1.27) % 1, 0)
        self.assertEqual(pins["1"].x, -15.24)
        self.assertEqual(pins["4"].angle, 180)


if __name__ == "__main__":
    unittest.main()
