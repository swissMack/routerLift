#include "IOExpander.h"
#include "config.h"
#include <Wire.h>

IOExpander IO;

bool IOExpander::begin() {
    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL);
    Wire.setClock(400000);

    present_ = mcp_.begin_I2C(MCP::I2C_ADDRESS, &Wire);
    if (!present_) return false;

    // Sensor inputs - NPN inductive sensors pull LOW when triggered;
    // use internal pull-ups so they idle HIGH.
    mcp_.pinMode(MCP::PIN_ENDSTOP_BOTTOM, INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_ENDSTOP_TOP,    INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_BRASS_STAMP,    INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_FOOTSWITCH,     INPUT_PULLUP);

    // Board ID inputs (jumpers to GND on the function board)
    mcp_.pinMode(MCP::PIN_BOARD_ID_0, INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_BOARD_ID_1, INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_BOARD_ID_2, INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_BOARD_ID_3, INPUT_PULLUP);

    // Rate switch inputs (3-position, common to GND, one throw per position)
    mcp_.pinMode(MCP::PIN_RATE_X1,   INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_RATE_X10,  INPUT_PULLUP);
    mcp_.pinMode(MCP::PIN_RATE_X100, INPUT_PULLUP);

    return true;
}

// All sensors are active-LOW (NPN sensors short to GND when triggered).
bool IOExpander::readEndstopBottom() {
    return !mcp_.digitalRead(MCP::PIN_ENDSTOP_BOTTOM);
}
bool IOExpander::readEndstopTop() {
    return !mcp_.digitalRead(MCP::PIN_ENDSTOP_TOP);
}
bool IOExpander::readBrassStamp() {
    return !mcp_.digitalRead(MCP::PIN_BRASS_STAMP);
}
bool IOExpander::readFootSwitch() {
    return !mcp_.digitalRead(MCP::PIN_FOOTSWITCH);
}

uint8_t IOExpander::readBoardId() {
    // Inverted because jumpers pull to GND = bit set.
    uint8_t id = 0;
    if (!mcp_.digitalRead(MCP::PIN_BOARD_ID_0)) id |= 0x01;
    if (!mcp_.digitalRead(MCP::PIN_BOARD_ID_1)) id |= 0x02;
    if (!mcp_.digitalRead(MCP::PIN_BOARD_ID_2)) id |= 0x04;
    if (!mcp_.digitalRead(MCP::PIN_BOARD_ID_3)) id |= 0x08;
    return id;
}

uint8_t IOExpander::readRateMultiplier() {
    // Each position pulls one pin LOW. If multiple or none read LOW we treat
    // it as 'unknown' so the caller can fall back to a safe default (x1).
    bool x1   = !mcp_.digitalRead(MCP::PIN_RATE_X1);
    bool x10  = !mcp_.digitalRead(MCP::PIN_RATE_X10);
    bool x100 = !mcp_.digitalRead(MCP::PIN_RATE_X100);
    if (x1   && !x10 && !x100) return 1;
    if (!x1  && x10  && !x100) return 10;
    if (!x1  && !x10 && x100)  return 100;
    return 0;
}
