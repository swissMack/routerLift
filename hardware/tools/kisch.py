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
POWER_NETS = {"+3V3": "power:+3V3", "+5V": "power:+5V", "+24V": "power:+24V", "GND": "power:GND"}
POWER_POINTS_DOWN = {"power:GND"}
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
              dnp=False, fields=None):
        """nets maps pin number or unique pin name to a net name, or None for no-connect."""
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
        at = (_snap(at[0]), _snap(at[1]))
        self._add_part(lib_id, ref, value, at, rot, unit, footprint, dnp, fields or {},
                       list(pins), power=False)
        for number, net in resolved.items():
            pin = pins[number]
            point = pin_point(at, rot, pin)
            if net is None:
                self.items.append([A("no_connect"), [A("at"), point[0], point[1]],
                                   [A("uuid"), self._next()]])
                continue
            d = pin_outward(rot, pin)
            end = (round(point[0] + d[0] * STUB, 4), round(point[1] + d[1] * STUB, 4))
            self.wire(point, end)
            self.label(net, end, d)
            self._count(net)

    def _add_part(self, lib_id, ref, value, at, rot, unit, footprint, dnp, fields, pins, power):
        self.parts.append(dict(lib_id=lib_id, ref=ref, value=value, at=at, rot=rot, unit=unit,
                               footprint=footprint, dnp=dnp, fields=fields, pins=pins,
                               power=power, uuid=self._next("part")))

    def wire(self, a, b):
        self.items.append([A("wire"), [A("pts"), [A("xy"), a[0], a[1]], [A("xy"), b[0], b[1]]],
                           [A("stroke"), [A("width"), 0], [A("type"), A("default")]],
                           [A("uuid"), self._next()]])

    def label(self, net, point, direction):
        angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[direction]
        side = "left" if angle in (0, 90) else "right"
        at = [A("at"), point[0], point[1], angle]
        if net in POWER_NETS:
            lib_id = POWER_NETS[net]
            base = (0, 1) if lib_id in POWER_POINTS_DOWN else (0, -1)
            self._add_part(lib_id, "#PWR?", net, point, _rotation(base, direction), 1, "",
                           False, {}, ["1"], power=True)
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
        props = [("Reference", instances[0][1], part["power"], (2.54, -2.54)),
                 ("Value", part["value"], False, (2.54, 2.54)),
                 ("Footprint", part["footprint"], True, (0, 0)),
                 ("Datasheet", "", True, (0, 0))]
        props += [(k, v, True, (0, 0)) for k, v in part["fields"].items()]
        for name, value, hidden, (dx, dy) in props:
            e.append([A("property"), name, value, [A("at"), x + dx, y + dy, 0],
                      _font(hide=hidden, justify=["left"])])
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
