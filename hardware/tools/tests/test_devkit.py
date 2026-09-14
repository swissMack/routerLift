import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devkit import DEVKIT_LEFT, DEVKIT_RIGHT, devkit_gpio


class DevkitTest(unittest.TestCase):
    def test_rows_are_fifteen_pins(self):
        self.assertEqual(len(DEVKIT_LEFT), 15)
        self.assertEqual(len(DEVKIT_RIGHT), 15)

    def test_gpio_from_silkscreen(self):
        self.assertEqual(devkit_gpio("D26"), 26)
        self.assertEqual(devkit_gpio("D17"), 17)
        self.assertEqual(devkit_gpio("TX0_1"), 1)
        self.assertEqual(devkit_gpio("VP_36"), 36)
        self.assertIsNone(devkit_gpio("3V3"))
        self.assertIsNone(devkit_gpio("GND"))

    def test_every_firmware_gpio_is_on_a_header(self):
        gpios = {devkit_gpio(s) for s in DEVKIT_LEFT + DEVKIT_RIGHT}
        self.assertTrue({26, 27, 14, 4, 33, 25, 32, 13, 21, 17, 16, 35, 34} <= gpios)
