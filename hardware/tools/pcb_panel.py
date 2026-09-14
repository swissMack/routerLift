"""Panel carrier placement. M3 hole in each corner.

Coordinates are mm from the board's top-left corner, y down (see pcbkit).
Display leads J1/J2 on the left edge; J3/J4/J5 along the top edge; J6/J7 along the bottom edge.
"""
import pcbnew

import pcbkit

NAME = "panel-carrier"
W, H = 80.0, 62.0
EDGE_MARGIN = 1.0
TOP_TERMINALS = ["J3", "J4", "J5"]        # link, MPG, 5 V in - left to right
BOTTOM_TERMINALS = ["J6", "J7"]           # buttons, LED - left to right
TERMINAL_X0 = 9.5                         # hole keep-out ends at 7.5; refdes sits in the gap
TERMINAL_GAP = 2.5
TERMINAL_ROT_TOP = 180                    # entries face the top edge - confirmed from 3D render
TERMINAL_ROT_BOTTOM = 0                   # entries face the bottom edge - confirmed from 3D render
HOLE_INSET = 4.0                          # 6.4 mm hole pad + 0.5 mm edge clearance
HOLES = [(HOLE_INSET, HOLE_INSET), (W - HOLE_INSET, HOLE_INSET),
         (HOLE_INSET, H - HOLE_INSET), (W - HOLE_INSET, H - HOLE_INSET)]
LABEL_GAP = 0.8                           # terminal courtyard to label start
LABEL_BAND = 10.5                         # room reserved for the vertical net labels
ESCAPE_DX = 2.0                           # U1 pin 8 pad centre to its B.Cu escape via
RES_PAD1_Y = 31.0                        # vertical axial resistors: pad 1 lowest
DECOUPLE_MAX = 3.0                       # cap courtyard to chip power pad, edge to edge
STITCH_TEXT_CLEAR = 1.0                   # no stitching via within this of any silk text
# Filled in by build(): a box around every silkscreen text (net labels, refdes, P3/P4, DNP),
# so vias never land under a label but can still stitch the pour between them.
STITCH_AVOID = []


def _mm(v):
    return pcbnew.ToMM(v.x) - pcbkit.ORIGIN[0], pcbnew.ToMM(v.y) - pcbkit.ORIGIN[1]


def set_ref(fp, b, x, y, rot=0, visible=True):
    ref = fp.Reference()
    ref.SetPosition(b.p(x, y))
    ref.SetTextAngleDegrees(rot)
    ref.SetVisible(visible)


def pad(fp, number):
    return [p for p in fp.Pads() if p.GetNumber() == number][0]


def terminal_label(netname):
    name = netname.lstrip("/")
    for prefix in ("BTN_", "SW_", "LINK_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def rect_gap(a, b):
    """Edge-to-edge distance between two (x0, y0, x1, y1) rectangles; 0 if they touch."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def pad_box(p):
    box = p.GetBoundingBox()
    return (pcbnew.ToMM(box.GetX()) - pcbkit.ORIGIN[0], pcbnew.ToMM(box.GetY()) - pcbkit.ORIGIN[1],
            pcbnew.ToMM(box.GetRight()) - pcbkit.ORIGIN[0],
            pcbnew.ToMM(box.GetBottom()) - pcbkit.ORIGIN[1])


def escape_via(b, ref, pin, dx, dy):
    """Locked F.Cu stub from a pad to a via on the pad's net; the autorouter keeps both."""
    p = pad(b.fps[ref], pin)
    start = p.GetPosition()
    end = pcbnew.VECTOR2I(start.x + pcbkit.MM(dx), start.y + pcbkit.MM(dy))
    t = pcbnew.PCB_TRACK(b.board)
    t.SetStart(start)
    t.SetEnd(end)
    t.SetWidth(pcbkit.MM(0.25))
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(p.GetNet())
    t.SetLocked(True)
    b.board.Add(t)
    v = pcbnew.PCB_VIA(b.board)
    v.SetPosition(end)
    v.SetWidth(pcbkit.MM(0.6))
    v.SetDrill(pcbkit.MM(0.3))
    v.SetNet(p.GetNet())
    v.SetLocked(True)
    b.board.Add(v)
    return v


def text_boxes(b, grow):
    """(x0, y0, x1, y1) mm boxes, grown by `grow`, around every visible silkscreen text."""
    items = [d for d in b.board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)]
    items += [fp.Reference() for fp in b.fps.values() if fp.Reference().IsVisible()]
    out = []
    for t in items:
        x0, y0, x1, y1 = pad_box(t)
        out.append((x0 - grow, y0 - grow, x1 + grow, y1 + grow))
    return out


def decoupling_gap(b, cap, chip, pin):
    return rect_gap(b.courtyard_mm(cap), pad_box(pad(b.fps[chip], pin)))


def _edge_row(b, comps, pads, refs, rot, bottom):
    x = TERMINAL_X0
    for ref in refs:
        fp = b.place(comps[ref], pads, 0, 0, rot=rot)
        x0, y0, _, y1 = b.courtyard_mm(ref)
        dy = (H - EDGE_MARGIN - y1) if bottom else (EDGE_MARGIN - y0)
        fp.SetPosition(b.p(x - x0, dy))
        cx0, cy0, cx1, cy1 = b.courtyard_mm(ref)
        yc = (cy0 + cy1) / 2
        set_ref(fp, b, cx0 - 0.8, yc, rot=90)       # in the gap to the block's left
        for p in fp.Pads():
            px, _ = _mm(p.GetPosition())
            # All labels read upward; each starts just off the courtyard and runs inboard.
            ly = cy0 - LABEL_GAP if bottom else cy1 + LABEL_GAP
            t = b.silk(terminal_label(p.GetNetname()), px, ly, size=1.0, rot=90)
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if bottom else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        x = cx1 + TERMINAL_GAP
    end = x - TERMINAL_GAP
    if end > W - 2 * HOLE_INSET:
        raise ValueError("edge row too wide for %.1f mm board: ends at %.1f" % (W, end))


def build(comps, pads):
    b = pcbkit.BoardBuilder(NAME, W, H)
    _edge_row(b, comps, pads, TOP_TERMINALS, TERMINAL_ROT_TOP, bottom=False)
    _edge_row(b, comps, pads, BOTTOM_TERMINALS, TERMINAL_ROT_BOTTOM, bottom=True)

    # Display leads on the left edge, pin 1 at the top of each.
    for ref, y, label in (("J1", 24.0, "P3"), ("J2", 36.0, "P4")):
        fp = b.place(comps[ref], pads, 3.0, y, rot=270)
        x0, y0, x1, y1 = b.courtyard_mm(ref)
        set_ref(fp, b, x1 + 1.2, y1 - 1.0, rot=90)
        _, p1y = _mm(pad(fp, "1").GetPosition())
        b.silk(label, (x0 + x1) / 2, y0 - 1.0)
        t = b.silk("1", x1 + 0.9, p1y, size=1.0)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)

    # I2C pull-ups beside J1.
    for ref, x in (("R1", 10.5), ("R2", 14.0)):
        fp = b.place(comps[ref], pads, x, RES_PAD1_Y, rot=90)
        set_ref(fp, b, x, RES_PAD1_Y + 3.3, rot=90)

    # MPG shifter under J4, DNP pull-ups to its left, decoupler at pins 14/13.
    fp = b.place(comps["U1"], pads, 34.5, 31.0, rot=0)
    set_ref(fp, b, 34.5, 31.0, rot=90)
    p14x, p14y = _mm(pad(b.fps["U1"], "14").GetPosition())
    # Above the pin-14 end, not beside the right pad column: beside it, C1 and the routing
    # starved the F.Cu thermals of GND pins 11/13 and of C1's own GND pad.
    fp = b.place(comps["C1"], pads, p14x, p14y - 3.3, rot=0)
    set_ref(fp, b, p14x + 7.3, p14y - 3.3, rot=90)
    # Outputs 4 and 8 both run to J1 on the left; on F.Cu the pin-8 trace has to wrap U1's
    # corner and closes the pour around GND pin 7 (starved thermal). Drop it to B.Cu at the pad.
    escape_via(b, "U1", "8", ESCAPE_DX, 0.0)
    for ref, x in (("R3", 22.5), ("R4", 26.0)):
        fp = b.place(comps[ref], pads, x, RES_PAD1_Y, rot=90)
        set_ref(fp, b, x, RES_PAD1_Y + 3.3, rot=90)
    b.silk("DNP", 24.25, RES_PAD1_Y + 5.9)

    # Button expander above J7, decoupler right at VDD/VSS (pins 9/10).
    fp = b.place(comps["U2"], pads, 57.5, 28.5, rot=90)
    set_ref(fp, b, 57.5, 28.5)
    p9x, p9y = _mm(pad(b.fps["U2"], "9").GetPosition())
    fp = b.place(comps["C2"], pads, p9x, p9y + 3.1, rot=0)
    set_ref(fp, b, p9x + 7.6, p9y + 3.1, rot=90)
    fp = b.place(comps["R5"], pads, 70.0, RES_PAD1_Y, rot=90)
    set_ref(fp, b, 70.0, RES_PAD1_Y + 3.3, rot=90)

    for hx, hy in HOLES:
        set_ref(b.mounting_hole(hx, hy), b, hx, hy, visible=False)
    b.silk("routerLift panel carrier Rev H", W - 2.2, H / 2, size=1.2, rot=90)
    b.ground_zones()
    STITCH_AVOID[:] = text_boxes(b, STITCH_TEXT_CLEAR)

    for cap, chip, pins in (("C1", "U1", ("14", "13")), ("C2", "U2", ("9", "10"))):
        for pin in pins:
            gap = decoupling_gap(b, cap, chip, pin)
            if gap > DECOUPLE_MAX:
                raise ValueError("%s is %.2f mm from %s pin %s (max %.1f)"
                                 % (cap, gap, chip, pin, DECOUPLE_MAX, ))
    return b
