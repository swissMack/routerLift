"""Generate, route and check a carrier board.

$KPY hardware/tools/gen_pcb.py motion-carrier [--no-route]

Exit status is non-zero if DRC reports violations or warnings (--severity-all) or unconnected
items, or if the pinned Freerouting jar is missing; the exports still run after a DRC failure
so the placement can be inspected (expected before routing).
"""
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcbkit
import pcb_motion
import pcb_panel
from pcb_netlist import export_netlist, read_netlist

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
HW = Path(__file__).resolve().parents[1]
BOARDS = {"motion-carrier": pcb_motion, "panel-carrier": pcb_panel}
FAB_LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"
MAX_PASSES = "30"


def freerouting_flags(dsn, ses):
    return ["-de", str(dsn), "-do", str(ses), "-mp", MAX_PASSES, "--gui.enabled=false"]


def cli(*args, **kw):
    return subprocess.run([KICAD_CLI] + [str(a) for a in args], **kw)


def main(argv):
    name = argv[1]
    route = "--no-route" not in argv
    outdir = HW / name
    pcb = outdir / (name + ".kicad_pcb")
    comps, pads = read_netlist(export_netlist(outdir / (name + ".kicad_sch"), KICAD_CLI))
    builder = BOARDS[name].build(comps, pads)
    pcbkit.apply_rules(builder.board)
    builder.save(pcb)
    if route:
        try:
            jar = pcbkit.freerouting_jar()
        except (FileNotFoundError, RuntimeError) as e:
            print("ERROR:", e)
            return 2
        pcbkit.autoroute(pcb, jar, freerouting_flags)
        print("stitching vias:", pcbkit.stitch_ground(pcb, avoid=builder.stitch_avoid))
    drc = cli("pcb", "drc", "--schematic-parity", "--severity-all", "--exit-code-violations",
              "--refill-zones", "-o", outdir / (name + "-drc.rpt"), pcb)
    gerbers = outdir / "fab" / "gerbers"
    gerbers.mkdir(parents=True, exist_ok=True)
    for old in gerbers.iterdir():
        old.unlink()
    cli("pcb", "export", "gerbers", "--layers", FAB_LAYERS, "-o", str(gerbers) + "/", pcb, check=True)
    cli("pcb", "export", "drill", "--format", "excellon", "-o", str(gerbers) + "/", pcb, check=True)
    with zipfile.ZipFile(outdir / "fab" / (name + "-jlcpcb.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerbers.iterdir()):
            z.write(f, f.name)
    cli("pcb", "export", "pdf", "--mode-single", "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts",
        "-o", outdir / (name + "-pcb.pdf"), pcb, check=True)
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "--quality", "high", "-w", "2400", "-h", "1600",
            "-o", outdir / ("%s-%s.png" % (name, side)), pcb, check=True)
    if drc.returncode != 0:
        print("DRC FAILED (exit %d): see %s" % (drc.returncode, outdir / (name + "-drc.rpt")))
        return 1
    print("ok", pcb)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
