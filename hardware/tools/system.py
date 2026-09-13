"""System reference drawing: mains and low-voltage wiring between modules. Not for layout."""
import kisch
from kisch import GRID, Project, Sheet, box_symbol, write_symbol_library

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


def box_field_gap(name):
    """place()'s default field_gap (STUB, 2.54mm) is far smaller than most of these
    boxes: box_symbol()'s Reference/Value sit at a fixed offset from the part's origin
    regardless of box height, so on any box with 3+ rows the default offset lands the
    Reference or Value squarely on one of the box's own pin rows - confirmed by
    rendering MAINS_INLET (Value "Mains inlet" overlapping its own PE pin's name) and
    PSU_24_36V/RELAY_MODULE/PANEL_BUTTONS the same way. Push both fields clear of the
    box's own top/bottom edge (half_h, computed the same way as box_symbol()) plus one
    full row pitch (2*GRID) of margin, on the 1.27mm grid, for every box - not just the
    ones with a same-row collision, since a short gap still leaves several boxes with
    text visibly hugging their own outline (checked by rendering)."""
    left, right = BOXES[name]
    rows = max(len(left), len(right), 1)
    half_h = round(GRID * (rows + 1), 4)
    return round(half_h + 2 * GRID, 4)


def place_box(s, name, ref, value, at, nets, rot=0):
    s.place(box(name), ref, value, at, nets, rot=rot, field_gap=box_field_gap(name))


def rejog(s, name, at, pin_key, net, extra, rot=0):
    """Move the wire+label place_box() just drew for one pin, adding a perpendicular
    jog before the label. Needed once, for RELAY_MODULE's NO/RELAY_NO: it sits on
    the row immediately next to COM/L_FUSED, and both COM and NO are GLOBAL nets, so
    both get the same longer POWER_STUB (see kisch.py place()'s stub comment) and
    stay exactly as close together as before - the fix that separates a global net
    from a plain-labelled neighbour (moving it further along its own stub direction,
    clear of the neighbour's shorter one) does nothing when BOTH neighbours move by
    the same amount and stay aligned. A global label's own shape (hex + Intersheet-
    refs) measured about 3.4mm tall by rendering, taller than the 2.54mm row pitch
    between COM and NO, so simply removing and redrawing the one wire+label with an
    extra sideways step, clear of the other, is what actually separates them -
    confirmed by rendering."""
    pins = s.lib.pins(box(name))
    pin = next(p for p in pins.values() if p.name == pin_key)
    point = kisch.pin_point(at, rot, pin)
    d = kisch.pin_outward(rot, pin)
    base = kisch.POWER_STUB if (net in kisch.POWER_NETS or net in s.globals) else kisch.STUB
    old_end = (round(point[0] + d[0] * base, 4), round(point[1] + d[1] * base, 4))
    s.items = [it for it in s.items if not (
        (it[0] == "wire" and tuple(kisch.find(it, "pts")[2][1:]) == old_end) or
        (it[0] in ("label", "global_label") and it[1] == net
         and tuple(kisch.find(it, "at")[1:3]) == old_end))]
    perp = (-d[1], d[0])
    mid = (round(point[0] + d[0] * kisch.STUB, 4), round(point[1] + d[1] * kisch.STUB, 4))
    jogged = (round(mid[0] + perp[0] * extra, 4), round(mid[1] + perp[1] * extra, 4))
    end = (round(jogged[0] + d[0] * (base - kisch.STUB), 4),
           round(jogged[1] + d[1] * (base - kisch.STUB), 4))
    s.wire(point, mid)
    s.wire(mid, jogged)
    s.wire(jogged, end)
    s.label(net, end, d, field_gap=box_field_gap(name))


def mains(lib):
    s = Sheet("mains", "Mains, E-stop and router power", lib, paper="A3", globals=GLOBALS)
    place_box(s, "MAINS_INLET", "M?", "Mains inlet", (50.8, 76.2),
              {"L": "L_SUPPLY", "N": "N_SUPPLY", "PE": "PE"})
    place_box(s, "RCD", "M?", "RCD", (114.3, 76.2),
              {"L_IN": "L_SUPPLY", "N_IN": "N_SUPPLY", "L_OUT": "L_RCD", "N_OUT": "N_RCD"})
    place_box(s, "ESTOP_NC", "M?", "E-stop mushroom NC", (177.8, 76.2),
              {"L_IN": "L_RCD", "L_OUT": "L_ESTOP"})
    s.place("Device:Fuse", "F1", "Fuse, PSU + router", (228.6, 76.2),
            {"1": "L_ESTOP", "2": "L_FUSED"}, rot=90)
    place_box(s, "PSU_24_36V", "M?", "PSU 24-36 V", (304.8, 76.2),
              {"L": "L_FUSED", "N": "N_RCD", "PE": "PE", "V+": "+24V", "V-": "GND"})
    place_box(s, "KEY_SWITCH", "M?", "Bit-change key switch", (114.3, 152.4),
              {"IN": "RELAY_NO", "OUT": "COIL_A1"})
    place_box(s, "CONTACTOR", "M?", "Router contactor", (177.8, 152.4),
              {"A1": "COIL_A1", "A2": "N_RCD", "L1": "L_FUSED", "L2": "N_RCD",
               "T1": "ROUTER_L", "T2": "ROUTER_N"})
    place_box(s, "RC_SNUBBER", "M?", "RC snubber", (177.8, 203.2),
              {"X1": "L_FUSED", "X2": "ROUTER_L"})
    place_box(s, "ROUTER_SOCKET", "M?", "Router socket", (304.8, 152.4),
              {"L": "ROUTER_L", "N": "ROUTER_N", "PE": "PE"})
    place_box(s, "PE_BOND", "M?", "PE: enclosure + lift frame", (304.8, 203.2), {"PE": "PE"})
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
    place_box(s, "BUCK_5V", "M?", "Buck 5 V >=2 A", (63.5, 50.8),
              {"VIN+": "+24V", "VIN-": "GND", "5V": "+5V", "GND": "GND"})
    place_box(s, "MOTION_CARRIER", "M?", "Motion carrier", (177.8, 101.6),
              {"+5V": "+5V", "GND": "GND", "LINK_GND": "GND", "LINK_TX": "LINK_TX", "LINK_RX": "LINK_RX",
               "PUL+": "PUL_P", "PUL-": "PUL_N", "DIR+": "DIR_P", "DIR-": "DIR_N",
               "ENA+": "ENA_P", "ENA-": "ENA_N", "RELAY_5V": "+5V", "RELAY_GND": "GND",
               "RELAY_IN": "RELAY_IN", "HOME": "HOME_SIG", "TOP": "TOP_SIG", "DRV_ALM": None,
               "PROBE": "PROBE_SIG", "FOOT": "FOOT_SIG", "STOP": "STOP_SIG", "SIG_GND": "GND"})
    place_box(s, "TB6600", "M?", "TB6600 1/8 step", (292.1, 63.5),
              {"PUL+": "PUL_P", "PUL-": "PUL_N", "DIR+": "DIR_P", "DIR-": "DIR_N",
               "ENA+": "ENA_P", "ENA-": "ENA_N", "VCC": "+24V", "GND": "GND",
               "A+": "MOT_A_P", "A-": "MOT_A_N", "B+": "MOT_B_P", "B-": "MOT_B_N"})
    place_box(s, "STEPPER", "M?", "Stepper motor", (381.0, 63.5),
              {"A+": "MOT_A_P", "A-": "MOT_A_N", "B+": "MOT_B_P", "B-": "MOT_B_N"})
    place_box(s, "RELAY_MODULE", "M?", "5 V relay module", (292.1, 127.0),
              {"VCC": "+5V", "GND": "GND", "IN": "RELAY_IN", "COM": "L_FUSED", "NO": "RELAY_NO"})
    rejog(s, "RELAY_MODULE", (292.1, 127.0), "NO", "RELAY_NO", 2 * GRID)
    place_box(s, "LIMIT_SWITCH_NC", "M?", "HOME bottom limit NC", (292.1, 177.8),
              {"C": "GND", "NC": "HOME_SIG"})
    place_box(s, "LIMIT_SWITCH_NC", "M?", "TOP limit NC", (292.1, 203.2),
              {"C": "GND", "NC": "TOP_SIG"})
    place_box(s, "PROBE_PLATE", "M?", "Touch plate + clip on bit", (292.1, 228.6),
              {"PLATE": "PROBE_SIG", "CLIP": "GND"})
    place_box(s, "FOOT_PEDAL", "M?", "Foot pedal NO", (292.1, 254.0),
              {"C1": "GND", "NO1": "FOOT_SIG", "C2": "GND", "NO2": "FOOT_MIRROR"})
    place_box(s, "STOP_BUTTON", "M?", "STOP flush NO", (292.1, 284.48),
              {"C": "GND", "NO": "STOP_SIG"})
    place_box(s, "PANEL_CARRIER", "M?", "Panel carrier", (177.8, 330.2),
              {"LINK_GND": "GND", "LINK_TX": "LINK_TX", "LINK_RX": "LINK_RX", "+5V": "+5V",
               "GND": "GND", "MPG_5V": "+5V", "MPG_GND": "GND", "MPG_A": "MPG_A", "MPG_B": "MPG_B",
               "P3": "LEAD_P3", "P4": "LEAD_P4", "CYCLE": "BTN_CYCLE_START", "ROUTER": "BTN_ROUTER",
               "BIT": "BTN_BIT_CHANGE", "ZERO": "BTN_ZERO", "PRESET": "BTN_PRESET",
               "ROUGH_FINE": "SW_ROUGH_FINE", "FOOT_MIRROR": "FOOT_MIRROR", "BTN_GND": "GND",
               "LED+": "LED_A", "LED-": "GND"})
    place_box(s, "DISPLAY_JC4827W543C", "M?", "Guition JC4827W543C", (292.1, 330.2),
              {"P1_5V": "+5V", "P1_GND": "GND", "P3": "LEAD_P3", "P4": "LEAD_P4"})
    place_box(s, "MPG_ZS80", "M?", "MPG ZS80 100 PPR 5 V", (63.5, 330.2),
              {"5V": "+5V", "GND": "GND", "A": "MPG_A", "B": "MPG_B"})
    place_box(s, "PANEL_BUTTONS", "M?", "Panel buttons + rough/fine", (292.1, 381.0),
              {"CYCLE": "BTN_CYCLE_START", "ROUTER": "BTN_ROUTER", "BIT": "BTN_BIT_CHANGE",
               "ZERO": "BTN_ZERO", "PRESET": "BTN_PRESET", "ROUGH_FINE": "SW_ROUGH_FINE", "COM": "GND"})
    place_box(s, "ROUTER_LED", "M?", "ROUTER LED", (381.0, 330.2), {"A": "LED_A", "K": "GND"})
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
