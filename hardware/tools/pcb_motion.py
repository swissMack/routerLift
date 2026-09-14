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
# M3 holes, a true rectangle. Left column on the 4 mm edge inset; right column just left of the
# J1 refdes (J1/J2 sockets start at x 99.6), so the top-right hole stays >10 mm from the antenna.
# Bottom row sits above the terminal net labels (DRV_ALM label top ~60.6); the DRV_ALM
# conditioning block is lifted (BLOCK_DY) to make room for the bottom-right hole.
HOLE_X = (4.0, 93.0)
HOLE_Y = (4.0, 56.5)
HOLES = [(HOLE_X[0], HOLE_Y[0]), (HOLE_X[1], HOLE_Y[0]), (HOLE_X[0], HOLE_Y[1]), (HOLE_X[1], HOLE_Y[1])]
HOLE_EDGE_MIN = 4.0                                  # hole centre to board edge
HOLE_CLEAR = 0.5                                     # hole courtyard to other courtyards / text
HOLE_LABEL_POS = (9.0, HOLE_Y[1])                    # right of the bottom-left hole
ANTENNA_CLEAR = 10.0                                 # nothing but the devkit this close to the keep-out
LINK_NOTE = "LINK: straight-through 1-1 2-2 3-3"
STITCH_AVOID = [(0.0, 59.0, W, H),                   # terminal net-label band + terminal row
                (ANTENNA_KEEPOUT[0] - ANTENNA_CLEAR, 0.0, W, ANTENNA_KEEPOUT[3] + ANTENNA_CLEAR)]
# Left short edge, far from the antenna end. rot 90: pin 1 (GND) lowest.
J8_POS = (5.0, 36.0)
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
BLOCK_DY = {"DRV_ALM": -7.5}                         # whole block lifted, clear of hole (93, 56.5)
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
    # J2's refdes sits below its tail end: beside the tail it collides with the lifted DRV_ALM cap.
    for ref, y, rdx, rdy in (("J1", DEVKIT_TOP_ROW_Y, 0.0, 0.0),
                             ("J2", DEVKIT_TOP_ROW_Y + ROW_SPACING, 2.8, 3.6)):
        fp = b.place(comps[ref], pads, DEVKIT_PIN1_X, y, rot=270)
        set_ref(fp, b, tail_x + rdx, y + rdy)
    b.rule_area(*ANTENNA_KEEPOUT)
    b.silk("ANTENNA THIS EDGE >", W - 17.0, 2.6)
    b.silk("DEVKIT ROWS 25.4 mm - VERIFY", DEVKIT_PIN1_X - 18.0,
           DEVKIT_TOP_ROW_Y + ROW_SPACING / 2)

    # Conditioning channels: a block above each channel's field terminal pin.
    for ch in CHANNELS:
        pullup, series, diode, cap = channel_parts(pads, ch)
        tref, tpin = FIELD_TERMINAL_PIN[ch]
        px = pad_x(b.fps[tref], tpin)
        dy = BLOCK_DY.get(ch, 0.0)
        for ref, dx in ((pullup, -BLOCK_R_DX), (series, BLOCK_R_DX)):
            fp = b.place(comps[ref], pads, px + dx, BLOCK_R_Y + dy, rot=90)
            set_ref(fp, b, px + dx, BLOCK_R_REF_Y + dy)
        fp = b.place(comps[diode], pads, px + BLOCK_D[0], BLOCK_D[1] + dy, rot=0)
        set_ref(fp, b, px + BLOCK_D[0], BLOCK_DC_REF_Y + dy)
        fp = b.place(comps[cap], pads, px + BLOCK_C[0], BLOCK_C[1] + dy, rot=90)
        set_ref(fp, b, px + BLOCK_C[0], BLOCK_DC_REF_Y + dy)
        b.silk(ch, px, BLOCK_LABEL_Y + dy, size=1.0)

    # J8 on the left short edge (away from the antenna). Pin labels, with the shared link net
    # names, sit on its board side; the wiring note sits above it.
    j8 = b.place(comps["J8"], pads, J8_POS[0], J8_POS[1], rot=90)
    x0, y0, x1, y1 = b.courtyard_mm("J8")
    set_ref(j8, b, (x0 + x1) / 2, y1 + 0.9)
    for pad in j8.Pads():
        py = pcbnew.ToMM(pad.GetPosition().y) - pcbkit.ORIGIN[1]
        t = b.silk(pad.GetNetname().lstrip("/"), x1 + 0.8, py, size=1.0)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    t = b.silk(LINK_NOTE, x0, y0 - 0.9, size=1.0)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    b.silk("routerLift motion carrier Rev H", 32.0, 3.0, size=1.2)

    # Mounting holes: a rectangle, inset from the edges, clear of every courtyard and text,
    # and ANTENNA_CLEAR from the antenna keep-out. Checked before the holes are placed.
    hx0, hy0, hx1, hy1 = pcbkit.hole_rectangle(HOLES)
    pitch = "M3 HOLES %g x %g mm PITCH - VERIFY CLIPS" % (hx1 - hx0, hy1 - hy0)
    t = b.silk(pitch, HOLE_LABEL_POS[0], HOLE_LABEL_POS[1], size=1.0)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    obstacles = [(r, b.courtyard_mm(r)) for r in b.fps] + [("text", tb) for tb in b.text_boxes()]
    for hx, hy in HOLES:
        fp = b.mounting_hole(hx, hy)
        set_ref(fp, b, hx, hy, visible=False)
        if min(hx, hy, W - hx, H - hy) < HOLE_EDGE_MIN:
            raise ValueError("hole (%g, %g) closer than %g mm to the board edge" % (hx, hy, HOLE_EDGE_MIN))
        box = b.courtyard_mm(fp.GetReference())
        if pcbkit.rect_gap(box, ANTENNA_KEEPOUT) < ANTENNA_CLEAR:
            raise ValueError("hole (%g, %g) within %g mm of the antenna keep-out" % (hx, hy, ANTENNA_CLEAR))
        for what, other in obstacles:
            if pcbkit.rect_gap(box, other) < HOLE_CLEAR:
                raise ValueError("hole (%g, %g) courtyard hits %s %r" % (hx, hy, what, other))
    b.ground_zones()
    b.stitch_avoid = list(STITCH_AVOID) + b.text_boxes(1.0)   # also keep vias off silk text
    return b
