import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_pins import config_pins, header_constants

YAML = """name: routerLift
uart1:
  txd_pin: gpio.17      # comment
  rxd_pin: gpio.16
axes:
  z:
    motor0:
      limit_neg_pin: gpio.33:pu
      stepstick:
        step_pin: gpio.26
probe:
  pin: gpio.32:low:pu
Relay:
  output_pin: gpio.4
"""

HEADER = """namespace Pins {
constexpr int8_t UART_TX = 18;   // -> FluidNC
constexpr uint8_t MCP_ADDR = 0x20;
}
namespace Expander {
constexpr uint8_t A_ZERO        = 3;
}"""


class CheckPinsTest(unittest.TestCase):
    def test_config_pins_tracks_top_level_section(self):
        pins = config_pins(YAML)
        self.assertEqual(pins[("uart1", "txd_pin")], 17)
        self.assertEqual(pins[("axes", "limit_neg_pin")], 33)
        self.assertEqual(pins[("axes", "step_pin")], 26)
        self.assertEqual(pins[("probe", "pin")], 32)
        self.assertEqual(pins[("Relay", "output_pin")], 4)

    def test_header_constants_decimal_only(self):
        c = header_constants(HEADER)
        self.assertEqual(c["UART_TX"], 18)
        self.assertEqual(c["A_ZERO"], 3)
        self.assertNotIn("MCP_ADDR", c)
