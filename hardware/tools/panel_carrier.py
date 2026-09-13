"""Panel carrier: MPG level shifter, MCP23017 button expander, leads to the display."""
from kisch import Project, Sheet
import parts

HDR4 = "Connector_Generic:Conn_01x04"
LVC14 = "74xx:74HC14"  # 74LVC14 is not in the stock KiCad library; Value overridden below.
POWER_UNIT = 7
GATE_PINS = {1: ("1", "2"), 2: ("3", "4"), 3: ("5", "6"), 4: ("9", "8"), 5: ("11", "10"), 6: ("13", "12")}
GATES = {1: ("MPG_A_5V", "MPG_A_N"), 2: ("MPG_A_N", "MPG_A_3V3"),
         3: ("MPG_B_5V", "MPG_B_N"), 4: ("MPG_B_N", "MPG_B_3V3"),
         5: ("GND", None), 6: ("GND", None)}
BUTTONS = ["BTN_CYCLE_START", "BTN_ROUTER", "BTN_BIT_CHANGE", "BTN_ZERO", "BTN_PRESET",
           "SW_ROUGH_FINE", "FOOT_MIRROR"]
MCP = "Interface_Expansion:MCP23017x-x-SO"


def build(lib, outdir):
    s = Sheet("panel-carrier", "routerLift panel carrier - Rev H", lib, paper="A3")
    s.place(HDR4, "J1", "display P3: IO6 IO7 IO15 IO16", (38.1, 50.8),
            {"1": "MPG_A_3V3", "2": "MPG_B_3V3", "3": "SDA", "4": "SCL"}, footprint=parts.FP_MX125_4)
    # field_gap=7.62 on J2/J4/J5: each has a +3V3 or +5V pin immediately next to a GND
    # (or another power) pin. At the default offset (STUB), a +3V3/+5V flag's own Value
    # text overlaps its own arrow's tip at this rotation (GND's flag clears fine at the
    # same offset - confirmed by rendering; see place()'s field_gap docstring). 5.08 was
    # tried first and still left the last glyph of "+5V" touching the arrow tip on J4/J5
    # (rendered and read at 600dpi) - 7.62 (3x STUB) clears it with visible margin on
    # every instance. GND-only connectors (J3, J6, J7) don't need it.
    s.place(HDR4, "J2", "display P4: GND 3.3V IO17 IO18", (38.1, 88.9),
            {"1": "GND", "2": "+3V3", "3": "LINK_TX", "4": "LINK_RX"}, footprint=parts.FP_MX125_4,
            field_gap=7.62)
    t2, t3, t4, t8 = parts.term(2), parts.term(3), parts.term(4), parts.term(8)
    s.place(t3[0], "J3", "LINK to motion: GND TX RX", (38.1, 127.0),
            {"1": "GND", "2": "LINK_TX", "3": "LINK_RX"}, footprint=t3[1])
    s.place(t4[0], "J4", "MPG +5V GND A B", (38.1, 165.1),
            {"1": "+5V", "2": "GND", "3": "MPG_A_5V", "4": "MPG_B_5V"}, footprint=t4[1],
            field_gap=7.62)
    s.place(t2[0], "J5", "5V IN from buck", (38.1, 203.2), {"1": "+5V", "2": "GND"},
            footprint=t2[1], field_gap=7.62)

    for unit, (inp, out) in GATES.items():
        pin_in, pin_out = GATE_PINS[unit]
        s.place(LVC14, "U1", "74LVC14", (114.3, 38.1 + (unit - 1) * 20.32),
                {pin_in: inp, pin_out: out}, unit=unit, footprint=parts.FP_SOIC14)
    # Power unit sits a full extra row pitch below U1F (not the usual single 20.32 step)
    # so its own +3V3 flag - pulled back up toward U1F by POWER_STUB - lands clear of
    # U1F's "74LVC14" Value text instead of on top of it (confirmed by rendering: at
    # the usual one-step gap they overlapped as "+3V74LVC14").
    s.place(LVC14, "U1", "74LVC14", (114.3, 180.34), {"14": "+3V3", "7": "GND"},
            unit=POWER_UNIT, footprint=parts.FP_SOIC14)
    s.place(parts.C, "C1", "100n", (139.7, 180.34), {"1": "+3V3", "2": "GND"}, footprint=parts.FP_C)
    s.place(parts.R, "R3", "10k DNP", (165.1, 38.1), {"1": "+5V", "2": "MPG_A_5V"},
            footprint=parts.FP_R, dnp=True)
    s.place(parts.R, "R4", "10k DNP", (177.8, 38.1), {"1": "+5V", "2": "MPG_B_5V"},
            footprint=parts.FP_R, dnp=True)

    # Interface_Expansion:MCP23017x-x-SO pin names (list_pins.py, 2026-09-13):
    # I2C clock pin is named SCK (not SCL); power pins are V_{DD}/V_{SS}; reset is
    # ~{RESET} as expected; pins 11 and 14 are NC (name "NC" is not unique, so they
    # must be keyed by pin number).
    mcp = {"SCK": "SCL", "SDA": "SDA", "A0": "GND", "A1": "GND", "A2": "GND",
           "~{RESET}": "+3V3", "INTA": None, "INTB": None, "V_{SS}": "GND", "V_{DD}": "+3V3",
           "11": None, "14": None, "GPA7": None, "GPB0": "LED_ROUTER_DRV"}
    mcp.update({"GPA%d" % i: net for i, net in enumerate(BUTTONS)})
    mcp.update({"GPB%d" % i: None for i in range(1, 8)})
    # field_gap: U2's own rows sit exactly STUB (2.54mm) either side of its origin
    # (GPA7/INTB at local y=+2.54, GPB0/RESET at y=-2.54), so the default Reference/
    # Value offset lands squarely on those rows. Clear past the whole 28-pin field
    # (rows run to local y=+/-20.32) so both fields land above/below the symbol instead.
    s.place(MCP, "U2", "MCP23017 @0x20", (254.0, 101.6), mcp,
            footprint=parts.FP_SOIC28, field_gap=27.94)
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
