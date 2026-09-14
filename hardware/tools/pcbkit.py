"""Build KiCad boards with pcbnew. Run under KiCad's bundled python.

Coordinates are millimetres from the board's top-left corner, y down.
"""
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pcbnew

FP_DIR = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
ORIGIN = (100.0, 100.0)  # where the board sits on the KiCad page
NET_CLASS_POWER = ("+5V", "+3V3", "GND")
MM = pcbnew.FromMM

# JLCPCB design rules, mm. apply_rules() and every hand-placed track/via read these.
CLEARANCE = 0.25
TRACK_WIDTH = 0.25
POWER_TRACK_WIDTH = 0.6
VIA_DIAMETER = 0.6
VIA_DRILL = 0.3

TOOLS = Path(__file__).resolve().parent
FREEROUTING_SCRIPT = TOOLS / "get_freerouting.sh"
FREEROUTING_CACHE = TOOLS / ".cache"


def pinned_freerouting_version():
    """The version get_freerouting.sh downloads: $FREEROUTING_VERSION, else the script's default."""
    env = os.environ.get("FREEROUTING_VERSION")
    if env:
        return env
    m = re.search(r"FREEROUTING_VERSION:-([^}]+)\}", FREEROUTING_SCRIPT.read_text())
    if not m:
        raise RuntimeError("no default FREEROUTING_VERSION in " + str(FREEROUTING_SCRIPT))
    return m.group(1)


def freerouting_jar(cache=FREEROUTING_CACHE, version=None):
    """Path of the cached jar for the pinned version; raises if it has not been downloaded."""
    version = version or pinned_freerouting_version()
    jar = Path(cache) / ("freerouting-%s.jar" % version.lstrip("v"))
    if not jar.is_file():
        raise FileNotFoundError("Freerouting %s not found at %s - run hardware/tools/get_freerouting.sh"
                                % (version, jar))
    return jar


def rect_gap(a, b):
    """Edge-to-edge distance between two (x0, y0, x1, y1) rectangles; 0 if they touch or overlap."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def hole_rectangle(holes, tol=1e-6):
    """(x0, y0, x1, y1) of four hole centres that form an axis-aligned rectangle; ValueError if not."""
    if len(holes) != 4:
        raise ValueError("expected 4 holes, got %d" % len(holes))
    xs = sorted(set(round(x / tol) * tol for x, _ in holes))
    ys = sorted(set(round(y / tol) * tol for _, y in holes))
    corners = set((round(x / tol) * tol, round(y / tol) * tol) for x, y in holes)
    if len(xs) != 2 or len(ys) != 2 or corners != set((x, y) for x in xs for y in ys):
        raise ValueError("holes are not a rectangle: %r" % (holes,))
    return xs[0], ys[0], xs[1], ys[1]


def bbox_mm(item):
    box = item.GetBoundingBox()
    return (pcbnew.ToMM(box.GetX()) - ORIGIN[0], pcbnew.ToMM(box.GetY()) - ORIGIN[1],
            pcbnew.ToMM(box.GetRight()) - ORIGIN[0], pcbnew.ToMM(box.GetBottom()) - ORIGIN[1])


def _load_fp(lib_id):
    lib, name = lib_id.split(":", 1)
    fp = pcbnew.FootprintLoad(str(FP_DIR / (lib + ".pretty")), name)
    if fp is None:
        raise KeyError("footprint not found: " + lib_id)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))  # keep the nickname, or DRC reports a symbol mismatch
    return fp


class BoardBuilder:
    def __init__(self, name, width, height):
        self.name, self.w, self.h = name, float(width), float(height)
        self.board = pcbnew.BOARD()
        self.nets, self.fps = {}, {}
        self._holes = 0
        self.holes = []          # (x, y) centres, in placement order
        self.stitch_avoid = []   # (x0, y0, x1, y1) mm boxes where stitch_ground() places no via
        rect = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_RECT)
        rect.SetStart(self.p(0, 0))
        rect.SetEnd(self.p(self.w, self.h))
        rect.SetLayer(pcbnew.Edge_Cuts)
        rect.SetWidth(MM(0.1))
        self.board.Add(rect)

    def p(self, x, y):
        return pcbnew.VECTOR2I(MM(ORIGIN[0] + x), MM(ORIGIN[1] + y))

    def net(self, name):
        if name not in self.nets:
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.nets[name] = item
        return self.nets[name]

    def place(self, comp, pads, x, y, rot=0):
        fp = _load_fp(comp.footprint)
        fp.SetReference(comp.ref)
        fp.SetValue(comp.value)
        self.board.Add(fp)
        fp.SetPosition(self.p(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetDNP(bool(comp.dnp))  # else schematic parity reports a 'Do not populate' mismatch
        if comp.datasheet:
            fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText(comp.datasheet)
        if comp.description:
            fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(comp.description)
        for pad in fp.Pads():
            netname = pads.get((comp.ref, pad.GetNumber()))
            if netname:
                pad.SetNet(self.net(netname))
        self.fps[comp.ref] = fp
        return fp

    def mounting_hole(self, x, y):
        self._holes += 1
        fp = _load_fp("MountingHole:MountingHole_3.2mm_M3_Pad")
        fp.SetReference("H%d" % self._holes)
        fp.SetValue("M3")
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM)
        self.board.Add(fp)
        fp.SetPosition(self.p(x, y))
        self.fps[fp.GetReference()] = fp
        self.holes.append((float(x), float(y)))
        return fp

    def text_boxes(self, grow=0.0):
        """(x0, y0, x1, y1) mm boxes, grown by `grow`, around every visible silkscreen text."""
        items = [d for d in self.board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)]
        items += [fp.Reference() for fp in self.fps.values() if fp.Reference().IsVisible()]
        out = []
        for t in items:
            x0, y0, x1, y1 = bbox_mm(t)
            out.append((x0 - grow, y0 - grow, x1 + grow, y1 + grow))
        return out

    def _outline_zone(self, zone, x0, y0, x1, y1):
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            pt = self.p(x, y)
            outline.Append(pt.x, pt.y)

    def rule_area(self, x0, y0, x1, y1):
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowZoneFills(True)  # KiCad 10 name for "no copper pour"
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        self._outline_zone(z, x0, y0, x1, y1)
        self.board.Add(z)
        return z

    def ground_zones(self):
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(self.board)
            z.SetLayer(layer)
            z.SetNet(self.net("GND"))
            z.SetLocalClearance(MM(0.3))
            z.SetMinThickness(MM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            self._outline_zone(z, 0.5, 0.5, self.w - 0.5, self.h - 0.5)
            self.board.Add(z)

    def silk(self, text, x, y, size=1.0, rot=0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(text)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(0.15))
        t.SetPosition(self.p(x, y))
        t.SetTextAngleDegrees(rot)
        self.board.Add(t)
        return t

    def courtyard_mm(self, ref):
        box = self.fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        return (pcbnew.ToMM(box.GetX()) - ORIGIN[0], pcbnew.ToMM(box.GetY()) - ORIGIN[1],
                pcbnew.ToMM(box.GetRight()) - ORIGIN[0], pcbnew.ToMM(box.GetBottom()) - ORIGIN[1])

    def save(self, path):
        _save_board(self.board, path)


def apply_rules(board):
    """Apply JLCPCB-compatible clearances and net classes to a live pcbnew.BOARD.

    This is the single source of truth for design rules -- it sets pcbnew's own
    BOARD_DESIGN_SETTINGS and NET_SETTINGS directly, so pcbnew.SaveBoard() then
    writes correct values into the sibling .kicad_pro itself, and anything that
    reads the live board (DSN export for the autorouter, kicad-cli DRC) sees the
    same rules. Idempotent -- safe to call again after a load/save cycle, which
    is required wherever a board is reloaded from disk (autoroute(), stitch_ground()).
    """
    ds = board.GetDesignSettings()
    ds.m_MinClearance = MM(CLEARANCE)
    ds.m_TrackMinWidth = MM(TRACK_WIDTH)
    ds.m_ViasMinSize = MM(VIA_DIAMETER)
    ds.m_MinThroughDrill = MM(VIA_DRILL)
    ds.m_CopperEdgeClearance = MM(0.5)
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_MinSilkTextHeight = MM(1.0)
    ds.m_MinSilkTextThickness = MM(0.15)

    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetTrackWidth(MM(TRACK_WIDTH))
    default.SetClearance(MM(CLEARANCE))
    default.SetViaDiameter(MM(VIA_DIAMETER))
    default.SetViaDrill(MM(VIA_DRILL))

    power = pcbnew.NETCLASS("Power")
    power.SetTrackWidth(MM(POWER_TRACK_WIDTH))
    power.SetClearance(MM(CLEARANCE))
    power.SetViaDiameter(MM(VIA_DIAMETER))
    power.SetViaDrill(MM(VIA_DRILL))
    ns.SetNetclass("Power", power)

    for pattern in NET_CLASS_POWER:
        ns.SetNetclassPatternAssignment(pattern, "Power")

    board.SynchronizeNetsAndNetClasses(False)


def _save_board(board, path):
    """Save `board` to `path`, saving+restoring the sibling .kicad_pro.

    pcbnew.SaveBoard() also (re)writes the sibling .kicad_pro with whatever is
    in the live board's design settings / net classes, discarding every other
    top-level key that was already in the file (the real carriers' schematic-
    derived settings, sheet layout, etc.). Snapshot the file first and restore
    every top-level key except "board" and "net_settings" -- those two pcbnew
    now owns, and apply_rules() is what puts the right values in them. "meta"
    is left as pcbnew wrote it unless the snapshot's meta.filename differs
    (e.g. the project was renamed), in which case the snapshot's meta wins.
    """
    path = Path(path)
    pro = path.with_suffix(".kicad_pro")
    prior = json.loads(pro.read_text()) if pro.exists() else None
    pcbnew.SaveBoard(str(path), board)
    if prior is None:
        return
    new = json.loads(pro.read_text())
    for key, val in prior.items():
        if key in ("board", "net_settings", "meta"):
            continue
        new[key] = val
    old_meta, new_meta = prior.get("meta"), new.get("meta")
    if old_meta is not None and (old_meta.get("filename") != (new_meta or {}).get("filename")):
        new["meta"] = old_meta
    pro.write_text(json.dumps(new, indent=2) + "\n")


def autoroute(pcb_path, jar, flags):
    """Export DSN, run Freerouting, import SES, refill zones, save in place.

    flags: callable(dsn, ses) -> list of Freerouting CLI args (from Task 1's --help record).
    """
    board = pcbnew.LoadBoard(str(pcb_path))
    apply_rules(board)
    with tempfile.TemporaryDirectory() as d:
        dsn, ses = Path(d) / "board.dsn", Path(d) / "board.ses"
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError("DSN export failed")
        subprocess.run(["java", "-jar", str(jar)] + flags(dsn, ses), check=True, cwd=d)
        if not ses.exists():
            raise RuntimeError("Freerouting produced no SES file")
        if not pcbnew.ImportSpecctraSES(board, str(ses)):
            raise RuntimeError("SES import failed")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    _save_board(board, pcb_path)


def stitch_ground(pcb_path, pitch=10.0, margin=0.2, avoid=()):
    """Add GND vias, sized from GND's own net class, on a grid wherever both GND
    zones are filled in a ring around the candidate point (not just the centre).

    avoid: (x0, y0, x1, y1) rectangles in board mm (top-left origin, as BoardBuilder)
    where no via is placed -- e.g. silkscreen label bands.
    """
    avoid_nm = [(MM(ORIGIN[0] + x0), MM(ORIGIN[1] + y0), MM(ORIGIN[0] + x1), MM(ORIGIN[1] + y1))
                for x0, y0, x1, y1 in avoid]
    board = pcbnew.LoadBoard(str(pcb_path))
    apply_rules(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    net = board.FindNet("GND")
    if net is None:
        _save_board(board, pcb_path)
        return 0

    nc = net.GetNetClassSlow()
    via_dia, via_drill = nc.GetViaDiameter(), nc.GetViaDrill()
    default_clearance = board.GetDesignSettings().m_NetSettings.GetDefaultNetclass().GetClearance()
    probe_r = via_dia / 2 + default_clearance + MM(margin)
    ring = 8

    gnd = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]
    front = [z for z in gnd if z.GetLayer() == pcbnew.F_Cu]
    back = [z for z in gnd if z.GetLayer() == pcbnew.B_Cu]
    box = board.GetBoardEdgesBoundingBox()
    added = 0
    x = box.GetX() + MM(pitch / 2)
    while x < box.GetRight():
        y = box.GetY() + MM(pitch / 2)
        while y < box.GetBottom():
            if any(ax0 <= x <= ax1 and ay0 <= y <= ay1 for ax0, ay0, ax1, ay1 in avoid_nm):
                y += MM(pitch)
                continue
            probes = [pcbnew.VECTOR2I(int(x), int(y))]
            for i in range(ring):
                angle = 2 * math.pi * i / ring
                probes.append(pcbnew.VECTOR2I(int(x + probe_r * math.cos(angle)),
                                               int(y + probe_r * math.sin(angle))))
            if all(any(z.HitTestFilledArea(pcbnew.F_Cu, pt) for z in front) and
                   any(z.HitTestFilledArea(pcbnew.B_Cu, pt) for z in back) for pt in probes):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                via.SetWidth(via_dia)
                via.SetDrill(via_drill)
                via.SetNet(net)
                board.Add(via)
                added += 1
            y += MM(pitch)
        x += MM(pitch)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    _save_board(board, pcb_path)
    return added
