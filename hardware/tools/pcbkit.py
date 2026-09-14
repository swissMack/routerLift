"""Build KiCad boards with pcbnew. Run under KiCad's bundled python.

Coordinates are millimetres from the board's top-left corner, y down.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pcbnew

FP_DIR = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
ORIGIN = (100.0, 100.0)  # where the board sits on the KiCad page
NET_CLASS_POWER = ("+5V", "+3V3", "GND")
MM = pcbnew.FromMM


def _load_fp(lib_id):
    lib, name = lib_id.split(":", 1)
    fp = pcbnew.FootprintLoad(str(FP_DIR / (lib + ".pretty")), name)
    if fp is None:
        raise KeyError("footprint not found: " + lib_id)
    return fp


class BoardBuilder:
    def __init__(self, name, width, height):
        self.name, self.w, self.h = name, float(width), float(height)
        self.board = pcbnew.BOARD()
        self.nets, self.fps = {}, {}
        self._holes = 0
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
        return fp

    def _outline_zone(self, zone, x0, y0, x1, y1):
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            pt = self.p(x, y)
            outline.Append(pt.x, pt.y)

    def rule_area(self, x0, y0, x1, y1):
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(True)
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
        # pcbnew.SaveBoard() also (re)writes the sibling .kicad_pro with its own
        # default project settings, clobbering anything write_project_rules()
        # already put there. Preserve it across the save.
        path = Path(path)
        pro = path.with_suffix(".kicad_pro")
        prior = pro.read_text() if pro.exists() else None
        pcbnew.SaveBoard(str(path), self.board)
        if prior is not None:
            pro.write_text(prior)


def write_project_rules(pro_path):
    """Merge JLCPCB rules and net classes into the project file the schematic already uses."""
    pro_path = Path(pro_path)
    pro = json.loads(pro_path.read_text()) if pro_path.exists() else {}
    board = pro.setdefault("board", {})
    ds = board.setdefault("design_settings", {})
    ds["rules"] = {
        "min_clearance": 0.25, "min_track_width": 0.25, "min_via_diameter": 0.6,
        "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.5,
        "min_hole_to_hole": 0.25, "min_text_height": 1.0, "min_text_thickness": 0.15,
    }
    ds["track_widths"] = [0.0, 0.25, 0.6]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}]
    pro["net_settings"] = {
        "classes": [
            {"name": "Default", "clearance": 0.25, "track_width": 0.25,
             "via_diameter": 0.6, "via_drill": 0.3},
            {"name": "Power", "clearance": 0.25, "track_width": 0.6,
             "via_diameter": 0.6, "via_drill": 0.3},
        ],
        "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in NET_CLASS_POWER],
        "meta": {"version": 3},
    }
    pro.setdefault("meta", {"filename": pro_path.name, "version": 1})
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")


def autoroute(pcb_path, jar, flags):
    """Export DSN, run Freerouting, import SES, refill zones, save in place.

    flags: callable(dsn, ses) -> list of Freerouting CLI args (from Task 1's --help record).
    """
    board = pcbnew.LoadBoard(str(pcb_path))
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
    pcbnew.SaveBoard(str(pcb_path), board)


def stitch_ground(pcb_path, pitch=10.0, margin=1.0):
    """Add GND vias on a grid wherever both GND zones are filled around the point."""
    board = pcbnew.LoadBoard(str(pcb_path))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gnd = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]
    front = [z for z in gnd if z.GetLayer() == pcbnew.F_Cu]
    back = [z for z in gnd if z.GetLayer() == pcbnew.B_Cu]
    box = board.GetBoardEdgesBoundingBox()
    net = board.FindNet("GND")
    added = 0
    x = box.GetX() + MM(pitch / 2)
    while x < box.GetRight():
        y = box.GetY() + MM(pitch / 2)
        while y < box.GetBottom():
            probes = [pcbnew.VECTOR2I(x + dx, y + dy) for dx, dy in
                      ((0, 0), (MM(margin), 0), (-MM(margin), 0), (0, MM(margin)), (0, -MM(margin)))]
            if all(any(z.HitTestFilledArea(pcbnew.F_Cu, pt) for z in front) and
                   any(z.HitTestFilledArea(pcbnew.B_Cu, pt) for z in back) for pt in probes):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(x, y))
                via.SetWidth(MM(0.6))
                via.SetDrill(MM(0.3))
                via.SetNet(net)
                board.Add(via)
                added += 1
            y += MM(pitch)
        x += MM(pitch)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(pcb_path), board)
    return added
