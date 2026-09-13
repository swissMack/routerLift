"""Regenerate the KiCad projects: python3 hardware/tools/gen_schematics.py [project ...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kisch import Library
import motion_carrier
import panel_carrier

HW = Path(__file__).resolve().parents[1]
BUILDERS = {"motion-carrier": motion_carrier.build, "panel-carrier": panel_carrier.build}


def main(argv):
    targets = argv[1:] or list(BUILDERS)
    for name in targets:
        BUILDERS[name](Library(), HW / name)
        print("wrote", HW / name)


if __name__ == "__main__":
    main(sys.argv)
