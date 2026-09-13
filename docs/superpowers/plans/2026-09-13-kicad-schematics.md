# KiCad Schematics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate three KiCad projects (motion carrier, panel carrier, system reference) from Python, ERC-clean and pin-checked against the firmware.

**Architecture:** A small library `hardware/tools/kisch.py` writes `.kicad_sch` files. Parts connect by net name: every pin gets a 2.54 mm wire stub ending in a label, power symbol, or no-connect flag — no wire routing. One builder module per project declares parts and nets. `check_pins.py` exports the netlist with `kicad-cli` and compares it with `firmware/config.yaml` and `hmi/include/pins.h`.

**Tech Stack:** Python 3.9 stdlib only (the Mac's `python3` is 3.9.6 — no `match`, no `X | Y` types), `unittest`, KiCad 10 `kicad-cli`, KiCad stock symbol libraries.

**Spec:** `docs/superpowers/specs/2026-09-13-kicad-schematics-design.md`

## Global Constraints

- Sources of truth: motion GPIOs `firmware/config.yaml`; panel GPIOs and MCP23017 bits `hmi/include/pins.h`; circuits and values `docs/WIRING-RevH.md`, `docs/BOM.md`.
- Undecided BOM facts are labelled **UNVERIFIED** on the drawing, never guessed.
- Conditioning topology: `+3V3 — 4.7 kΩ — wire node — 10 kΩ — GPIO node (BAT54S + 100 nF) — GPIO`.
- The motion 3.3 V and panel 3.3 V are never joined; the link carries GND, TX, RX only.
- 74LVC14 on the panel 3.3 V, two stages per channel, non-inverting. Never 74HCT14.
- Generated files are not hand-edited; change the generator and regenerate.
- `KICAD_CLI` default: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. Symbol dir default: `/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols`.
- Conventional Commits; one commit per task; end each commit message with the session attribution lines.

## File Structure

| File | Responsibility |
| --- | --- |
| `hardware/tools/kisch.py` | S-expression I/O, symbol library reader, `Sheet`, `Project`, `box_symbol` |
| `hardware/tools/parts.py` | Footprint strings and symbol ids shared by builders |
| `hardware/tools/devkit.py` | 30-pin ESP32 devkit header rows (physical silkscreen fact) |
| `hardware/tools/motion_carrier.py` | Builds `hardware/motion-carrier/` |
| `hardware/tools/panel_carrier.py` | Builds `hardware/panel-carrier/` |
| `hardware/tools/system.py` | Builds `hardware/system/` + its `routerlift.kicad_sym` |
| `hardware/tools/gen_schematics.py` | CLI entry: builds all or named projects |
| `hardware/tools/list_pins.py` | Prints a stock symbol's pins (used to verify pin numbers) |
| `hardware/tools/check_pins.py` | Netlist vs firmware cross-check |
| `hardware/tools/verify.sh` | Generate → ERC → PDF → check_pins |
| `hardware/tools/tests/` | `unittest` tests + `fixtures/Test.kicad_sym` |
| `hardware/README.md` | How to regenerate, what each project is |

---

### Task 0: Prerequisite — KiCad installed

- [ ] **Step 1:** Confirm `ls /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` succeeds. If not, stop and ask the user to run `! brew install --cask kicad` (needs sudo; cannot be run by the agent).
- [ ] **Step 2:** Run `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli version` and note it (expected 10.0.x).

---

### Task 1: `kisch` core library

**Files:**
- Create: `hardware/tools/kisch.py`
- Create: `hardware/tools/tests/fixtures/Test.kicad_sym`
- Test: `hardware/tools/tests/test_kisch.py`

**Interfaces:**
- Produces:
  - `Atom(str)`, `parse(text) -> list`, `dump(expr) -> str`, `find(expr, key)`, `findall(expr, key)`
  - `Library(symbol_dir=KICAD_SYMBOL_DIR, extra=None)`; `.get(lib_id) -> list`; `.pins(lib_id, unit=1) -> Dict[str, Pin]`
  - `Pin` namedtuple `(number, name, etype, x, y, angle)`
  - `pin_point(at, rot, pin) -> (x, y)`, `pin_outward(rot, pin) -> (dx, dy)`
  - `Sheet(name, title, lib, paper="A3", globals=())`: `.port(name, shape)`, `.place(lib_id, ref, value, at, nets, rot=0, unit=1, footprint="", dnp=False, fields=None)`, `.flag(net, at)`, `.note(text, at, size=1.8)`, `.add_child(child, name, at, ports)`
  - `Project(name, root, outdir)`: `.validate()`, `.annotate() -> dict`, `.write()`
  - `box_symbol(name, left, right, lib="routerlift") -> list`, `write_symbol_library(path, symbols)`
  - `POWER_NETS = {"+3V3", "+5V", "+24V", "GND"}` mapping to `power:` symbols

- [ ] **Step 1: Write the test fixture library**

`hardware/tools/tests/fixtures/Test.kicad_sym`:

```
(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")
  (symbol "R2" (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
    (property "Value" "R2" (at 0 0 90) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "R2_0_1"
      (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
    (symbol "R2_1_1"
      (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
      (pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
  (symbol "RX" (extends "R2")
    (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
    (property "Value" "RX" (at 0 0 90) (effects (font (size 1.27 1.27))))
    (property "Description" "derived" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))))
  (symbol "G2" (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
    (property "Value" "G2" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
    (symbol "G2_1_1"
      (pin input line (at -5.08 0 0) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
      (pin output line (at 5.08 0 180) (length 2.54) (name "Y" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27))))))
    (symbol "G2_2_1"
      (pin power_in line (at 0 5.08 270) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
      (pin power_in line (at 0 -5.08 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27))))))))
```

- [ ] **Step 2: Write the failing tests**

`hardware/tools/tests/test_kisch.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest discover -s hardware/tools/tests -v`
Expected: `ModuleNotFoundError: No module named 'kisch'`

- [ ] **Step 4: Implement `hardware/tools/kisch.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s hardware/tools/tests -v`
Expected: all tests `ok`. Note `test_duplicate_fixed_reference_rejected` must fail on `duplicate`, not on a single-connection net (annotate does not validate).

- [ ] **Step 6: Ignore KiCad local files**

Append to `.gitignore`:

```
# KiCad local state and reports
hardware/**/*.kicad_prl
hardware/**/*-backups/
hardware/**/fp-info-cache
hardware/**/*-erc.rpt
hardware/**/_autosave-*
__pycache__/
```

- [ ] **Step 7: Commit**

```bash
git add hardware/tools/kisch.py hardware/tools/tests .gitignore
git commit -m "feat(hardware): add kisch, a KiCad schematic writer"
```

---

### Task 2: Motion carrier

**Files:**
- Create: `hardware/tools/parts.py`, `hardware/tools/devkit.py`, `hardware/tools/list_pins.py`, `hardware/tools/motion_carrier.py`, `hardware/tools/gen_schematics.py`
- Create (generated): `hardware/motion-carrier/{motion-carrier,conditioning}.kicad_sch`, `motion-carrier.kicad_pro`, `motion-carrier.pdf`
- Test: `hardware/tools/tests/test_devkit.py`

**Interfaces:**
- Consumes: `Library`, `Sheet`, `Project` from Task 1.
- Produces: `devkit.DEVKIT_LEFT`, `devkit.DEVKIT_RIGHT` (lists of 15 silkscreen names), `devkit.devkit_gpio(silk) -> Optional[int]`; `parts.term(n) -> (lib_id, footprint)`; `motion_carrier.build(lib, outdir)`; nets `STEP DIR ENABLE RELAY_IN HOME_IN TOP_IN PROBE_IN FOOT_IN DRV_ALM_IN STOP LINK_TX LINK_RX` on J1/J2.

- [ ] **Step 1: Verify stock symbols and pin numbers**

`hardware/tools/list_pins.py`:

```python
"""Print a stock symbol's pins: python3 list_pins.py Diode:BAT54S [unit]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kisch import Library

lib_id = sys.argv[1]
unit = int(sys.argv[2]) if len(sys.argv) > 2 else 1
for p in Library().pins(lib_id, unit).values():
    print("%4s  %-12s %-14s at (%g, %g) %g" % (p.number, p.name, p.etype, p.x, p.y, p.angle))
```

Run each and record the result:

```bash
cd hardware/tools
for id in Device:R Device:C Diode:BAT54S Connector_Generic:Conn_01x15 Connector_Generic:Conn_01x03 \
  Connector:Screw_Terminal_01x02 Connector:Screw_Terminal_01x03 Connector:Screw_Terminal_01x06 \
  power:+3V3 power:+5V power:GND power:PWR_FLAG; do echo "== $id"; python3 list_pins.py $id; done
```

Expected: every id resolves. For `Diode:BAT54S` the requirement is **pin 1 = anode of the lower diode, pin 2 = cathode of the upper diode, pin 3 = common (K1/A2)** — so pin 1 → GND, pin 2 → +3V3, pin 3 → GPIO node. If the printed names disagree with that (e.g. names show pin 3 as a plain anode or cathode), fix the `nets` dict in Step 4 to match the printed names before generating. If a symbol id is missing, list candidates with `grep -o '(symbol "[^"]*' <symdir>/<Lib>.kicad_sym | grep -i <part>` and use the match.

- [ ] **Step 2: Write failing devkit test**

`hardware/tools/tests/test_devkit.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devkit import DEVKIT_LEFT, DEVKIT_RIGHT, devkit_gpio


class DevkitTest(unittest.TestCase):
    def test_rows_are_fifteen_pins(self):
        self.assertEqual(len(DEVKIT_LEFT), 15)
        self.assertEqual(len(DEVKIT_RIGHT), 15)

    def test_gpio_from_silkscreen(self):
        self.assertEqual(devkit_gpio("D26"), 26)
        self.assertEqual(devkit_gpio("TX2_17"), 17)
        self.assertEqual(devkit_gpio("VP_36"), 36)
        self.assertIsNone(devkit_gpio("3V3"))
        self.assertIsNone(devkit_gpio("GND"))

    def test_every_firmware_gpio_is_on_a_header(self):
        gpios = {devkit_gpio(s) for s in DEVKIT_LEFT + DEVKIT_RIGHT}
        self.assertTrue({26, 27, 14, 4, 33, 25, 32, 13, 21, 17, 16, 35, 34} <= gpios)
```

Run: `python3 -m unittest discover -s hardware/tools/tests -v` → Expected: `No module named 'devkit'`.

- [ ] **Step 3: Implement `devkit.py` and `parts.py`**

`hardware/tools/devkit.py`:

```python
"""30-pin ESP32-WROOM-32 devkit (DOIT v1 layout), antenna up, USB down.

Physical fact read from the silkscreen - VERIFY against the board in hand
before ordering a PCB. Index 0 is header pin 1 (top).
"""
import re

DEVKIT_LEFT = ["EN", "VP_36", "VN_39", "D34", "D35", "D32", "D33", "D25",
               "D26", "D27", "D14", "D12", "GND", "D13", "VIN"]
DEVKIT_RIGHT = ["D23", "D22", "TX0_1", "RX0_3", "D21", "D19", "D18", "D5",
                "TX2_17", "RX2_16", "D4", "D2", "D15", "GND", "3V3"]


def devkit_gpio(silk):
    m = re.search(r"(?:^D|_)(\d+)$", silk)
    return int(m.group(1)) if m else None
```

`hardware/tools/parts.py`:

```python
"""Symbol ids and footprints shared by the builders."""

R = "Device:R"
C = "Device:C"
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOIC14 = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"
FP_SOIC28 = "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm"
FP_DEVKIT_ROW = "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical"
FP_LINK = "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical"
FP_MX125_4 = "Connector_Molex:Molex_PicoBlade_53047-0410_1x04_P1.25mm_Vertical"


def term(n):
    """(symbol, footprint) for an n-way 5.08 mm screw terminal."""
    return ("Connector:Screw_Terminal_01x%02d" % n,
            "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-%d-5.08_1x%02d_P5.08mm_Horizontal"
            % (n, n))
```

Run tests → Expected: `test_devkit` passes.

- [ ] **Step 4: Implement `motion_carrier.py`**

```python
"""Motion carrier: ESP32 devkit, five input conditioners, field terminals."""
from devkit import DEVKIT_LEFT, DEVKIT_RIGHT
from kisch import Project, Sheet
import parts

CHANNELS = ["HOME", "TOP", "PROBE", "FOOT", "DRV_ALM"]

# Silkscreen name -> net. Firmware pin numbers are checked by check_pins.py.
DEVKIT_NETS = {
    "D26": "STEP", "D27": "DIR", "D14": "ENABLE", "D4": "RELAY_IN",
    "D33": "HOME_IN", "D25": "TOP_IN", "D32": "PROBE_IN", "D13": "FOOT_IN",
    "D35": "DRV_ALM_IN", "D21": "STOP", "TX2_17": "LINK_TX", "RX2_16": "LINK_RX",
    "VIN": "+5V", "GND": "GND", "3V3": "+3V3",
}


def conditioning(lib):
    s = Sheet("conditioning", "Input conditioning channel (x5)", lib, paper="A4")
    s.port("FIELD", "bidirectional")
    s.port("GPIO", "output")
    s.place(parts.R, "R?", "4.7k", (50.8, 50.8), {"1": "+3V3", "2": "FIELD"}, footprint=parts.FP_R)
    s.place(parts.R, "R?", "10k", (88.9, 76.2), {"1": "FIELD", "2": "GPIO"}, rot=90,
            footprint=parts.FP_R)
    s.place("Diode:BAT54S", "D?", "BAT54S", (127.0, 76.2), {"1": "GND", "2": "+3V3", "3": "GPIO"},
            footprint=parts.FP_SOT23)
    s.place(parts.C, "C?", "100n", (165.1, 76.2), {"1": "GPIO", "2": "GND"}, footprint=parts.FP_C)
    s.note("Pull-up on the WIRE side of the 10k; clamp and 100n on the GPIO side.\n"
           "A pull-up on the GPIO side leaves a closed switch at ~2.2 V, which does not read LOW.\n"
           "10k x 100n = ~1 ms filter (ELE-04). BAT54S makes a mis-wired PNP sensor survivable.",
           (25.4, 101.6))
    return s


def build(lib, outdir):
    cond = conditioning(lib)
    root = Sheet("motion-carrier", "routerLift motion carrier - Rev H", lib, paper="A3")

    for ref, row, x in (("J1", DEVKIT_LEFT, 76.2), ("J2", DEVKIT_RIGHT, 139.7)):
        nets = {str(i + 1): DEVKIT_NETS.get(silk) for i, silk in enumerate(row)}
        root.place("Connector_Generic:Conn_01x15", ref, "ESP32 devkit %s row" %
                   ("left" if ref == "J1" else "right"), (x, 101.6), nets,
                   footprint=parts.FP_DEVKIT_ROW)
    root.note("J1 pins 1-15: " + " ".join(DEVKIT_LEFT) + "\nJ2 pins 1-15: " + " ".join(DEVKIT_RIGHT)
              + "\nDOIT 30-pin layout - VERIFY against the devkit silkscreen.\n"
              "GPIO 34 reserved (feedback), 35 = driver alarm, not configured yet.", (25.4, 25.4))

    for i, name in enumerate(CHANNELS):
        root.add_child(cond, name, (215.9, 50.8 + i * 22.86),
                       {"FIELD": name + "_FIELD", "GPIO": name + "_IN"})

    t2, t3, t6 = parts.term(2), parts.term(3), parts.term(6)
    root.place(t2[0], "J3", "5V IN from buck", (330.2, 38.1), {"1": "+5V", "2": "GND"},
               footprint=t2[1])
    root.place(t6[0], "J4", "TB6600 PUL+ PUL- DIR+ DIR- ENA+ ENA-", (330.2, 76.2),
               {"1": "+3V3", "2": "STEP", "3": "+3V3", "4": "DIR", "5": "+3V3", "6": "ENABLE"},
               footprint=t6[1])
    root.place(t3[0], "J5", "RELAY +5V GND IN", (330.2, 114.3),
               {"1": "+5V", "2": "GND", "3": "RELAY_IN"}, footprint=t3[1])
    root.place(t6[0], "J6", "HOME GND TOP GND DRV_ALM GND", (330.2, 152.4),
               {"1": "HOME_FIELD", "2": "GND", "3": "TOP_FIELD", "4": "GND",
                "5": "DRV_ALM_FIELD", "6": "GND"}, footprint=t6[1])
    root.place(t6[0], "J7", "PROBE GND FOOT GND STOP GND", (330.2, 203.2),
               {"1": "PROBE_FIELD", "2": "GND", "3": "FOOT_FIELD", "4": "GND",
                "5": "STOP", "6": "GND"}, footprint=t6[1])
    root.place("Connector_Generic:Conn_01x03", "J8", "LINK to panel: GND TX RX", (330.2, 247.65),
               {"1": "GND", "2": "LINK_TX", "3": "LINK_RX"}, footprint=parts.FP_LINK)

    root.flag("+5V", (38.1, 254.0))
    root.flag("GND", (50.8, 254.0))
    root.flag("+3V3", (63.5, 254.0))
    root.note("LINK carries GND, TX, RX only. NEVER join this 3V3 to the panel's 3.3 V.\n"
              "TB6600 common is +3.3 V (not 5 V). STOP goes direct to GPIO 21 (feed_hold_pin).\n"
              "Sensor shields: GND terminal at this end only.", (25.4, 215.9))
    Project("motion-carrier", root, outdir).write()
```

- [ ] **Step 5: Implement `gen_schematics.py`**

```python
"""Regenerate the KiCad projects: python3 hardware/tools/gen_schematics.py [project ...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kisch import Library
import motion_carrier

HW = Path(__file__).resolve().parents[1]
BUILDERS = {"motion-carrier": motion_carrier.build}


def main(argv):
    targets = argv[1:] or list(BUILDERS)
    for name in targets:
        BUILDERS[name](Library(), HW / name)
        print("wrote", HW / name)


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 6: Generate and run ERC**

```bash
python3 hardware/tools/gen_schematics.py motion-carrier
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch erc -o hardware/motion-carrier/motion-carrier-erc.rpt hardware/motion-carrier/motion-carrier.kicad_sch
cat hardware/motion-carrier/motion-carrier-erc.rpt | tail -20
```

Expected: `** ERC messages: N  Errors 0  Warnings W`. If kicad-cli refuses to load the file, read its message — the usual cause is a malformed token; fix in `kisch.py`, add a regression test, rerun. Resolve every **error**. Warnings: fix `pin_not_connected`, `label_dangling`, `power_pin_not_driven`; lib-symbol-mismatch warnings from the embedded copy may be accepted and are noted in the commit message.

- [ ] **Step 7: Export PDF and review**

```bash
$K sch export pdf -o hardware/motion-carrier/motion-carrier.pdf hardware/motion-carrier/motion-carrier.kicad_sch
```

Open the PDF with the Read tool (pages 1–2). Check: no labels overlapping other labels or symbols, all five channel blocks present, notes legible. Adjust coordinates in `motion_carrier.py`, regenerate, re-run ERC.

- [ ] **Step 8: Commit**

```bash
git add hardware/tools hardware/motion-carrier
git commit -m "feat(hardware): generate the motion carrier schematic"
```

---

### Task 3: Panel carrier

**Files:**
- Create: `hardware/tools/panel_carrier.py`
- Modify: `hardware/tools/gen_schematics.py` (register builder)
- Create (generated): `hardware/panel-carrier/panel-carrier.kicad_sch`, `.kicad_pro`, `.pdf`

**Interfaces:**
- Consumes: `Sheet`, `Project`, `parts`.
- Produces: `panel_carrier.build(lib, outdir)`; J1 (P3) pins 1–4 = `MPG_A_3V3 MPG_B_3V3 SDA SCL`; J2 (P4) pins 1–4 = `GND +3V3 LINK_TX LINK_RX`; U2 GPA0–6 = `BTN_CYCLE_START BTN_ROUTER BTN_BIT_CHANGE BTN_ZERO BTN_PRESET SW_ROUGH_FINE FOOT_MIRROR`, GPB0 = `LED_ROUTER_DRV`.

- [ ] **Step 1: Verify symbols**

```bash
cd hardware/tools
for u in 1 2 3 4 5 6 7; do echo "== 74LVC14 unit $u"; python3 list_pins.py 74xx:74LVC14 $u; done
python3 list_pins.py Interface_Expansion:MCP23017_SO
python3 list_pins.py Connector_Generic:Conn_01x04
python3 list_pins.py Connector:Screw_Terminal_01x08
```

Expected for 74LVC14: units 1–6 = (in, out) (1,2) (3,4) (5,6) (9,8) (11,10) (13,12); unit 7 = 14 VCC, 7 GND. If `74xx:74LVC14` is missing use `74xx:74HC14` with Value `74LVC14`. If the power unit is not 7, change `POWER_UNIT`. For MCP23017 note the exact names of the reset pin (expected `~{RESET}`) and the address/interrupt pins; if `MCP23017_SO` is missing, try `Interface_Expansion:MCP23017_S`. Update the `mcp` dict keys in Step 2 to the printed names.

- [ ] **Step 2: Implement `panel_carrier.py`**

```python
"""Panel carrier: MPG level shifter, MCP23017 button expander, leads to the display."""
from kisch import Project, Sheet
import parts

HDR4 = "Connector_Generic:Conn_01x04"
LVC14 = "74xx:74LVC14"
POWER_UNIT = 7
GATE_PINS = {1: ("1", "2"), 2: ("3", "4"), 3: ("5", "6"), 4: ("9", "8"), 5: ("11", "10"), 6: ("13", "12")}
GATES = {1: ("MPG_A_5V", "MPG_A_N"), 2: ("MPG_A_N", "MPG_A_3V3"),
         3: ("MPG_B_5V", "MPG_B_N"), 4: ("MPG_B_N", "MPG_B_3V3"),
         5: ("GND", None), 6: ("GND", None)}
BUTTONS = ["BTN_CYCLE_START", "BTN_ROUTER", "BTN_BIT_CHANGE", "BTN_ZERO", "BTN_PRESET",
           "SW_ROUGH_FINE", "FOOT_MIRROR"]


def build(lib, outdir):
    s = Sheet("panel-carrier", "routerLift panel carrier - Rev H", lib, paper="A3")
    s.place(HDR4, "J1", "display P3: IO6 IO7 IO15 IO16", (38.1, 50.8),
            {"1": "MPG_A_3V3", "2": "MPG_B_3V3", "3": "SDA", "4": "SCL"}, footprint=parts.FP_MX125_4)
    s.place(HDR4, "J2", "display P4: GND 3.3V IO17 IO18", (38.1, 88.9),
            {"1": "GND", "2": "+3V3", "3": "LINK_TX", "4": "LINK_RX"}, footprint=parts.FP_MX125_4)
    t2, t3, t4, t8 = parts.term(2), parts.term(3), parts.term(4), parts.term(8)
    s.place(t3[0], "J3", "LINK to motion: GND TX RX", (38.1, 127.0),
            {"1": "GND", "2": "LINK_TX", "3": "LINK_RX"}, footprint=t3[1])
    s.place(t4[0], "J4", "MPG +5V GND A B", (38.1, 165.1),
            {"1": "+5V", "2": "GND", "3": "MPG_A_5V", "4": "MPG_B_5V"}, footprint=t4[1])
    s.place(t2[0], "J5", "5V IN from buck", (38.1, 203.2), {"1": "+5V", "2": "GND"}, footprint=t2[1])

    for unit, (inp, out) in GATES.items():
        pin_in, pin_out = GATE_PINS[unit]
        s.place(LVC14, "U1", "74LVC14", (114.3, 38.1 + (unit - 1) * 20.32),
                {pin_in: inp, pin_out: out}, unit=unit, footprint=parts.FP_SOIC14)
    s.place(LVC14, "U1", "74LVC14", (114.3, 165.1), {"14": "+3V3", "7": "GND"},
            unit=POWER_UNIT, footprint=parts.FP_SOIC14)
    s.place(parts.C, "C1", "100n", (139.7, 165.1), {"1": "+3V3", "2": "GND"}, footprint=parts.FP_C)
    s.place(parts.R, "R3", "10k DNP", (165.1, 38.1), {"1": "+5V", "2": "MPG_A_5V"},
            footprint=parts.FP_R, dnp=True)
    s.place(parts.R, "R4", "10k DNP", (177.8, 38.1), {"1": "+5V", "2": "MPG_B_5V"},
            footprint=parts.FP_R, dnp=True)

    mcp = {"SCL": "SCL", "SDA": "SDA", "A0": "GND", "A1": "GND", "A2": "GND",
           "~{RESET}": "+3V3", "INTA": None, "INTB": None, "VSS": "GND", "VDD": "+3V3",
           "GPA7": None, "GPB0": "LED_ROUTER_DRV"}
    mcp.update({"GPA%d" % i: net for i, net in enumerate(BUTTONS)})
    mcp.update({"GPB%d" % i: None for i in range(1, 8)})
    s.place("Interface_Expansion:MCP23017_SO", "U2", "MCP23017 @0x20", (254.0, 101.6), mcp,
            footprint=parts.FP_SOIC28)
    s.place(parts.C, "C2", "100n", (292.1, 50.8), {"1": "+3V3", "2": "GND"}, footprint=parts.FP_C)
    s.place(parts.R, "R1", "4.7k", (203.2, 50.8), {"1": "+3V3", "2": "SDA"}, footprint=parts.FP_R)
    s.place(parts.R, "R2", "4.7k", (215.9, 50.8), {"1": "+3V3", "2": "SCL"}, footprint=parts.FP_R)
    s.place(parts.R, "R5", "330", (330.2, 76.2), {"1": "LED_ROUTER_DRV", "2": "LED_ROUTER_A"},
            footprint=parts.FP_R)
    nets = {str(i + 1): net for i, net in enumerate(BUTTONS)}
    nets["8"] = "GND"
    s.place(t8[0], "J6", "BUTTONS A0-A6, COM", (368.3, 127.0), nets, footprint=t8[1])
    s.place(t2[0], "J7", "ROUTER LED + -", (368.3, 76.2), {"1": "LED_ROUTER_A", "2": "GND"},
            footprint=t2[1])

    s.flag("+3V3", (38.1, 254.0))
    s.flag("+5V", (50.8, 254.0))
    s.flag("GND", (63.5, 254.0))
    s.note("74LVC14 powered from the PANEL 3.3 V - NOT 74HCT14 (5 V outputs would damage the S3).\n"
           "Two stages per channel = non-inverting, SIGNALS_INVERTED = false.\n"
           "R3/R4: fit 10k only if the MPG outputs are open-collector (UNVERIFIED).\n"
           "J2 3.3V feeds this board only - never connect it to the motion 3V3.\n"
           "FOOT_MIRROR (GPA6): foot-switch release mirror, plan UNVERIFIED.\n"
           "Check pin 1 on the P3/P4 leads before trusting wire colours.", (25.4, 222.25))
    Project("panel-carrier", s, outdir).write()
```

- [ ] **Step 3: Register the builder**

In `gen_schematics.py` add `import panel_carrier` and `"panel-carrier": panel_carrier.build` to `BUILDERS`.

- [ ] **Step 4: Generate, ERC, PDF, review**

```bash
python3 hardware/tools/gen_schematics.py panel-carrier
$K sch erc -o hardware/panel-carrier/panel-carrier-erc.rpt hardware/panel-carrier/panel-carrier.kicad_sch && tail -20 hardware/panel-carrier/panel-carrier-erc.rpt
$K sch export pdf -o hardware/panel-carrier/panel-carrier.pdf hardware/panel-carrier/panel-carrier.kicad_sch
```

Expected: Errors 0. Read the PDF; fix overlaps (the MCP23017 is ~35 mm tall — keep neighbours clear).

- [ ] **Step 5: Run all tests, commit**

```bash
python3 -m unittest discover -s hardware/tools/tests -v
git add hardware/tools hardware/panel-carrier
git commit -m "feat(hardware): generate the panel carrier schematic"
```

---

### Task 4: System reference project

**Files:**
- Create: `hardware/tools/system.py`
- Modify: `hardware/tools/gen_schematics.py`
- Create (generated): `hardware/system/{system,mains,low-voltage}.kicad_sch`, `system.kicad_pro`, `routerlift.kicad_sym`, `sym-lib-table`, `system.pdf`

**Interfaces:**
- Consumes: `box_symbol`, `write_symbol_library`, `Sheet(globals=...)`, `Project`.
- Produces: `system.build(lib, outdir)`; `system.BOXES`.

- [ ] **Step 1: Implement `system.py`**

```python
"""System reference drawing: mains and low-voltage wiring between modules. Not for layout."""
from kisch import Project, Sheet, box_symbol, write_symbol_library

BOXES = {
    "MAINS_INLET": ([], ["L", "N", "PE"]),
    "RCD": (["L_IN", "N_IN"], ["L_OUT", "N_OUT"]),
    "ESTOP_NC": (["L_IN"], ["L_OUT"]),
    "PSU_24_36V": (["L", "N", "PE"], ["V+", "V-"]),
    "CONTACTOR": (["A1", "A2", "L1", "L2"], ["T1", "T2"]),
    "KEY_SWITCH": (["IN"], ["OUT"]),
    "RC_SNUBBER": (["X1"], ["X2"]),
    "ROUTER_SOCKET": (["L", "N", "PE"], []),
    "PE_BOND": (["PE"], []),
    "BUCK_5V": (["VIN+", "VIN-"], ["5V", "GND"]),
    "TB6600": (["PUL+", "PUL-", "DIR+", "DIR-", "ENA+", "ENA-"], ["VCC", "GND", "A+", "A-", "B+", "B-"]),
    "STEPPER": (["A+", "A-", "B+", "B-"], []),
    "RELAY_MODULE": (["VCC", "GND", "IN"], ["COM", "NO"]),
    "MOTION_CARRIER": (["+5V", "GND", "LINK_GND", "LINK_TX", "LINK_RX"],
                       ["PUL+", "PUL-", "DIR+", "DIR-", "ENA+", "ENA-", "RELAY_5V", "RELAY_GND",
                        "RELAY_IN", "HOME", "TOP", "DRV_ALM", "PROBE", "FOOT", "STOP", "SIG_GND"]),
    "PANEL_CARRIER": (["LINK_GND", "LINK_TX", "LINK_RX", "+5V", "GND", "MPG_5V", "MPG_GND", "MPG_A", "MPG_B"],
                      ["P3", "P4", "CYCLE", "ROUTER", "BIT", "ZERO", "PRESET", "ROUGH_FINE",
                       "FOOT_MIRROR", "BTN_GND", "LED+", "LED-"]),
    "DISPLAY_JC4827W543C": (["P1_5V", "P1_GND", "P3", "P4"], []),
    "MPG_ZS80": (["5V", "GND", "A", "B"], []),
    "LIMIT_SWITCH_NC": (["C", "NC"], []),
    "PROBE_PLATE": (["PLATE", "CLIP"], []),
    "FOOT_PEDAL": (["C1", "NO1", "C2", "NO2"], []),
    "STOP_BUTTON": (["C", "NO"], []),
    "PANEL_BUTTONS": (["CYCLE", "ROUTER", "BIT", "ZERO", "PRESET", "ROUGH_FINE", "COM"], []),
    "ROUTER_LED": (["A", "K"], []),
}
GLOBALS = ("L_FUSED", "RELAY_NO")


def box(name):
    return "routerlift:" + name


def mains(lib):
    s = Sheet("mains", "Mains, E-stop and router power", lib, paper="A3", globals=GLOBALS)
    s.place(box("MAINS_INLET"), "M?", "Mains inlet", (50.8, 76.2),
            {"L": "L_SUPPLY", "N": "N_SUPPLY", "PE": "PE"})
    s.place(box("RCD"), "M?", "RCD", (114.3, 76.2),
            {"L_IN": "L_SUPPLY", "N_IN": "N_SUPPLY", "L_OUT": "L_RCD", "N_OUT": "N_RCD"})
    s.place(box("ESTOP_NC"), "M?", "E-stop mushroom NC", (177.8, 76.2),
            {"L_IN": "L_RCD", "L_OUT": "L_ESTOP"})
    s.place("Device:Fuse", "F1", "Fuse, PSU + router", (228.6, 76.2),
            {"1": "L_ESTOP", "2": "L_FUSED"}, rot=90)
    s.place(box("PSU_24_36V"), "M?", "PSU 24-36 V", (304.8, 76.2),
            {"L": "L_FUSED", "N": "N_RCD", "PE": "PE", "V+": "+24V", "V-": "GND"})
    s.place(box("KEY_SWITCH"), "M?", "Bit-change key switch", (114.3, 152.4),
            {"IN": "RELAY_NO", "OUT": "COIL_A1"})
    s.place(box("CONTACTOR"), "M?", "Router contactor", (177.8, 152.4),
            {"A1": "COIL_A1", "A2": "N_RCD", "L1": "L_FUSED", "L2": "N_RCD",
             "T1": "ROUTER_L", "T2": "ROUTER_N"})
    s.place(box("RC_SNUBBER"), "M?", "RC snubber", (177.8, 203.2),
            {"X1": "L_FUSED", "X2": "ROUTER_L"})
    s.place(box("ROUTER_SOCKET"), "M?", "Router socket", (304.8, 152.4),
            {"L": "ROUTER_L", "N": "ROUTER_N", "PE": "PE"})
    s.place(box("PE_BOND"), "M?", "PE: enclosure + lift frame", (304.8, 203.2), {"PE": "PE"})
    s.flag("+24V", (38.1, 254.0))
    s.flag("GND", (50.8, 254.0))
    s.note("E-stop breaks L to BOTH the PSU and the contactor (SAF-01).\n"
           "Key switch in series with the coil: key out = contactor cannot pull in (SAF-02).\n"
           "Contactor coil voltage UNVERIFIED - drawn as 230 V AC from L_FUSED / N (BOM block A).\n"
           "L_FUSED and RELAY_NO continue on the low-voltage sheet (relay module contact).",
           (25.4, 25.4))
    return s


def low_voltage(lib):
    s = Sheet("low-voltage", "Low voltage: supply, motion, sensors, panel", lib, paper="A2",
              globals=GLOBALS)
    s.place(box("BUCK_5V"), "M?", "Buck 5 V >=2 A", (63.5, 50.8),
            {"VIN+": "+24V", "VIN-": "GND", "5V": "+5V", "GND": "GND"})
    s.place(box("MOTION_CARRIER"), "M?", "Motion carrier", (177.8, 101.6),
            {"+5V": "+5V", "GND": "GND", "LINK_GND": "GND", "LINK_TX": "LINK_TX", "LINK_RX": "LINK_RX",
             "PUL+": "PUL_P", "PUL-": "PUL_N", "DIR+": "DIR_P", "DIR-": "DIR_N",
             "ENA+": "ENA_P", "ENA-": "ENA_N", "RELAY_5V": "+5V", "RELAY_GND": "GND",
             "RELAY_IN": "RELAY_IN", "HOME": "HOME_SIG", "TOP": "TOP_SIG", "DRV_ALM": None,
             "PROBE": "PROBE_SIG", "FOOT": "FOOT_SIG", "STOP": "STOP_SIG", "SIG_GND": "GND"})
    s.place(box("TB6600"), "M?", "TB6600 1/8 step", (292.1, 63.5),
            {"PUL+": "PUL_P", "PUL-": "PUL_N", "DIR+": "DIR_P", "DIR-": "DIR_N",
             "ENA+": "ENA_P", "ENA-": "ENA_N", "VCC": "+24V", "GND": "GND",
             "A+": "MOT_A_P", "A-": "MOT_A_N", "B+": "MOT_B_P", "B-": "MOT_B_N"})
    s.place(box("STEPPER"), "M?", "Stepper motor", (381.0, 63.5),
            {"A+": "MOT_A_P", "A-": "MOT_A_N", "B+": "MOT_B_P", "B-": "MOT_B_N"})
    s.place(box("RELAY_MODULE"), "M?", "5 V relay module", (292.1, 127.0),
            {"VCC": "+5V", "GND": "GND", "IN": "RELAY_IN", "COM": "L_FUSED", "NO": "RELAY_NO"})
    s.place(box("LIMIT_SWITCH_NC"), "M?", "HOME bottom limit NC", (292.1, 177.8),
            {"C": "GND", "NC": "HOME_SIG"})
    s.place(box("LIMIT_SWITCH_NC"), "M?", "TOP limit NC", (292.1, 203.2),
            {"C": "GND", "NC": "TOP_SIG"})
    s.place(box("PROBE_PLATE"), "M?", "Touch plate + clip on bit", (292.1, 228.6),
            {"PLATE": "PROBE_SIG", "CLIP": "GND"})
    s.place(box("FOOT_PEDAL"), "M?", "Foot pedal NO", (292.1, 254.0),
            {"C1": "GND", "NO1": "FOOT_SIG", "C2": "GND", "NO2": "FOOT_MIRROR"})
    s.place(box("STOP_BUTTON"), "M?", "STOP flush NO", (292.1, 284.48),
            {"C": "GND", "NO": "STOP_SIG"})
    s.place(box("PANEL_CARRIER"), "M?", "Panel carrier", (177.8, 330.2),
            {"LINK_GND": "GND", "LINK_TX": "LINK_TX", "LINK_RX": "LINK_RX", "+5V": "+5V",
             "GND": "GND", "MPG_5V": "+5V", "MPG_GND": "GND", "MPG_A": "MPG_A", "MPG_B": "MPG_B",
             "P3": "LEAD_P3", "P4": "LEAD_P4", "CYCLE": "BTN_CYCLE_START", "ROUTER": "BTN_ROUTER",
             "BIT": "BTN_BIT_CHANGE", "ZERO": "BTN_ZERO", "PRESET": "BTN_PRESET",
             "ROUGH_FINE": "SW_ROUGH_FINE", "FOOT_MIRROR": "FOOT_MIRROR", "BTN_GND": "GND",
             "LED+": "LED_A", "LED-": "GND"})
    s.place(box("DISPLAY_JC4827W543C"), "M?", "Guition JC4827W543C", (292.1, 330.2),
            {"P1_5V": "+5V", "P1_GND": "GND", "P3": "LEAD_P3", "P4": "LEAD_P4"})
    s.place(box("MPG_ZS80"), "M?", "MPG ZS80 100 PPR 5 V", (63.5, 330.2),
            {"5V": "+5V", "GND": "GND", "A": "MPG_A", "B": "MPG_B"})
    s.place(box("PANEL_BUTTONS"), "M?", "Panel buttons + rough/fine", (292.1, 381.0),
            {"CYCLE": "BTN_CYCLE_START", "ROUTER": "BTN_ROUTER", "BIT": "BTN_BIT_CHANGE",
             "ZERO": "BTN_ZERO", "PRESET": "BTN_PRESET", "ROUGH_FINE": "SW_ROUGH_FINE", "COM": "GND"})
    s.place(box("ROUTER_LED"), "M?", "ROUTER LED", (381.0, 330.2), {"A": "LED_A", "K": "GND"})
    s.flag("+5V", (38.1, 406.4))
    s.note("GND = one star point at the PSU (PWR-04).\n"
           "Motion 3V3 and panel 3.3 V are separate rails: the link carries GND, TX, RX only.\n"
           "DRV_ALM (GPIO 35) reserved for future closed-loop driver - no-connect today.\n"
           "FOOT_PEDAL drawn with a second contact for the HMI release mirror - UNVERIFIED.\n"
           "A single shared contact would tie the two 3.3 V rails together through the pull-ups.\n"
           "LEAD_P3 / LEAD_P4 are MX1.25 4-pin leads; carrier schematics give the pinout.",
           (25.4, 25.4))
    return s


def build(lib, outdir):
    for name, (left, right) in BOXES.items():
        lib.extra[box(name)] = box_symbol(name, left, right)
    root = Sheet("system", "routerLift system - Rev H", lib, paper="A4")
    root.add_child(mains(lib), "Mains", (50.8, 76.2), {})
    root.add_child(low_voltage(lib), "Low voltage", (127.0, 76.2), {})
    root.note("Reference drawing only - not for PCB layout.\n"
              "Carrier boards: hardware/motion-carrier, hardware/panel-carrier.", (25.4, 25.4))
    Project("system", root, outdir).write()
    write_symbol_library(outdir / "routerlift.kicad_sym", [lib.extra[box(n)] for n in BOXES])
    (outdir / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n  (lib (name "routerlift")(type "KiCad")'
        '(uri "${KIPRJMOD}/routerlift.kicad_sym")(options "")(descr "routerLift module blocks"))\n)\n')
```

- [ ] **Step 2: Register the builder** — `import system` and `"system": system.build` in `BUILDERS`.

- [ ] **Step 3: Generate, ERC, PDF, review**

```bash
python3 hardware/tools/gen_schematics.py system
$K sch erc -o hardware/system/system-erc.rpt hardware/system/system.kicad_sch && tail -20 hardware/system/system-erc.rpt
$K sch export pdf -o hardware/system/system.pdf hardware/system/system.kicad_sch
```

Expected: Errors 0 (warnings about module symbols may remain). Read all 3 PDF pages; the A2 low-voltage sheet is dense — spread boxes if labels collide.

- [ ] **Step 4: Run tests, commit**

```bash
python3 -m unittest discover -s hardware/tools/tests -v
git add hardware/tools hardware/system
git commit -m "feat(hardware): generate the system reference schematic"
```

---

### Task 5: Pin cross-check and verify script

**Files:**
- Create: `hardware/tools/check_pins.py`, `hardware/tools/verify.sh`
- Test: `hardware/tools/tests/test_check_pins.py`

**Interfaces:**
- Consumes: generated projects from Tasks 2–3; `devkit` tables; `kisch.parse/find/findall`.
- Produces: `config_pins(text) -> Dict[Tuple[str, str], int]`, `header_constants(text) -> Dict[str, int]`, `netlist(sch) -> Dict[Tuple[ref, pin], Tuple[net, pinfunction]]`, `main() -> int` exit code.

- [ ] **Step 1: Write failing tests**

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_pins import config_pins, header_constants

YAML = """name: routerLift
uart1:
  txd_pin: gpio.17      # comment
  rxd_pin: gpio.16
axes:
  z:
    motor0:
      limit_neg_pin: gpio.33:pu
      stepstick:
        step_pin: gpio.26
probe:
  pin: gpio.32:low:pu
Relay:
  output_pin: gpio.4
"""

HEADER = """namespace Pins {
constexpr int8_t UART_TX = 18;   // -> FluidNC
constexpr uint8_t MCP_ADDR = 0x20;
}
namespace Expander {
constexpr uint8_t A_ZERO        = 3;
}"""


class CheckPinsTest(unittest.TestCase):
    def test_config_pins_tracks_top_level_section(self):
        pins = config_pins(YAML)
        self.assertEqual(pins[("uart1", "txd_pin")], 17)
        self.assertEqual(pins[("axes", "limit_neg_pin")], 33)
        self.assertEqual(pins[("axes", "step_pin")], 26)
        self.assertEqual(pins[("probe", "pin")], 32)
        self.assertEqual(pins[("Relay", "output_pin")], 4)

    def test_header_constants_decimal_only(self):
        c = header_constants(HEADER)
        self.assertEqual(c["UART_TX"], 18)
        self.assertEqual(c["A_ZERO"], 3)
        self.assertNotIn("MCP_ADDR", c)
```

Run → Expected: `No module named 'check_pins'`.

- [ ] **Step 2: Implement `check_pins.py`**

```python
"""Cross-check the carrier schematics against the firmware pin maps.

python3 hardware/tools/check_pins.py   (exit 0 = consistent)
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devkit import DEVKIT_LEFT, DEVKIT_RIGHT, devkit_gpio
from kisch import find, findall, parse

KICAD_CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
HW = Path(__file__).resolve().parents[1]
REPO = HW.parent

MOTION_EXPECT = {
    ("uart1", "txd_pin"): "LINK_TX", ("uart1", "rxd_pin"): "LINK_RX",
    ("axes", "step_pin"): "STEP", ("axes", "direction_pin"): "DIR",
    ("axes", "disable_pin"): "ENABLE", ("axes", "limit_neg_pin"): "HOME_IN",
    ("axes", "limit_pos_pin"): "TOP_IN", ("probe", "pin"): "PROBE_IN",
    ("control", "feed_hold_pin"): "STOP", ("control", "macro0_pin"): "FOOT_IN",
    ("Relay", "output_pin"): "RELAY_IN",
}
RESERVED = {35: "DRV_ALM_IN"}
P3 = {"1": 6, "2": 7, "3": 15, "4": 16}
P4 = {"3": 17, "4": 18}
PANEL_EXPECT = {"MPG_A": "MPG_A_3V3", "MPG_B": "MPG_B_3V3", "MCP_SDA": "SDA", "MCP_SCL": "SCL",
                "UART_RX": "LINK_TX", "UART_TX": "LINK_RX"}
EXPANDER_EXPECT = {"A_CYCLE_START": "BTN_CYCLE_START", "A_ROUTER": "BTN_ROUTER",
                   "A_BIT_CHANGE": "BTN_BIT_CHANGE", "A_ZERO": "BTN_ZERO",
                   "A_PRESET": "BTN_PRESET", "A_ROUGH_FINE": "SW_ROUGH_FINE",
                   "A_FOOT_MIRROR": "FOOT_MIRROR", "B_ROUTER_LED": "LED_ROUTER_DRV"}


def config_pins(text):
    section, out = None, {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\w+):", line)
        if m:
            section = m.group(1)
        m = re.match(r"^\s*(\w+):\s*gpio\.(\d+)", line)
        if m:
            out[(section, m.group(1))] = int(m.group(2))
    return out


def header_constants(text):
    return {m.group(1): int(m.group(2)) for m in
            re.finditer(r"constexpr\s+\w+\s+(\w+)\s*=\s*(\d+)\s*;", text)}


def netlist(sch):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "net.net"
        subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
                        "-o", str(out), str(sch)], check=True, capture_output=True)
        tree = parse(out.read_text(encoding="utf-8"))
    nodes = {}
    for net in findall(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1]).split("/")[-1]
        for node in findall(net, "node"):
            func = find(node, "pinfunction")
            nodes[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = (
                name, str(func[1]) if func else "")
    return nodes


def check_motion(errors):
    nodes = netlist(HW / "motion-carrier" / "motion-carrier.kicad_sch")
    gpio_net = {}
    for ref, row in (("J1", DEVKIT_LEFT), ("J2", DEVKIT_RIGHT)):
        for i, silk in enumerate(row):
            gpio = devkit_gpio(silk)
            if gpio is not None:
                gpio_net[gpio] = nodes[(ref, str(i + 1))][0]
    cfg = config_pins((REPO / "firmware" / "config.yaml").read_text(encoding="utf-8"))
    for key, net in MOTION_EXPECT.items():
        if key not in cfg:
            errors.append("config.yaml: %s.%s not found" % key)
        elif gpio_net.get(cfg[key]) != net:
            errors.append("config.yaml %s.%s = gpio.%d but the schematic has %r there, expected %r"
                          % (key[0], key[1], cfg[key], gpio_net.get(cfg[key]), net))
    used = set(cfg.values())
    for gpio, net in sorted(gpio_net.items()):
        if net.startswith("unconnected") or gpio in used:
            continue
        if RESERVED.get(gpio) != net:
            errors.append("GPIO %d carries %s but config.yaml does not use it" % (gpio, net))


def check_panel(errors):
    nodes = netlist(HW / "panel-carrier" / "panel-carrier.kicad_sch")
    io_net = {io: nodes[("J1", pin)][0] for pin, io in P3.items()}
    io_net.update({io: nodes[("J2", pin)][0] for pin, io in P4.items()})
    consts = header_constants((REPO / "hmi" / "include" / "pins.h").read_text(encoding="utf-8"))
    for name, net in PANEL_EXPECT.items():
        if name not in consts:
            errors.append("pins.h: %s not found" % name)
        elif io_net.get(consts[name]) != net:
            errors.append("pins.h %s = %d but the schematic has %r there, expected %r"
                          % (name, consts[name], io_net.get(consts[name]), net))
    mcp = {func: net for (ref, _), (net, func) in nodes.items() if ref == "U2"}
    for name, net in EXPANDER_EXPECT.items():
        if name not in consts:
            errors.append("pins.h: %s not found" % name)
            continue
        func = ("GPA%d" if name.startswith("A_") else "GPB%d") % consts[name]
        if mcp.get(func) != net:
            errors.append("pins.h %s -> %s but U2 %s is %r" % (name, net, func, mcp.get(func)))


def main():
    errors = []
    check_motion(errors)
    check_panel(errors)
    for e in errors:
        print("MISMATCH:", e)
    print("check_pins: %d mismatch(es)" % len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run unit tests → pass; run the check**

```bash
python3 -m unittest discover -s hardware/tools/tests -v
python3 hardware/tools/check_pins.py
```

Expected: `check_pins: 0 mismatch(es)`. If `config.yaml: control.feed_hold_pin not found` appears, open `firmware/config.yaml` lines 136–180 and correct the section name in `MOTION_EXPECT` (sections seen at plan time: `uart1`, `axes`, `probe`, `control`, `Relay`). A real mismatch means the schematic is wrong — fix the builder, not the check.

- [ ] **Step 4: Prove the check catches a fault**

Temporarily change `"D26": "STEP"` to `"D26": "DIR"` and `"D27": "DIR"` to `"D27": "STEP"` in `motion_carrier.py`, regenerate, run `check_pins.py` → Expected: 2 mismatches, exit 1. Revert, regenerate, confirm 0.

- [ ] **Step 5: `verify.sh`**

```sh
#!/bin/sh
# Regenerate every KiCad project, run ERC, export PDFs, cross-check pins.
set -eu
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
HW="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m unittest discover -s "$HW/tools/tests"
python3 "$HW/tools/gen_schematics.py"
for p in motion-carrier panel-carrier system; do
  "$KICAD_CLI" sch erc --severity-error --exit-code-violations \
    -o "$HW/$p/$p-erc.rpt" "$HW/$p/$p.kicad_sch"
  "$KICAD_CLI" sch export pdf -o "$HW/$p/$p.pdf" "$HW/$p/$p.kicad_sch"
done
python3 "$HW/tools/check_pins.py"
echo "verify: OK"
```

Run: `chmod +x hardware/tools/verify.sh && hardware/tools/verify.sh` → Expected last line `verify: OK`.

- [ ] **Step 6: Commit**

```bash
git add hardware/tools hardware/*/*.pdf
git commit -m "feat(hardware): cross-check schematic pins against the firmware"
```

---

### Task 6: Documentation

**Files:**
- Create: `hardware/README.md`
- Modify: `CLAUDE.md` (Key paths table), `docs/SUPERSEDED.md` (table row)

- [ ] **Step 1: Write `hardware/README.md`**

```markdown
# Hardware — KiCad schematics (Rev H)

Generated from Python. **Do not edit the `.kicad_sch` files in KiCad** — the next
regeneration overwrites them. Change `tools/*.py` and run:

    hardware/tools/verify.sh     # tests, generate, ERC, PDFs, pin cross-check

| Project | What | For layout? |
| --- | --- | --- |
| `motion-carrier/` | ESP32 devkit sockets, 5 input conditioners, field terminals, link header | Yes |
| `panel-carrier/` | 74LVC14 MPG shifter, MCP23017 + pull-ups, MX1.25 leads to the display | Yes |
| `system/` | Mains, E-stop, PSU, modules and cabling between them | No — reference |

`tools/check_pins.py` fails if a schematic pin disagrees with `firmware/config.yaml` or
`hmi/include/pins.h`.

## Open items shown on the drawings

- Devkit header rows assume the DOIT 30-pin layout — verify against the board in hand.
- Contactor coil voltage (BOM block A).
- MPG output type — R3/R4 on the panel carrier are DNP until known.
- Foot-switch release mirror (MCP GPA6) — needs a second pedal contact or a shared-contact decision.
```

- [ ] **Step 2:** In `CLAUDE.md` Key paths table add rows:
  `| hardware/ | KiCad schematics generated by hardware/tools (see hardware/README.md) |` and change the `docs/BOM.md, docs/WIRING-RevH.*, docs/PINOUT.svg` row to also mention `hardware/system/system.pdf`.

- [ ] **Step 3:** In `docs/SUPERSEDED.md` table add:
  `| SCHEMATIC-RevH.svg | Hand-drawn Rev H schematic | hardware/ KiCad projects (system.pdf, carrier PDFs) |`
  Leave the file in place (other docs link to it).

- [ ] **Step 4: Final verification and commit**

```bash
hardware/tools/verify.sh
git add hardware/README.md CLAUDE.md docs/SUPERSEDED.md
git commit -m "docs: point to the generated KiCad schematics"
```
