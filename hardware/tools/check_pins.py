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
            pin = str(find(node, "pin")[1])
            func = find(node, "pinfunction")
            pinfunction = str(func[1]) if func else ""
            # kicad-cli's kicadsexpr netlist writes pinfunction as "<pin_name>_<pin_number>"
            # (confirmed by exporting a real netlist: MCP23017 pin 21 -> "GPA0_21", 74xx pin
            # 14 -> "VCC_14", a Conn_01x04 pin 1 -> "Pin_1_1") rather than the bare pin name -
            # strip the pin's own number back off so callers can match on the plain name.
            suffix = "_" + pin
            if pinfunction.endswith(suffix):
                pinfunction = pinfunction[: -len(suffix)]
            nodes[(str(find(node, "ref")[1]), pin)] = (name, pinfunction)
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
