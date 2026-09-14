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

    def test_field_gap_does_not_move_a_power_flags_own_arrow_distance(self):
        """The ruling from the final fix wave: field_gap and a power flag's own
        Value-to-arrow distance are deliberately DECOUPLED (see place()'s field_gap
        docstring and _symbol()'s comment). This used to be the opposite - field_gap
        was the lever that fixed J2/J4/J5's +3V3/+5V flags overlapping their own
        arrow's tip - but a part placed with a large field_gap for its OWN
        Reference/Value clearance (U2 here, field_gap=27.94; the large system.py
        boxes) then dragged its power flags' "GND"/"+3V3" Value text 24-28mm away
        from their own arrow too, which is worse. So a power flag's Value now keeps
        the fixed pre-parameter STUB gap regardless of field_gap - confirmed here by
        checking a large field_gap changes nothing about that distance. (The separate
        "+" hidden behind the arrow's tip - the actual J2/J4/J5 regression - is now
        fixed generically in kisch instead: see RisingArrowPlusVisibilityTest.)"""
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
        self.assertAlmostEqual(value_pos(27.94), kisch.STUB)


class FieldsOverrideTest(unittest.TestCase):
    """place()'s fields= kwarg (panel_carrier.py's 74LVC14, which reuses the stock
    74HC14 symbol under a different Value and needs its own Datasheet/Description,
    not the HC part's own) must OVERRIDE a same-named default property (Datasheet is
    always emitted, empty, by _symbol()) rather than emit a second, duplicate
    property of the same name - and still add a genuinely new field (Description,
    which has no default) as before."""

    def _props(self, fields):
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "A", "2": "B"}, fields=fields)
        tree = s.to_sexpr("p", ["/x"], {("/x", s.parts[0]["uuid"]): "R1"}, {}, True)
        sym = find(tree, "symbol")
        return findall(sym, "property")

    def test_fields_overrides_an_existing_default_property(self):
        props = self._props({"Datasheet": "https://example.com/lvc14.pdf"})
        datasheets = [p for p in props if p[1] == "Datasheet"]
        self.assertEqual(len(datasheets), 1, "expected exactly one Datasheet property")
        self.assertEqual(datasheets[0][2], "https://example.com/lvc14.pdf")

    def test_fields_still_adds_a_genuinely_new_property(self):
        props = self._props({"Description": "Hex Schmitt-trigger inverter"})
        descriptions = [p for p in props if p[1] == "Description"]
        self.assertEqual(len(descriptions), 1)
        self.assertEqual(descriptions[0][2], "Hex Schmitt-trigger inverter")

    def test_omitting_fields_is_unaffected(self):
        props = self._props(None)
        self.assertEqual([p[2] for p in props if p[1] == "Datasheet"], [""])


class JogTest(unittest.TestCase):
    """The Critical regression from Task 4 review round 1: on hardware/tools/system.py's
    generated box symbols, a POWER_NET pin (GND/+5V) directly above a plain-net pin has
    its own arrow/ground-symbol graphic - not just its Value text, which
    PowerNetLegibilityTest already covers - overlap the plain pin's own label text, on
    both left- and right-pointing rows. Confirmed by rendering the real system project
    through kicad-cli: MOTION_CARRIER's RELAY_GND/RELAY_IN, RELAY_MODULE's GND/RELAY_IN,
    LIMIT_SWITCH_NC's GND/HOME_SIG or TOP_SIG, FOOT_PEDAL's two GND/FOOT_* pairs,
    STOP_BUTTON's GND/STOP_SIG, PANEL_CARRIER's LINK_GND/LINK_TX and MPG_GND/MPG_A,
    DISPLAY_JC4827W543C's P1_GND/LEAD_P3, and MPG_ZS80's GND/MPG_A all show the same
    failure. Mechanism: a power flag's shape (the stock "power:GND"/"power:+5V"
    polyline) is centred on its own row and reaches about half of box_symbol()'s 2.54mm
    row pitch either side of it; a plain label is justified against the *bottom* of its
    anchor point (see label()), so it grows upward, toward the row above. The two
    reaches meet almost exactly at the row boundary by construction - stub length
    (POWER_STUB vs STUB) only moves things *along* the wire, not perpendicular to it, so
    it cannot fix this. Reproduce the same shape - a 2-row box_symbol() with a power net
    on row 1 and a plain net on row 2 - on both sides, using the real "power:GND"
    polyline geometry (fixtures/power.kicad_sym matches the stock library's shape), and
    check by bounding box (not by eye) that it overlaps without a jog and clears with
    one, in both orientations."""

    def _polyline_bbox(self, l, lib_id, at, rot):
        """Bounding box (sheet mm) of a power symbol's own drawn polyline(s), after
        kisch's rigid-body part rotation - the same transform pin_point() applies to
        pins, applied here to the symbol's graphics instead, since KiCad rotates a
        symbol's pins and its artwork together as one rigid body (confirmed against
        the real design: see place()'s jog docstring)."""
        sym = l.get(lib_id)
        xs, ys = [], []
        for sub in findall(sym, "symbol"):
            for poly in findall(sub, "polyline"):
                for xy in find(poly, "pts")[1:]:
                    fake = kisch.Pin("", "", "", float(xy[1]), float(xy[2]), 0)
                    x, y = kisch.pin_point(at, rot, fake)
                    xs.append(x)
                    ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _label_bbox(x, y, text, size, justify):
        """Like the module-level _text_bbox, but - unlike that one - actually honours
        a vertical ("top"/"bottom") justify component instead of always centring:
        needed here because the mechanism under test IS the vertical justify (a plain
        label is anchored at the *bottom* of its text, so it grows upward - see
        label()), which _text_bbox's centred approximation cannot see. Kept local to
        this test rather than changing the shared _text_bbox, which every other test
        in this file already relies on at its current (centred) precision."""
        x, y, size = float(x), float(y), float(size)
        width, height = len(text) * size, size * 1.6
        if "right" in justify:
            x0, x1 = x - width, x
        elif "left" in justify:
            x0, x1 = x, x + width
        else:
            x0, x1 = x - width / 2, x + width / 2
        if "bottom" in justify:
            y0, y1 = y - height, y
        elif "top" in justify:
            y0, y1 = y, y + height
        else:
            y0, y1 = y - height / 2, y + height / 2
        return (x0, y0, x1, y1)

    def _render(self, side, extra):
        # A 2-row box_symbol(): GND on row 1 (top, local y = +GRID), a plain net on
        # row 2 (bottom, local y = -GRID) - the exact shape every failing box above
        # has, regardless of how many other rows surround it. The plain net's name
        # ("RELAY_IN", the real one from MOTION_CARRIER) matters: it must be long
        # enough that its label text reaches back to where GND's own longer-stub flag
        # sits, exactly as it does in the real design - a short name like "SIG" does
        # not reach that far and would not reproduce the collision. `side` puts both
        # pins on the left (direction (-1, 0)) or the right (direction (1, 0)).
        left, right = (["GND", "RELAY_IN"], []) if side == "left" else ([], ["GND", "RELAY_IN"])
        sym = kisch.box_symbol("J", left, right)
        l = Library(symbol_dir=FIXTURES, extra={"routerlift:J": sym})
        s = Sheet("p", "p", l)
        s.place("routerlift:J", "J1", "j", (50.8, 50.8),
                {"GND": "GND", "RELAY_IN": "RELAY_IN"}, jog={"GND": extra})
        # RELAY_IN needs a second connection (validate() rejects a one-ended net); GND
        # is a power net so it needs none.
        s.place("routerlift:J", "J2", "far", (152.4, 50.8),
                {"GND": "GND", "RELAY_IN": "RELAY_IN"})
        with tempfile.TemporaryDirectory() as d:
            Project("p", s, d).write()
            tree = parse((Path(d) / "p.kicad_sch").read_text())
        gnd = [sym for sym in findall(tree, "symbol")
               if find(sym, "lib_id")[1] == "power:GND"
               and abs(float(find(sym, "at")[1]) - 50.8) < 30][0]
        gnd_at = find(gnd, "at")
        gnd_box = self._polyline_bbox(l, "power:GND",
                                       (float(gnd_at[1]), float(gnd_at[2])),
                                       float(gnd_at[3]))
        sig_boxes = []
        for lbl in findall(tree, "label"):
            at = find(lbl, "at")
            if lbl[1] == "RELAY_IN" and abs(float(at[1]) - 50.8) < 30:
                justify = find(find(lbl, "effects"), "justify")[1:]
                sig_boxes.append(self._label_bbox(at[1], at[2], "RELAY_IN", 1.27, justify))
        self.assertEqual(len(sig_boxes), 1, "expected exactly one RELAY_IN label near J1")
        return gnd_box, sig_boxes[0]

    def test_power_directly_above_plain_overlaps_without_a_jog_left_side(self):
        gnd_box, sig_box = self._render("left", extra=0)
        self.assertTrue(_overlaps(gnd_box, sig_box),
                         "expected the un-jogged fixture to reproduce the collision: "
                         "%r vs %r" % (gnd_box, sig_box))

    def test_power_directly_above_plain_overlaps_without_a_jog_right_side(self):
        gnd_box, sig_box = self._render("right", extra=0)
        self.assertTrue(_overlaps(gnd_box, sig_box),
                         "expected the un-jogged fixture to reproduce the collision: "
                         "%r vs %r" % (gnd_box, sig_box))

    def test_jog_clears_the_collision_left_side(self):
        # Left-side pins point in direction (-1, 0); perpendicular is (0, -1) (see
        # place()'s jog docstring), so a positive extra moves GND toward smaller sheet
        # y - up and away from SIG, which sits below it (larger sheet y).
        gnd_box, sig_box = self._render("left", extra=2 * kisch.GRID)
        self.assertFalse(_overlaps(gnd_box, sig_box),
                          "GND still overlaps SIG after jogging: %r vs %r"
                          % (gnd_box, sig_box))

    def test_jog_clears_the_collision_right_side(self):
        # Right-side pins point in direction (1, 0); perpendicular is (0, 1), so a
        # negative extra moves GND up and away from SIG here instead.
        gnd_box, sig_box = self._render("right", extra=-2 * kisch.GRID)
        self.assertFalse(_overlaps(gnd_box, sig_box),
                          "GND still overlaps SIG after jogging: %r vs %r"
                          % (gnd_box, sig_box))

    def test_omitting_jog_draws_the_same_single_straight_wire_as_before(self):
        """Every existing caller (motion_carrier.py, panel_carrier.py, and every
        place() call in system.py that doesn't need a jog) omits `jog` entirely, and
        must see the exact single straight wire place() always drew."""
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "A", "2": "B"})
        wires = findall(s.items, "wire")
        self.assertEqual(len(wires), 2)
        for w in wires:
            self.assertEqual(len(find(w, "pts")) - 1, 2)

    def test_zero_jog_also_draws_a_single_straight_wire(self):
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "A", "2": "B"}, jog={"1": 0})
        wires = findall(s.items, "wire")
        self.assertEqual(len(wires), 2)
        for w in wires:
            self.assertEqual(len(find(w, "pts")) - 1, 2)

    def test_jog_never_draws_a_zero_length_wire(self):
        """place()'s jog cascade draws point -> mid -> jogged -> end, where `end` is
        `jogged` moved by (stub - STUB) along the pin's own outward direction. For a
        PLAIN net (stub == STUB - every net that is not itself a POWER_NET or a
        declared global) that offset is exactly 0, so end == jogged and the third
        wire has identical endpoints - confirmed on the real low-voltage.kicad_sch,
        which has 19 of these (system.py's power_plain_jogs jogs the plain net
        directly below a power pin whose own row above is also a power pin, e.g.
        MOTION_CARRIER's ENA-/RELAY_5V/RELAY_GND run). Reproduce with place() jogging
        a plain net directly and check no wire kisch wrote has equal endpoints."""
        s = Sheet("t", "t", lib())
        s.place("Test:R2", "R1", "1k", (50.8, 50.8), {"1": "A", "2": "B"},
                jog={"1": 2 * kisch.GRID})
        for w in findall(s.items, "wire"):
            pts = find(w, "pts")
            p1, p2 = tuple(pts[1][1:]), tuple(pts[2][1:])
            self.assertNotEqual(p1, p2, "zero-length wire: %r" % (w,))


class RisingArrowPlusVisibilityTest(unittest.TestCase):
    """The regression, found in two halves:

    Half 1 - a RISING-arrow power net (+3V3/+5V/+24V) whose pin points left
    (text_dir == (-1, 0)) put its Value text's leading "+" glyph under its own
    arrowhead's sharp tip - confirmed by rendering motion-carrier J3/J4/J5 and the
    panel carrier's own +3V3/+5V flags through kicad-cli: it read "<3V3", the "+"
    invisible.

    Half 2 - found only AFTER fixing half 1 and re-rendering the real system project
    for the legibility check this fix wave required: GND, pointing RIGHT
    (text_dir == (1, 0)) - the opposite net, the opposite direction - has the exact
    same failure ("GND" struck through by its own arrow), on system.py's
    MOTION_CARRIER box (M11's RELAY_GND). An earlier version of this fix special-cased
    "rising arrow, direction (-1, 0)" and missed this half entirely.

    Both halves turn out to be ONE case, not two: label() computes each flag's own
    rotation via _rotation(base, direction), and that rotation is 90 degrees for
    BOTH failures (GND's base is the opposite of a rising arrow's, so the same 90
    degrees falls at the opposite text_dir) and only ever 0/180/270 for every other
    (net, direction) combination - confirmed by enumerating all 4 directions x all 4
    POWER_NETS members (see the fix wave's report). So the fix keys on part["rot"]
    == 90 alone, not on lib_id or text_dir, and covers every net/direction pair with
    one check.

    This is NOT checked here by re-deriving a bounding box the way
    PowerNetLegibilityTest and JogTest do for their own regressions: the property
    that broke is the stored 90 degree field angle (see FieldRotationTest's own
    comment on this being a KiCad rendering quirk with no documented model) combined
    with a *rotated* justify meaning that does not match the plain left-grows-right /
    right-grows-left textbook convention _text_bbox assumes for angle-0 text - the
    same category of "not derivable, only found by rendering" quirk _symbol()'s
    comment on vertical justify already warns about
    (test_power_value_field_has_no_vertical_justify pins that one the same way, by
    asserting the known-good justify directly rather than a bbox). So this pins the
    known-good *justify choice* the fix makes for all four (net-shape, direction)
    combinations that reach rot 90 or rot 270 - confirmed correct by rendering, not
    modelled geometrically - and that the offset magnitude (still exactly STUB, in
    the same text_dir direction) is otherwise unchanged by it."""

    def _flag_value(self, net, pin):
        l = lib()
        s = Sheet("t", "t", l)
        # Test:G2's pin "A" (angle 0) has pin_outward (-1, 0); pin "Y" (angle 180) has
        # pin_outward (1, 0) - the two horizontal directions this regression needs
        # (see LibraryTest.test_pin_geometry's sibling cases and box_symbol()'s left-
        # and right-side pins, which use the same two angles).
        other = "Y" if pin == "A" else "A"
        s.place("Test:G2", "U1", "G2", (50.8, 50.8), {pin: net, other: "OTHER"}, unit=1)
        s.place("Test:G2", "U2", "G2", (101.6, 50.8), {pin: "OTHER", other: None}, unit=1)
        with tempfile.TemporaryDirectory() as d:
            Project("t", s, d).write()
            tree = parse((Path(d) / "t.kicad_sch").read_text())
        lib_id = kisch.POWER_NETS[net]
        flag = [sym for sym in findall(tree, "symbol") if find(sym, "lib_id")[1] == lib_id][0]
        flag_at = find(flag, "at")
        value_prop = [p for p in findall(flag, "property") if p[1] == "Value"][0]
        at = find(value_prop, "at")
        justify = find(find(value_prop, "effects"), "justify")[1:]
        offset = (round(float(at[1]) - float(flag_at[1]), 4),
                 round(float(at[2]) - float(flag_at[2]), 4))
        return int(flag_at[3]), offset, list(justify)

    def test_rising_arrow_pointing_left_gets_the_flipped_justify(self):
        rot, offset, justify = self._flag_value("+3V3", "A")
        self.assertEqual(rot, 90)
        self.assertEqual(offset, (-kisch.STUB, 0))
        self.assertEqual(justify, ["left"])

    def test_rising_arrow_pointing_right_keeps_the_ordinary_justify(self):
        rot, offset, justify = self._flag_value("+3V3", "Y")
        self.assertEqual(rot, 270)
        self.assertEqual(offset, (kisch.STUB, 0))
        self.assertEqual(justify, ["left"])

    def test_gnd_pointing_right_gets_the_flipped_justify(self):
        rot, offset, justify = self._flag_value("GND", "Y")
        self.assertEqual(rot, 90)
        self.assertEqual(offset, (kisch.STUB, 0))
        self.assertEqual(justify, ["right"])

    def test_gnd_pointing_left_keeps_the_ordinary_justify(self):
        rot, offset, justify = self._flag_value("GND", "A")
        self.assertEqual(rot, 270)
        self.assertEqual(offset, (-kisch.STUB, 0))
        self.assertEqual(justify, ["right"])


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


class GlobalNetStubTest(unittest.TestCase):
    """A global label's own shape (the hex/chevron body plus its Intersheetrefs
    text) is taller than the 2.54mm row pitch box_symbol() (and similarly dense
    parts) use between pins - confirmed by rendering the system project's
    PSU_24_36V and CONTACTOR boxes through kicad-cli: a global net one row away
    from a plain-labelled neighbour landed squarely on that neighbour's own label,
    the same failure mode POWER_STUB already exists to fix for power nets. See
    kisch.py place()'s `stub` line."""

    def _stub_length(self, s, net, globals_=()):
        s.place("Test:R2", "R?", "1k", (50.8, 50.8), {"1": net, "2": None})
        wire = findall(s.items, "wire")[0]
        pts = find(wire, "pts")
        p1, p2 = pts[1][1:], pts[2][1:]
        return abs(p2[1] - p1[1])

    def test_global_net_gets_the_longer_power_stub(self):
        s = Sheet("t", "t", lib(), globals=("G",))
        self.assertAlmostEqual(self._stub_length(s, "G"), kisch.POWER_STUB)

    def test_non_global_net_on_the_same_sheet_keeps_the_default_stub(self):
        s = Sheet("t", "t", lib(), globals=("G",))
        self.assertAlmostEqual(self._stub_length(s, "OTHER"), kisch.STUB)

    def test_a_sheet_that_declares_no_globals_is_unaffected(self):
        """Sheet(globals=...) defaults to empty, so a sheet that never opts in -
        every sheet before this task's system.py - sees no change at all: neither
        motion-carrier.py nor panel-carrier.py pass globals, and both regenerate
        byte-identical (checked by hand, not by this suite)."""
        s = Sheet("t", "t", lib())
        self.assertAlmostEqual(self._stub_length(s, "G"), kisch.STUB)


if __name__ == "__main__":
    unittest.main()
