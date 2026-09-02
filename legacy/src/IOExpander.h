#pragma once
#include <Adafruit_MCP23X17.h>

// Thin wrapper around the MCP23017 so the rest of the code is decoupled
// from the underlying library and pin layout.
class IOExpander {
public:
    bool begin();
    bool isPresent() const { return present_; }

    // Inputs (debounce handled in caller modules)
    bool readEndstopBottom();
    bool readEndstopTop();
    bool readBrassStamp();
    bool readFootSwitch();

    // 4-bit board identifier from Port B
    uint8_t readBoardId();

    // 3-position rate switch (x1/x10/x100). Returns 1, 10, or 100.
    // 0 = no position detected (switch between detents / malfunction).
    uint8_t readRateMultiplier();

    // Raw access (for debugging / extension)
    Adafruit_MCP23X17& raw() { return mcp_; }

private:
    Adafruit_MCP23X17 mcp_;
    bool present_ = false;
};

extern IOExpander IO;
