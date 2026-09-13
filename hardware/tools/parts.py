"""Symbol ids and footprints shared by the builders."""

R = "Device:R"
C = "Device:C"
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOIC14 = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"
FP_SOIC28 = "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm"
FP_DEVKIT_ROW = "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical"
FP_LINK = "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical"
FP_MX125_4 = "Connector_Molex:Molex_PicoBlade_53047-0410_1x04_P1.25mm_Vertical"


def term(n):
    """(symbol, footprint) for an n-way 5.08 mm screw terminal."""
    return ("Connector:Screw_Terminal_01x%02d" % n,
            "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-%d-5.08_1x%02d_P5.08mm_Horizontal"
            % (n, n))
