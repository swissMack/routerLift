"""Print a stock symbol's pins: python3 list_pins.py Diode:BAT54S [unit]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kisch import Library

lib_id = sys.argv[1]
unit = int(sys.argv[2]) if len(sys.argv) > 2 else 1
for p in Library().pins(lib_id, unit).values():
    print("%4s  %-12s %-14s at (%g, %g) %g" % (p.number, p.name, p.etype, p.x, p.y, p.angle))
