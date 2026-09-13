"""kisch - write KiCad schematics from Python.

Parts connect by net name: every pin gets a short wire stub that ends in a
label, a power symbol or a no-connect flag. There is no wire routing.
"""
import collections
import copy
import json
import math
import os
import re
import uuid
from pathlib import Path

KICAD_SYMBOL_DIR = Path(os.environ.get(
    "KICAD_SYMBOL_DIR",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"))
FORMAT_VERSION = "20250114"
DATE = "2026-09-13"
GRID = 1.27
STUB = 2.54
# A power net's stub is longer than a signal net's: on a dense, multi-row connector
# (a power net on every other pin, e.g. a GND return alongside each signal) the usual
# STUB places the power symbol's Value text ("GND", "+5V", ...) right where the next
# row's own pin number or label already lives - a short stub can't out-distance that
# regardless of the field's own offset. See kisch.py Sheet._symbol for the matching
# field placement, and test_kisch.py PowerNetLegibilityTest for the case this covers.
POWER_STUB = STUB * 3
POWER_NETS = {"+3V3": "power:+3V3", "+5V": "power:+5V", "+24V": "power:+24V", "GND": "power:GND"}
POWER_POINTS_DOWN = {"power:GND"}
# label()'s own angle -> reading-side mapping, reused so a power symbol's Value field
# grows away from its pin (further out along the stub) instead of back toward the row
# it came from, which is what collides with a neighbouring pin's number or label.
_DIR_SIDE = {(1, 0): "left", (0, -1): "left", (-1, 0): "right", (0, 1): "right"}
NS = uuid.UUID("5b0f5d6e-3c1a-4e8e-9b7a-2f6c1d0a9e42")

Pin = collections.namedtuple("Pin", "number name etype x y angle")


# ------------------------------------------------------------ s-expressions

class Atom(str):
    """A bare token, written without quotes."""


A = Atom
_TOKEN = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')


def _unescape(s):
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), s)


def parse(text):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif t.startswith('"'):
            stack[-1].append(_unescape(t[1:-1]))
        else:
            stack[-1].append(Atom(t))
    return stack[0][0]


def _num(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def dump(e, indent=0):
    if isinstance(e, list):
        head = []
        i = 0
        while i < len(e) and not isinstance(e[i], list):
            head.append(dump(e[i]))
            i += 1
        out = "(" + " ".join(head)
        for x in e[i:]:
            out += "\n" + "\t" * (indent + 1) + dump(x, indent + 1)
        return out + ")"
    if isinstance(e, Atom):
        return str(e)
    if isinstance(e, bool):
        return "yes" if e else "no"
    if isinstance(e, (int, float)):
        return _num(e)
    return '"' + e.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def find(e, key):
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def findall(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def _uid(key):
    return str(uuid.uuid5(NS, key))


def _snap(v):
    return round(round(v / GRID) * GRID, 4)


def _font(size=1.27, hide=False, justify=None):
    e = [A("effects"), [A("font"), [A("size"), size, size]]]
    if justify:
        e.append([A("justify")] + [A(j) for j in justify])
    if hide:
        e.append([A("hide"), True])
    return e


# ----------------------------------------------------------------- symbols

class Library:
    def __init__(self, symbol_dir=KICAD_SYMBOL_DIR, extra=None):
        self.dir = Path(symbol_dir)
        self.extra = dict(extra or {})
        self._files = {}

    def _symbols(self, lib):
        if lib not in self._files:
            tree = parse((self.dir / (lib + ".kicad_sym")).read_text(encoding="utf-8"))
            self._files[lib] = {s[1]: s for s in findall(tree, "symbol")}
        return self._files[lib]

    def get(self, lib_id):
        """The symbol flattened and named lib_id, as a schematic embeds it."""
        if lib_id in self.extra:
            return copy.deepcopy(self.extra[lib_id])
        lib, name = lib_id.split(":", 1)
        symbols = self._symbols(lib)
        if name not in symbols:
            raise KeyError("symbol %s not found in %s.kicad_sym" % (name, lib))
        sym = copy.deepcopy(symbols[name])
        ext = find(sym, "extends")
        if ext is None:
            sym[1] = lib_id
            return sym
        parent = self.get(lib + ":" + ext[1])
        own = collections.OrderedDict((p[1], p) for p in findall(sym, "property"))
        out = [A("symbol"), lib_id]
        last_prop = 1
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == "property":
                out.append(own.pop(item[1], item))
                last_prop = len(out)
            elif isinstance(item, list) and item[0] == "symbol":
                item[1] = name + item[1][len(ext[1]):]
                out.append(item)
            else:
                out.append(item)
        out[last_prop:last_prop] = list(own.values())
        return out

    def pins(self, lib_id, unit=1):
        """{number: Pin} for one unit plus the shared unit 0, body style 1."""
        result = collections.OrderedDict()
        for sub in findall(self.get(lib_id), "symbol"):
            m = re.search(r"_(\d+)_(\d+)$", sub[1])
            u, style = int(m.group(1)), int(m.group(2))
            if u not in (0, unit) or style not in (0, 1):
                continue
            for p in findall(sub, "pin"):
                at = find(p, "at")
                number = str(find(p, "number")[1])
                result[number] = Pin(number, str(find(p, "name")[1]), str(p[1]),
                                     float(at[1]), float(at[2]),
                                     float(at[3]) if len(at) > 3 else 0.0)
        return result


def pin_point(at, rot, pin):
    r = math.radians(rot)
    x = pin.x * math.cos(r) - pin.y * math.sin(r)
    y = pin.x * math.sin(r) + pin.y * math.cos(r)
    return (round(at[0] + x, 4), round(at[1] - y, 4))


def pin_outward(rot, pin):
    a = math.radians(pin.angle + 180 + rot)
    return (int(round(math.cos(a))), -int(round(math.sin(a))))


def _rotation(base, direction):
    def ang(v):
        return math.degrees(math.atan2(-v[1], v[0]))
    return int(round(ang(direction) - ang(base))) % 360


def box_symbol(name, left, right, lib="routerlift"):
    """A labelled rectangle with passive pins: left side, then right side."""
    rows = max(len(left), len(right), 1)
    half_h = round(GRID * (rows + 1), 4)
    pins = []
    n = 0
    for side, names in ((-1, left), (1, right)):
        for i, pname in enumerate(names):
            n += 1
            y = round(GRID * (rows - 1 - 2 * i), 4)
            pins.append([A("pin"), A("passive"), A("line"),
                         [A("at"), side * 15.24, y, 0 if side < 0 else 180],
                         [A("length"), 2.54],
                         [A("name"), pname, _font()], [A("number"), str(n), _font()]])
    return [A("symbol"), lib + ":" + name,
            [A("pin_names"), [A("offset"), 1.016]],
            [A("exclude_from_sim"), False], [A("in_bom"), True], [A("on_board"), True],
            [A("property"), "Reference", "M", [A("at"), 0, half_h + 1.27, 0], _font()],
            [A("property"), "Value", name, [A("at"), 0, -half_h - 1.27, 0], _font()],
            [A("property"), "Footprint", "", [A("at"), 0, 0, 0], _font(hide=True)],
            [A("property"), "Datasheet", "", [A("at"), 0, 0, 0], _font(hide=True)],
            [A("symbol"), name + "_0_1",
             [A("rectangle"), [A("start"), -12.7, half_h], [A("end"), 12.7, -half_h],
              [A("stroke"), [A("width"), 0.254], [A("type"), A("default")]],
              [A("fill"), [A("type"), A("background")]]]],
            [A("symbol"), name + "_1_1"] + pins]


def write_symbol_library(path, symbols):
    tree = [A("kicad_symbol_lib"), [A("version"), A("20241209")],
            [A("generator"), "routerlift_gen_schematics"]]
    for sym in symbols:
        s = copy.deepcopy(sym)
        s[1] = s[1].split(":", 1)[1]
        tree.append(s)
    Path(path).write_text(dump(tree) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ sheets

class Sheet:
    def __init__(self, name, title, lib, paper="A3", globals=()):
        self.name, self.title, self.lib, self.paper = name, title, lib, paper
        self.globals = set(globals)
        self.filename = name + ".kicad_sch"
        self.parts, self.items, self.children = [], [], []
        self.ports = collections.OrderedDict()
        self.net_pins = collections.OrderedDict()
        self._n = 0
        self.uuid = self._next("sheet")

    def _next(self, key=""):
        self._n += 1
        return _uid("%s/%s/%d" % (self.name, key, self._n))

    def _count(self, net):
        self.net_pins[net] = self.net_pins.get(net, 0) + 1

    def port(self, name, shape):
        """Declare a hierarchical port. Call before placing parts that use it."""
        self.ports[name] = shape

    def place(self, lib_id, ref, value, at, nets, rot=0, unit=1, footprint="",
              dnp=False, fields=None, field_gap=None):
        """nets maps pin number or unique pin name to a net name, or None for no-connect.

        field_gap overrides how far the Reference/Value text sits from the part's
        origin (default STUB, i.e. the behaviour before this parameter existed - every
        existing caller that omits it is unaffected). Needed for a part whose own pins
        land exactly STUB away from its origin on both sides (e.g. an IC with an even
        number of rows per side and no centre pin): the default offset then lands the
        Reference/Value text squarely on the part's own nearest pin row instead of clear
        of it - confirmed on U2 (MCP23017x-x-SO), whose GPA7/INTB pins sit at local y
        =+2.54 and GPB0/RESET at y=-2.54, exactly matching the default offset, rendering
        "U2GPA7" and "MCP23017GPB0" as overlapping glyphs. Pass a value larger than the
        part's own furthest pin so both fields clear the whole symbol instead of landing
        on one row. See test_kisch.py FieldGapTest.

        The same value also sets how far a POWER net's own flag symbol (GND/+3V3/+5V/
        +24V, auto-added for any of this part's pins wired to one) keeps its Value text
        from its own arrow graphic - default STUB is occasionally too tight there too:
        confirmed on J4 in the real motion-carrier design (+3V3 on pins 1/3/5, pins
        pointing left) and reproduced on J2/J4/J5 here, where a +3V3 or +5V flag's own
        "+3V3"/"+5V" text overlaps its own arrow's tip at some rotations (GND's flag
        clears fine at the same offset; +3V3/+5V's does not - a rendering quirk of the
        stock symbols' geometry, not something derivable, only found by rendering). See
        test_kisch.py FieldGapTest.test_field_gap_clears_a_power_flags_own_arrow."""
        if ref.endswith("?") and unit != 1:
            raise ValueError("%s: multi-unit parts need a fixed reference" % lib_id)
        pins = self.lib.pins(lib_id, unit)
        by_name = collections.defaultdict(list)
        for p in pins.values():
            by_name[p.name].append(p)
        resolved = collections.OrderedDict()
        for key, net in nets.items():
            key = str(key)
            if key in pins:
                pin = pins[key]
            elif len(by_name.get(key, [])) == 1:
                pin = by_name[key][0]
            else:
                raise ValueError("%s %s unit %d: no unique pin %r; pins are %s" % (
                    ref, lib_id, unit, key,
                    ", ".join("%s=%s" % (p.number, p.name) for p in pins.values())))
            if pin.number in resolved:
                raise ValueError("%s: pin %s assigned twice" % (ref, pin.number))
            resolved[pin.number] = net
        missing = [n for n in pins if n not in resolved]
        if missing:
            raise ValueError("%s %s unit %d: unassigned pins %s (use None for no-connect)"
                             % (ref, lib_id, unit, ", ".join(missing)))
        fg = STUB if field_gap is None else field_gap
        at = (_snap(at[0]), _snap(at[1]))
        self._add_part(lib_id, ref, value, at, rot, unit, footprint, dnp, fields or {},
                       list(pins), power=False, field_gap=fg)
        for number, net in resolved.items():
            pin = pins[number]
            point = pin_point(at, rot, pin)
            if net is None:
                self.items.append([A("no_connect"), [A("at"), point[0], point[1]],
                                   [A("uuid"), self._next()]])
                continue
            d = pin_outward(rot, pin)
            # A global label's shape (the hex/chevron body plus its Intersheetrefs
            # text) is taller than a plain label's - measured by rendering an actual
            # dense connector through kicad-cli: about 3.4mm total for a 1.27mm font,
            # against the 2.54mm row pitch box_symbol() (and any similar multi-row
            # part) uses between pins. At the default STUB, a global net one row away
            # from a plain-labelled neighbour lands squarely on that neighbour's own
            # label text (confirmed on the system project's PSU_24_36V and CONTACTOR
            # boxes - system.py, mains sheet). Giving a global net the same longer
            # stub as a power net moves it far enough out that it's no longer aligned
            # in x with a same-side neighbour using the default stub, the same fix
            # POWER_STUB already relies on for power-vs-plain rows. Only Sheet(globals
            # =...) opts a sheet into this at all (self.globals defaults to empty), so
            # it changes nothing for a sheet that never declares any - confirmed by
            # motion-carrier and panel-carrier regenerating byte-identical.
            stub = POWER_STUB if (net in POWER_NETS or net in self.globals) else STUB
            end = (round(point[0] + d[0] * stub, 4), round(point[1] + d[1] * stub, 4))
            self.wire(point, end)
            self.label(net, end, d, field_gap=fg)
            self._count(net)

    def _add_part(self, lib_id, ref, value, at, rot, unit, footprint, dnp, fields, pins, power,
                 text_dir=None, field_gap=STUB):
        """text_dir, when given, is the outward pin direction the part was hung off of -
        used only to keep a power symbol's Value field growing away from its pin instead
        of back toward whatever else shares its row. field_gap is how far Reference/Value
        sit from the part's origin - see place()."""
        self.parts.append(dict(lib_id=lib_id, ref=ref, value=value, at=at, rot=rot, unit=unit,
                               footprint=footprint, dnp=dnp, fields=fields, pins=pins,
                               power=power, text_dir=text_dir, field_gap=field_gap,
                               uuid=self._next("part")))

    def wire(self, a, b):
        self.items.append([A("wire"), [A("pts"), [A("xy"), a[0], a[1]], [A("xy"), b[0], b[1]]],
                           [A("stroke"), [A("width"), 0], [A("type"), A("default")]],
                           [A("uuid"), self._next()]])

    def label(self, net, point, direction, field_gap=STUB):
        angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[direction]
        side = "left" if angle in (0, 90) else "right"
        at = [A("at"), point[0], point[1], angle]
        if net in POWER_NETS:
            lib_id = POWER_NETS[net]
            base = (0, 1) if lib_id in POWER_POINTS_DOWN else (0, -1)
            # Keep aligning the symbol's graphic to point into the wire. Forcing rotation
            # 0 regardless of wire direction was tried, to keep the Value field's angle
            # horizontal - but the graphic then always points the same way regardless of
            # wire direction, which for a horizontal connector pin walks the graphic
            # itself (not just its text) into whichever neighbouring row is "below" in
            # its unrotated orientation - confirmed on J1, where a GND forced to rotation
            # 0 landed its arrow across the next pin's own label. text_dir (passed to
            # _add_part below) is what _symbol() needs to keep the Value field legible at
            # whatever rotation alignment actually produces, so alignment doesn't need to
            # be sacrificed for it.
            self._add_part(lib_id, "#PWR?", net, point, _rotation(base, direction), 1, "",
                           False, {}, ["1"], power=True, text_dir=direction,
                           field_gap=field_gap)
        elif net in self.ports:
            self.items.append([A("hierarchical_label"), net, [A("shape"), A(self.ports[net])],
                               at, _font(justify=[side]), [A("uuid"), self._next()]])
        elif net in self.globals:
            self.items.append([A("global_label"), net, [A("shape"), A("bidirectional")],
                               at, _font(justify=[side]), [A("uuid"), self._next()],
                               [A("property"), "Intersheetrefs", "${INTERSHEET_REFS}",
                                [A("at"), point[0], point[1], 0], _font(hide=True)]])
        else:
            self.items.append([A("label"), net, at, _font(justify=[side, "bottom"]),
                               [A("uuid"), self._next()]])

    def flag(self, net, at):
        """PWR_FLAG on a net whose source is a passive pin (connector, module)."""
        at = (_snap(at[0]), _snap(at[1]))
        self._add_part("power:PWR_FLAG", "#FLG?", "PWR_FLAG", at, 0, 1, "", False, {},
                       ["1"], power=True)
        end = (at[0], round(at[1] + STUB, 4))
        self.wire(at, end)
        self.label(net, end, (0, 1))
        self._count(net)

    def note(self, text, at, size=1.8):
        self.items.append([A("text"), text, [A("exclude_from_sim"), False],
                           [A("at"), _snap(at[0]), _snap(at[1]), 0],
                           _font(size=size, justify=["left", "top"]), [A("uuid"), self._next()]])

    def add_child(self, child, name, at, ports):
        """ports maps each of child's port names to a net on this sheet."""
        if set(child.ports) != set(ports):
            raise ValueError("sheet %s: ports %s do not match %s"
                             % (name, sorted(ports), sorted(child.ports)))
        at = (_snap(at[0]), _snap(at[1]))
        size = (30.48, max(10.16, round(STUB * (len(ports) + 1), 4)))
        pins = []
        for i, (pname, net) in enumerate(ports.items()):
            p = (at[0], round(at[1] + STUB * (i + 1), 4))
            pins.append([A("pin"), pname, A(child.ports[pname]), [A("at"), p[0], p[1], 180],
                         _font(justify=["left"]), [A("uuid"), self._next()]])
            end = (round(p[0] - STUB, 4), p[1])
            self.wire(p, end)
            self.label(net, end, (-1, 0))
            self._count(net)
        self.children.append(dict(sheet=child, name=name, at=at, size=size, pins=pins,
                                  uuid=self._next("child")))

    # -------------------------------------------------------------- output

    def _symbol(self, part, project, instances):
        x, y = part["at"]
        e = [A("symbol"), [A("lib_id"), part["lib_id"]], [A("at"), x, y, part["rot"]],
             [A("unit"), part["unit"]], [A("exclude_from_sim"), False],
             [A("in_bom"), not part["power"]], [A("on_board"), not part["power"]],
             [A("dnp"), part["dnp"]], [A("uuid"), part["uuid"]]]
        # A power symbol's Value field ("GND", "+5V", ...) sits at the end of its net's
        # wire stub. A regular part's Reference/Value uses a fixed (2.54, -2.54)/(2.54,
        # 2.54) diagonal offset from the part - fine for an isolated part, but on a
        # multi-row connector with a power net on every other pin (a GND return beside
        # each signal, say) that offset reliably lands the text on the neighbouring
        # row's own pin number or label: the y half of it alone is a full row pitch at
        # this design's 2.54mm grid. Three changes fix this together - each was checked
        # in isolation against an actual dense connector (J4: +3V3 on every odd pin
        # beside STEP/DIR/ENABLE) rendered through kicad-cli, and each one on its own
        # left a real overlap:
        #  - place() gives a power net a 3x-longer stub (POWER_STUB), so its symbol
        #    sits well clear of the connector body and every row's own pin-number text,
        #    which all sit close to the connector regardless of row. On its own this
        #    does not stop the Value field reaching a neighbouring row, because -
        #  - the Value field is offset *in the same direction the stub already runs*
        #    (part["text_dir"], set by label() to the net's outward pin direction),
        #    scaled by GRID * 2, instead of the regular fixed diagonal - so it moves
        #    further from the row it came from, not back into a neighbour's. A smaller
        #    offset (GRID) leaves the text still touching its own symbol's glyph; a
        #    larger one (3 * GRID) overshoots it on some rotations - both confirmed by
        #    rendering, not derived.
        #  - the justify is the *outward* side only ("left" or "right", from
        #    part["text_dir"] via _DIR_SIDE) with no vertical ("bottom") component.
        #    Adding "bottom" - the same justify a plain label() text uses, and safe
        #    there - reliably broke this: at some rotations a property with a "bottom"
        #    vertical justify renders at a completely different position than the same
        #    offset with no vertical justify, up to and including landing exactly on
        #    top of an unrelated neighbour. This looks like a KiCad quirk specific to a
        #    rotated symbol's property justify, not documented anywhere found; treat it
        #    as load-bearing and re-check by rendering before changing it.
        # See test_kisch.py PowerNetLegibilityTest, which renders an actual multi-row
        # power-and-signal connector (not just an isolated part) through kicad-cli and
        # asserts none of the resulting glyph boxes overlap.
        fg = part["field_gap"]
        if part["power"] and part["text_dir"] is not None:
            tdx, tdy = part["text_dir"]
            value_offset, value_justify = (tdx * fg, tdy * fg), [_DIR_SIDE[part["text_dir"]]]
        elif part["power"]:
            value_offset, value_justify = (1.27, 1.27), ["left"]
        else:
            value_offset, value_justify = (2.54, fg), ["left"]
        props = [("Reference", instances[0][1], part["power"], (2.54, -fg), ["left"]),
                 ("Value", part["value"], False, value_offset, value_justify),
                 ("Footprint", part["footprint"], True, (0, 0), ["left"]),
                 ("Datasheet", "", True, (0, 0), ["left"])]
        props += [(k, v, True, (0, 0), ["left"]) for k, v in part["fields"].items()]
        # KiCad renders a symbol property's stored angle combined with the parent
        # symbol's own rotation, but not by simple addition - determined empirically
        # (see hardware/tools/tests/test_kisch.py FieldRotationTest): a stored angle of
        # 0 renders upright whenever the part's own rotation is a multiple of 180, and
        # a stored angle of 90 renders upright whenever it is an odd multiple of 90.
        # Getting this wrong is how field text (references, values - e.g. a power-flag
        # "GND"/"+5V") ends up sideways or upside down, which is how two power nets a
        # few pins apart on a rotated connector row end up as overlapping garbled text.
        field_angle = 0 if part["rot"] % 180 == 0 else 90
        for name, value, hidden, (dx, dy), justify in props:
            # A smaller font for a power symbol's Value only tightens how far it reaches
            # - it doesn't change position, so it stacks with the offset above instead
            # of replacing it.
            size = 1.0 if (part["power"] and name == "Value") else 1.27
            e.append([A("property"), name, value, [A("at"), x + dx, y + dy, field_angle],
                      _font(size=size, hide=hidden, justify=justify)])
        for number in part["pins"]:
            e.append([A("pin"), number, [A("uuid"), _uid(part["uuid"] + "/" + number)]])
        e.append([A("instances"), [A("project"), project] + [
            [A("path"), path, [A("reference"), ref], [A("unit"), part["unit"]]]
            for path, ref in instances]])
        return e

    def _block(self, child, project, instances):
        (x, y), (w, h) = child["at"], child["size"]
        return ([A("sheet"), [A("at"), x, y], [A("size"), w, h],
                 [A("exclude_from_sim"), False], [A("in_bom"), True], [A("on_board"), True],
                 [A("dnp"), False], [A("fields_autoplaced"), True],
                 [A("stroke"), [A("width"), 0.1524], [A("type"), A("solid")]],
                 [A("fill"), [A("color"), 0, 0, 0, 0.0]],
                 [A("uuid"), child["uuid"]],
                 [A("property"), "Sheetname", child["name"], [A("at"), x, round(y - 0.7, 4), 0],
                  _font(justify=["left", "bottom"])],
                 [A("property"), "Sheetfile", child["sheet"].filename,
                  [A("at"), x, round(y + h + 0.6, 4), 0], _font(justify=["left", "top"])]]
                + child["pins"]
                + [[A("instances"), [A("project"), project] + [
                    [A("path"), path, [A("page"), str(page)]] for path, page in instances]]])

    def to_sexpr(self, project, paths, refs, page_of, is_root):
        tree = [A("kicad_sch"), [A("version"), A(FORMAT_VERSION)], [A("generator"), "eeschema"],
                [A("generator_version"), "9.0"], [A("uuid"), self.uuid], [A("paper"), self.paper],
                [A("title_block"), [A("title"), self.title], [A("date"), DATE],
                 [A("rev"), "H"], [A("company"), "routerLift"]]]
        lib_ids = sorted({p["lib_id"] for p in self.parts})
        tree.append([A("lib_symbols")] + [self.lib.get(i) for i in lib_ids])
        tree.extend(self.items)
        for part in self.parts:
            tree.append(self._symbol(part, project,
                                     [(p, refs[(p, part["uuid"])]) for p in paths]))
        for child in self.children:
            tree.append(self._block(child, project,
                                    [(p, page_of[p + "/" + child["uuid"]]) for p in paths]))
        if is_root:
            tree.append([A("sheet_instances"), [A("path"), "/", [A("page"), "1"]]])
        tree.append([A("embedded_fonts"), False])
        return tree


class Project:
    def __init__(self, name, root, outdir):
        if root.name != name:
            raise ValueError("root sheet must be named after the project")
        self.name, self.root, self.outdir = name, root, Path(outdir)

    def instances(self):
        """[(sheet, path, page)], depth first, root first."""
        out = []

        def visit(sheet, path):
            out.append((sheet, path, len(out) + 1))
            for child in sheet.children:
                visit(child["sheet"], path + "/" + child["uuid"])

        visit(self.root, "/" + self.root.uuid)
        return out

    def sheets(self):
        seen = []
        for sheet, _, _ in self.instances():
            if sheet not in seen:
                seen.append(sheet)
        return seen

    def validate(self):
        totals = collections.OrderedDict()
        for sheet in self.sheets():
            for net, count in sheet.net_pins.items():
                if net in POWER_NETS:
                    continue
                if net in sheet.globals:
                    totals[net] = totals.get(net, 0) + count
                elif count + (1 if net in sheet.ports else 0) < 2:
                    raise ValueError("sheet %s: net %s has only one connection"
                                     % (sheet.name, net))
        for net, count in totals.items():
            if count < 2:
                raise ValueError("global net %s has only one connection" % net)

    def annotate(self):
        insts = self.instances()
        fixed, used = set(), collections.defaultdict(set)
        for sheet, _, _ in insts:
            for part in sheet.parts:
                if part["ref"].endswith("?"):
                    continue
                key = (part["ref"], part["unit"])
                if key in fixed:
                    raise ValueError("duplicate reference %s unit %d" % key)
                fixed.add(key)
                m = re.match(r"(#?[A-Za-z_]+)(\d+)$", part["ref"])
                if m:
                    used[m.group(1)].add(int(m.group(2)))
        refs, counters = {}, collections.defaultdict(int)
        for sheet, path, _ in insts:
            for part in sheet.parts:
                ref = part["ref"]
                if ref.endswith("?"):
                    prefix = ref[:-1]
                    n = counters[prefix] + 1
                    while n in used[prefix]:
                        n += 1
                    counters[prefix] = n
                    ref = "%s%d" % (prefix, n)
                refs[(path, part["uuid"])] = ref
        return refs

    def write(self):
        self.validate()
        refs = self.annotate()
        insts = self.instances()
        page_of = {path: page for _, path, page in insts}
        self.outdir.mkdir(parents=True, exist_ok=True)
        for sheet in self.sheets():
            paths = [path for s, path, _ in insts if s is sheet]
            tree = sheet.to_sexpr(self.name, paths, refs, page_of, sheet is self.root)
            (self.outdir / sheet.filename).write_text(dump(tree) + "\n", encoding="utf-8")
        pro = {"meta": {"filename": self.name + ".kicad_pro", "version": 1}}
        (self.outdir / (self.name + ".kicad_pro")).write_text(json.dumps(pro, indent=2) + "\n")
