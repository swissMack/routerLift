"""Motion carrier: ESP32 devkit, five input conditioners, field terminals."""
from devkit import DEVKIT_LEFT, DEVKIT_RIGHT
from kisch import Project, Sheet
import parts

CHANNELS = ["HOME", "TOP", "PROBE", "FOOT", "DRV_ALM"]

# Silkscreen name -> net. Firmware pin numbers are checked by check_pins.py.
DEVKIT_NETS = {
    "D26": "STEP", "D27": "DIR", "D14": "ENABLE", "D4": "RELAY_IN",
    "D33": "HOME_IN", "D25": "TOP_IN", "D32": "PROBE_IN", "D13": "FOOT_IN",
    "D35": "DRV_ALM_IN", "D21": "STOP", "D17": "LINK_TX", "D16": "LINK_RX",
    "VIN": "+5V", "GND": "GND", "3V3": "+3V3",
}


def conditioning(lib):
    s = Sheet("conditioning", "Input conditioning channel (x5)", lib, paper="A4")
    s.port("FIELD", "bidirectional")
    s.port("GPIO", "output")
    s.place(parts.R, "R?", "4.7k", (50.8, 50.8), {"1": "+3V3", "2": "FIELD"}, rot=90,
            footprint=parts.FP_R)
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
              + "\nDOIT 30-pin layout - verified against the HW-394 board silkscreen, 2026-09-14.\n"
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
