"""30-pin ESP32-WROOM-32 devkit (DOIT v1 layout), antenna up, USB down.

Physical fact read from the silkscreen. Verified against the board in hand
(HW-394, CH340C, USB-C) on 2026-09-14. Index 0 is header pin 1 (top).
"""
import re

DEVKIT_LEFT = ["EN", "VP_36", "VN_39", "D34", "D35", "D32", "D33", "D25",
               "D26", "D27", "D14", "D12", "D13", "GND", "VIN"]
DEVKIT_RIGHT = ["D23", "D22", "TX0_1", "RX0_3", "D21", "D19", "D18", "D5",
                "D17", "D16", "D4", "D2", "D15", "GND", "3V3"]


def devkit_gpio(silk):
    m = re.search(r"(?:^D|_)(\d+)$", silk)
    return int(m.group(1)) if m else None
