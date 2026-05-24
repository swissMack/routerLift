#pragma once
#include "config.h"

// At boot, the MCP23017 Port B 4-bit input is read. Jumpers/solder bridges on
// each function board encode a unique ID. The display unit then knows which
// firmware behaviour to load (router lift, dust collection, miter stop, ...).

class FunctionBoard {
public:
    bool        begin();
    BoardId     id() const   { return id_; }
    uint8_t     rawId() const { return rawId_; }
    const char* name() const;
    bool        isSupported() const { return id_ != BoardId::UNKNOWN; }

private:
    BoardId id_    = BoardId::UNKNOWN;
    uint8_t rawId_ = 0;
};

extern FunctionBoard Board;
