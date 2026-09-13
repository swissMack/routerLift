"""30-pin ESP32-WROOM-32 devkit (DOIT v1 layout), antenna up, USB down.

Physical fact read from the silkscreen - VERIFY against the board in hand
before ordering a PCB. Index 0 is header pin 1 (top).
"""
import re

DEVKIT_LEFT = ["EN", "VP_36", "VN_39", "D34", "D35", "D32", "D33", "D25",
               "D26", "D27", "D14", "D12", "GND", "D13", "VIN"]
DEVKIT_RIGHT = ["D23", "D22", "TX0_1", "RX0_3", "D21", "D19", "D18", "D5",
                "TX2_17", "RX2_16", "D4", "D2", "D15", "GND", "3V3"]


def devkit_gpio(silk):
    m = re.search(r"(?:^D|_)(\d+)$", silk)
    return int(m.group(1)) if m else None
