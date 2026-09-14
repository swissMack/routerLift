"""Motion carrier placement. Board 140 x 80 mm; terminals on the bottom edge.

Coordinates are mm from the board's top-left corner, y down (see pcbkit).
"""
import pcbnew

from pcb_netlist import refs_on_net
import pcbkit

NAME = "motion-carrier"
W, H = 140.0, 80.0
TERMINALS = ["J3", "J4", "J5", "J6", "J7"]           # left to right along the bottom edge
TERMINAL_ROT = 0                                     # 0 or 180 - confirmed from the 3D render
TERMINAL_GAP = 2.0
TERMINAL_X0 = 6.0
EDGE_MARGIN = 1.0
ROW_SPACING = 25.4                                   # devkit rows - UNVERIFIED
DEVKIT_PIN1_X = W - 3.0                              # pin 1 (antenna end) near the right edge
DEVKIT_TOP_ROW_Y = 8.0
ANTENNA_KEEPOUT = (W - 6.0, 4.0, W, 38.0)
HOLES = [(4.0, 4.0), (85.0, 4.0), (4.0, 62.0), (W - 4.0, 62.0)]
STITCH_AVOID = [(0.0, 59.0, W, H)]                   # terminal net-label band + terminal row
J8_POS = (134.0, 52.0)                             # rot 90: pin 1 (GND) lowest
CHANNELS = ["HOME", "TOP", "PROBE", "FOOT", "DRV_ALM"]
FIELD_TERMINAL_PIN = {"HOME": ("J6", "1"), "TOP": ("J6", "3"), "DRV_ALM": ("J6", "5"),
                      "PROBE": ("J7", "1"), "FOOT": ("J7", "3")}
# Conditioning block, relative to the field pin's x. Resistors stand vertically (rot 90, pad 1
# lowest) just above the terminal labels; BAT54S and the cap sit above them.
BLOCK_R_Y = 58.5
BLOCK_R_DX = 2.0
BLOCK_R_REF_Y = 47.8
BLOCK_D = (-2.0, 43.0)
BLOCK_C = (2.0, 45.5)
BLOCK_DC_REF_Y = 38.4
BLOCK_LABEL_Y = 36.6
LABEL_GAP = 0.8                                      # terminal courtyard top to label start


def set_ref(fp, b, x, y, rot=0, visible=True):
    ref = fp.Reference()
    ref.SetPosition(b.p(x, y))
    ref.SetTextAngleDegrees(rot)
    ref.SetVisible(visible)


def channel_parts(pads, channel):
    """(pull-up R, series R, BAT54S, C) for one conditioning channel, found by nets."""
    field, gpio = "/%s_FIELD" % channel, "/%s_IN" % channel
    series = [r for r in refs_on_net(pads, field, "R") if r in refs_on_net(pads, gpio, "R")][0]
    pullup = [r for r in refs_on_net(pads, field, "R") if r != series][0]
    diode = refs_on_net(pads, gpio, "D")[0]
    cap = refs_on_net(pads, gpio, "C")[0]
    return pullup, series, diode, cap


def terminal_label(netname):
    name = netname.lstrip("/")
    for suffix in ("_FIELD", "_IN"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


def pad_x(fp, number):
    pad = [p for p in fp.Pads() if p.GetNumber() == number][0]
    return pcbnew.ToMM(pad.GetPosition().x) - pcbkit.ORIGIN[0]


def build(comps, pads):
    b = pcbkit.BoardBuilder(NAME, W, H)

    # Terminals: measure each courtyard at the origin, then move it so the courtyard sits
    # EDGE_MARGIN inside the bottom edge, wire entries facing that edge.
    x = TERMINAL_X0
    for ref in TERMINALS:
        fp = b.place(comps[ref], pads, 0, 0, rot=TERMINAL_ROT)
        x0, _, _, y1 = b.courtyard_mm(ref)
        fp.SetPosition(b.p(x - x0, (H - EDGE_MARGIN) - y1))
        cx0, cy0, cx1, _ = b.courtyard_mm(ref)
        # Refdes in the gap to the left of the block, clear of the net labels above it.
        set_ref(fp, b, cx0 - 0.9, pcbnew.ToMM(fp.GetPosition().y) - pcbkit.ORIGIN[1], rot=90)
        for pad in fp.Pads():
            px = pcbnew.ToMM(pad.GetPosition().x) - pcbkit.ORIGIN[0]
            t = b.silk(terminal_label(pad.GetNetname()), px, cy0 - LABEL_GAP, size=1.0, rot=90)
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)   # reads upward, away from the pad
        x = cx1 + TERMINAL_GAP
    if x - TERMINAL_GAP > W - 1.0:
        raise ValueError("terminals need a board at least %.1f mm wide" % (x - TERMINAL_GAP + 1.0))

    # Devkit sockets, rotated so pin 1 is at the right (antenna) end. J1 (left row, EN) on top.
    tail_x = DEVKIT_PIN1_X - 14 * 2.54 - 3.2           # past pin 15, away from the antenna
    for ref, y in (("J1", DEVKIT_TOP_ROW_Y), ("J2", DEVKIT_TOP_ROW_Y + ROW_SPACING)):
        fp = b.place(comps[ref], pads, DEVKIT_PIN1_X, y, rot=270)
        set_ref(fp, b, tail_x, y)
    b.rule_area(*ANTENNA_KEEPOUT)
    b.silk("ANTENNA THIS EDGE >", W - 17.0, 2.6)
    b.silk("DEVKIT ROWS 25.4 mm - VERIFY", DEVKIT_PIN1_X - 18.0,
           DEVKIT_TOP_ROW_Y + ROW_SPACING / 2)

    # Conditioning channels: a block above each channel's field terminal pin.
    for ch in CHANNELS:
        pullup, series, diode, cap = channel_parts(pads, ch)
        tref, tpin = FIELD_TERMINAL_PIN[ch]
        px = pad_x(b.fps[tref], tpin)
        for ref, dx in ((pullup, -BLOCK_R_DX), (series, BLOCK_R_DX)):
            fp = b.place(comps[ref], pads, px + dx, BLOCK_R_Y, rot=90)
            set_ref(fp, b, px + dx, BLOCK_R_REF_Y)
        fp = b.place(comps[diode], pads, px + BLOCK_D[0], BLOCK_D[1], rot=0)
        set_ref(fp, b, px + BLOCK_D[0], BLOCK_DC_REF_Y)
        fp = b.place(comps[cap], pads, px + BLOCK_C[0], BLOCK_C[1], rot=90)
        set_ref(fp, b, px + BLOCK_C[0], BLOCK_DC_REF_Y)
        b.silk(ch, px, BLOCK_LABEL_Y, size=1.0)

    # J8 on the right short edge, beside the devkit's TX/RX pins (J2-9/10). On the left edge the
    # ~108 mm link run cut the B.Cu pour and starved J2-14's thermal (see task-3 report).
    j8 = b.place(comps["J8"], pads, J8_POS[0], J8_POS[1], rot=90)
    x0, y0, _, _ = b.courtyard_mm("J8")
    set_ref(j8, b, J8_POS[0] + 1.0, y0 - 0.9)
    for pad in j8.Pads():
        py = pcbnew.ToMM(pad.GetPosition().y) - pcbkit.ORIGIN[1]
        t = b.silk(terminal_label(pad.GetNetname()).replace("LINK_", ""), x0 - 0.8, py, size=1.0)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    b.silk("LINK", x0 - 3.0, y0 - 0.9, size=1.0)
    for hx, hy in HOLES:
        set_ref(b.mounting_hole(hx, hy), b, hx, hy, visible=False)
    b.silk("routerLift motion carrier Rev H", 32.0, 3.0, size=1.2)
    b.ground_zones()
    return b
