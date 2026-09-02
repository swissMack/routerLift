#include "FunctionBoard.h"
#include "IOExpander.h"

FunctionBoard Board;

bool FunctionBoard::begin() {
    rawId_ = IO.readBoardId();
    switch (rawId_) {
        case 1: id_ = BoardId::ROUTER_LIFT;     break;
        case 2: id_ = BoardId::DUST_COLLECTION; break;
        case 3: id_ = BoardId::MITER_SAW_STOP;  break;
        default: id_ = BoardId::UNKNOWN;        break;
    }
    return id_ != BoardId::UNKNOWN;
}

const char* FunctionBoard::name() const {
    switch (id_) {
        case BoardId::ROUTER_LIFT:     return "Router Lift";
        case BoardId::DUST_COLLECTION: return "Dust Collection";
        case BoardId::MITER_SAW_STOP:  return "Miter Saw Stop";
        default:                       return "Unknown";
    }
}
