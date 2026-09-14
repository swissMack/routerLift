"""Read a KiCad (kicadsexpr) netlist: components and which net each pad is on."""
import collections
import re
import subprocess
import tempfile
from pathlib import Path

from kisch import find, findall, parse

Component = collections.namedtuple("Component", "ref value footprint dnp")


def _natural(ref):
    m = re.match(r"([A-Za-z#]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def read_netlist(text):
    tree = parse(text)
    comps = collections.OrderedDict()
    for c in findall(find(tree, "components"), "comp"):
        fp = find(c, "footprint")
        dnp = any(str(find(p, "name")[1]) == "dnp" for p in findall(c, "property"))
        ref = str(find(c, "ref")[1])
        comps[ref] = Component(ref, str(find(c, "value")[1]), str(fp[1]) if fp else "", dnp)
    pads = {}
    for net in findall(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1])
        for node in findall(net, "node"):
            pads[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return comps, pads


def export_netlist(sch_path, kicad_cli):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "board.net"
        subprocess.run([kicad_cli, "sch", "export", "netlist", "--format", "kicadsexpr",
                        "-o", str(out), str(sch_path)], check=True, capture_output=True)
        return out.read_text(encoding="utf-8")


def refs_on_net(pads, net, prefix=""):
    return sorted({ref for (ref, _), n in pads.items() if n == net and ref.startswith(prefix)},
                  key=_natural)


def pads_of(pads, ref):
    return {pad: net for (r, pad), net in pads.items() if r == ref}
