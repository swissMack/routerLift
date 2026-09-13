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


def _text_bbox(x, y, text, size, justify):
    """A conservative estimate of a single line of text's bounding box in mm, from the
    same (x, y, justify, font size) kisch itself writes to the file - not a re-derivation
    of how kisch picks them, so this catches a real placement regression regardless of
    how the offset or justify is computed. Deliberately generous (assumes every
    character is as wide as the font is tall, and a full line-height above and below
    the anchor) so it only flags overlaps a human would actually see, not near misses."""
    x, y, size = float(x), float(y), float(size)
    width, height = len(text) * size, size * 1.6
    if "right" in justify:
        x0, x1 = x - width, x
    elif "left" in justify:
        x0, x1 = x, x + width
    else:
        x0, x1 = x - width / 2, x + width / 2
    return (x0, y - height / 2, x1, y + height / 2)


def _overlaps(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


class PowerNetLegibilityTest(unittest.TestCase):
    """The regression that prompted this: a 6-pin connector with a power net on every
    other pin (J4 in the real design - +3V3 on pins 1/3/5, STEP/DIR/ENABLE on 2/4/6)
    rendered its power nets' "+3V3" Value field directly on top of the neighbouring
    row's own label - confirmed by rendering the real design through kicad-cli, reading
    the PDF, and finding "STEP" and "+3V3" as literally overlapping glyphs. Reproduce
    the same shape (a power net's pin sandwiched between two signal pins, on the kind of
    pin-pointing-sideways connector every J1/J2/J4/J6/J7 in the real design uses) against
    a small fixture connector, and check by bounding box - not just by eye - that the
    power net's Value field does not overlap either neighbour's label. Also covers a
    power net whose own pin has no neighbour, and both power-symbol orientations
    (GND points "down" by default, +3V3/+5V/+24V point "up" - POWER_POINTS_DOWN)."""

    def _render(self):
        sym = kisch.box_symbol("J", ["1", "2", "3", "4"], [])
        l = Library(symbol_dir=FIXTURES, extra={"routerlift:J": sym})
        s = Sheet("p", "p", l)
        # Pin 1 = GND (no neighbour above it, like J1 pin 13 is not - this covers the
        # "last row" case too), pin 2 = a signal, pin 3 = +3V3 (sandwiched between two
        # signals, the exact shape that broke on J4), pin 4 = a signal.
        s.place("routerlift:J", "J1", "conn", (50.8, 50.8),
                {"1": "GND", "2": "SIG_TOP", "3": "+3V3", "4": "SIG_BOTTOM"})
        # Every signal net needs a second connection (validate() rejects a one-ended
        # net) - a second small connector elsewhere on the sheet, far from J1, does
        # that without adding anything near J1 that could itself cause an overlap.
        s.place("routerlift:J", "J2", "far", (152.4, 50.8), {"1": "SIG_TOP", "2": None,
                "3": "SIG_BOTTOM", "4": None})
        with tempfile.TemporaryDirectory() as d:
            Project("p", s, d).write()
            return parse((Path(d) / "p.kicad_sch").read_text())

    def test_power_value_field_does_not_overlap_a_neighbouring_row(self):
        tree = self._render()
        power_boxes = []
        for sym in findall(tree, "symbol"):
            lib_id = find(sym, "lib_id")[1]
            if not lib_id.startswith("power:"):
                continue
            value_prop = [p for p in findall(sym, "property") if p[1] == "Value"][0]
            at = find(value_prop, "at")
            justify = find(find(value_prop, "effects"), "justify")[1:]
            size = find(find(find(value_prop, "effects"), "font"), "size")[1]
            power_boxes.append(_text_bbox(at[1], at[2], value_prop[2], size, justify))
        label_boxes = []
        for item in findall(tree, "label"):
            at = find(item, "at")
            justify = find(find(item, "effects"), "justify")[1:]
            label_boxes.append(_text_bbox(at[1], at[2], item[1], 1.27, justify))
        self.assertEqual(len(power_boxes), 2, "expected GND and +3V3 Value fields")
        # 4, not 2: SIG_TOP and SIG_BOTTOM each get a label at J1 (near the power nets,
        # what this test is about) and a second one at J2 (the far end, added only to
        # satisfy validate()'s two-connections-per-net rule) - checking against both is
        # harmless since the J2 ones are 100mm away and can never overlap anything here.
        self.assertEqual(len(label_boxes), 4, "expected SIG_TOP and SIG_BOTTOM labels")
        for pb in power_boxes:
            for lb in label_boxes:
                self.assertFalse(_overlaps(pb, lb),
                                 "a power net's Value field overlaps a neighbouring "
                                 "row's label: %r vs %r" % (pb, lb))

    def test_power_value_field_has_no_vertical_justify(self):
        """Complements the bounding-box check above, which cannot catch this: adding a
        vertical ("top"/"bottom") justify component to a power symbol's Value field -
        the same justify plain net labels use safely - was tried and, on the real J4
        connector rendered through kicad-cli, placed the text at a visibly different
        (and overlapping) position than the same offset with no vertical justify. This
        isn't something derivable from the stored coordinates by any geometric model;
        it was only found by actually rendering and reading the PDF, so it can only be
        pinned here as a direct characterization of the stored justify, not re-derived."""
        tree = self._render()
        for sym in findall(tree, "symbol"):
            if not find(sym, "lib_id")[1].startswith("power:"):
                continue
            value_prop = [p for p in findall(sym, "property") if p[1] == "Value"][0]
            justify = find(find(value_prop, "effects"), "justify")[1:]
            self.assertNotIn("top", justify)
            self.assertNotIn("bottom", justify)


class FieldGapTest(unittest.TestCase):
    """The regression that prompted field_gap: U2 (Interface_Expansion:MCP23017x-x-SO) in
    the real panel-carrier design has a pin at local y=+2.54 (GPA7/INTB row) and another
    at y=-2.54 (GPB0/RESET row) - exactly STUB either side of its origin, which is also
    exactly where place()'s previous hardcoded Reference/Value offset landed. Rendered
    through kicad-cli this put "U2" on top of "GPA7" and "MCP23017 @0x20" on top of
    "GPB0", as literally overlapping glyphs. Reproduce the same shape (a part with a pin
    exactly STUB above and below its origin) against a small fixture and check, by
    bounding box, that a caller-supplied field_gap moves Reference/Value clear of both -
    and that omitting field_gap reproduces the exact previous (pre-parameter) offset, so
    every existing call site (motion_carrier.py and panel_carrier.py's other parts) is
    provably unaffected."""

    def _place(self, field_gap=None):
        # A 2-pin fixture with one pin exactly STUB above the origin and one exactly
        # STUB below it - the same shape that broke on U2, without needing the real
        # 28-pin symbol.
        sym = kisch.box_symbol("STRADDLE", ["TOP"], ["BOTTOM"])
        # box_symbol spaces rows GRID apart starting at (rows-1)*GRID from centre; with
        # one pin per side (rows=1) that puts both pins at y=0, so patch the fixture's
        # own pin "at" to +/-STUB to match the real regression shape exactly.
        for sub in findall(sym, "symbol"):
            for pin in findall(sub, "pin"):
                at = find(pin, "at")
                at[2] = kisch.STUB if find(pin, "name")[1] == "TOP" else -kisch.STUB
        l = Library(symbol_dir=FIXTURES, extra={"routerlift:STRADDLE": sym})
        s = Sheet("p", "p", l)
        kwargs = {} if field_gap is None else {"field_gap": field_gap}
        s.place("routerlift:STRADDLE", "U1", "STRADDLE", (50.8, 50.8),
                {"TOP": "A", "BOTTOM": "B"}, **kwargs)
        s.place("routerlift:STRADDLE", "U2", "STRADDLE", (101.6, 50.8),
                {"TOP": "A", "BOTTOM": "B"})
        with tempfile.TemporaryDirectory() as d:
            Project("p", s, d).write()
            return parse((Path(d) / "p.kicad_sch").read_text())

    def _field_box(self, tree, ref, name):
        for sym in findall(tree, "symbol"):
            props = {p[1]: p for p in findall(sym, "property")}
            if props.get("Reference", [None, None, ""])[2] == ref:
                p = props[name]
                at = find(p, "at")
                justify = find(find(p, "effects"), "justify")[1:]
                size = find(find(find(p, "effects"), "font"), "size")[1]
                return _text_bbox(at[1], at[2], p[2], size, justify)
        raise AssertionError("no symbol with Reference %r" % ref)

    def _pin_row_boxes(self, tree):
        """Bounding boxes of every net label kisch wrote - a proxy for "the part's own
        row", the same strategy PowerNetLegibilityTest uses, since kisch never writes a
        pin's own name/number text itself (KiCad draws that from the library symbol)."""
        boxes = []
        for lbl in findall(tree, "label"):
            at = find(lbl, "at")
            justify = find(find(lbl, "effects"), "justify")[1:]
            boxes.append(_text_bbox(at[1], at[2], lbl[1], 1.27, justify))
        return boxes

    def test_default_field_gap_matches_pre_parameter_offset(self):
        tree = self._place(field_gap=None)
        ref_box = self._field_box(tree, "U2", "Reference")
        val_box = self._field_box(tree, "U2", "Value")
        # Pre-parameter behaviour: Reference at (at.x+2.54, at.y-2.54), Value at
        # (at.x+2.54, at.y+2.54), both left-justified size 1.27 - reproduced exactly.
        self.assertEqual(ref_box, _text_bbox(104.14, 48.26, "U2", 1.27, ["left"]))
        self.assertEqual(val_box, _text_bbox(104.14, 53.34, "STRADDLE", 1.27, ["left"]))

    def test_field_gap_clears_the_parts_own_straddling_pins(self):
        tree = self._place(field_gap=12.7)
        ref_box = self._field_box(tree, "U1", "Reference")
        val_box = self._field_box(tree, "U1", "Value")
        for lb in self._pin_row_boxes(tree):
            self.assertFalse(_overlaps(ref_box, lb),
                             "Reference overlaps a pin row: %r vs %r" % (ref_box, lb))
            self.assertFalse(_overlaps(val_box, lb),
                             "Value overlaps a pin row: %r vs %r" % (val_box, lb))

    def test_default_power_flag_offset_matches_pre_parameter_behaviour(self):
        """A power net's flag (GND/+3V3/...) is a second, independent use of field_gap -
        it sets how far the flag's own Value text sits from its own arrow graphic (see
        place()'s docstring), not just the placed part's Reference/Value. Confirm the
        default (no field_gap passed to place()) reproduces the exact pre-parameter
        offset (tdx*STUB, tdy*STUB) for a power net's flag too."""
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "+3V3", "2": "GND"})
        with tempfile.TemporaryDirectory() as d:
            Project("t", s, d).write()
            tree = parse((Path(d) / "t.kicad_sch").read_text())
        flag = [sym for sym in findall(tree, "symbol")
                if find(sym, "lib_id")[1] == "power:+3V3"][0]
        value_prop = [p for p in findall(flag, "property") if p[1] == "Value"][0]
        at = find(value_prop, "at")
        # Pin 1 of Test:R2 points outward as (0, -1) (see
        # LibraryTest.test_pin_geometry): text_dir is (0, -1), so the pre-parameter
        # offset is (0*STUB, -1*STUB) from the flag's own wire-stub end.
        flag_at = find(flag, "at")
        self.assertEqual((float(at[1]), float(at[2])),
                         (float(flag_at[1]), round(float(flag_at[2]) - kisch.STUB, 4)))

    def test_field_gap_clears_a_power_flags_own_arrow(self):
        """The regression that prompted extending field_gap to power flags: J2/J4/J5 in
        the real panel-carrier design each put a +3V3 or +5V pin next to a GND pin on a
        connector whose pins point left (direction (-1, 0)) - and at that rotation, a
        +3V3/+5V flag's own Value text ("+3V3"/"+5V") overlaps its own arrow glyph's tip
        (GND's flag does not, at the identical offset - confirmed by rendering the real
        design through kicad-cli and reading the PDF, not derived). Reproduce the same
        direction and check that a larger field_gap moves the +3V3 flag's Value field
        further from its own origin than the default does, in the same outward
        direction - the concrete lever this test's regression was fixed with."""
        def value_pos(field_gap):
            l = lib()
            sym = kisch.box_symbol("H", ["1", "2"], [])
            l.extra["routerlift:H"] = sym
            s = Sheet("t", "t", l)
            kwargs = {} if field_gap is None else {"field_gap": field_gap}
            s.place("routerlift:H", "J1", "H", (50.8, 50.8), {"1": "+3V3", "2": "GND"},
                    **kwargs)
            with tempfile.TemporaryDirectory() as d:
                Project("t", s, d).write()
                tree = parse((Path(d) / "t.kicad_sch").read_text())
            flag = [sym for sym in findall(tree, "symbol")
                    if find(sym, "lib_id")[1] == "power:+3V3"][0]
            value_prop = [p for p in findall(flag, "property") if p[1] == "Value"][0]
            at = find(value_prop, "at")
            flag_at = find(flag, "at")
            return abs(float(at[1]) - float(flag_at[1])) + abs(float(at[2]) - float(flag_at[2]))
        self.assertAlmostEqual(value_pos(None), kisch.STUB)
        self.assertGreater(value_pos(5.08), value_pos(None))


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
