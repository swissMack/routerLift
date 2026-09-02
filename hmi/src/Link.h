#pragma once
//
// Link — GRBL sender. The single chokepoint for everything this board says to
// the motion controller.
//
// Nothing else in hmi/ may write to the UART. That is what makes the command
// vocabulary in docs/UART-PROTOCOL.md §4 exhaustive rather than aspirational.
//
// Two traffic classes, deliberately different:
//   - Line commands are queued and acknowledged. One in flight at a time.
//   - Realtime bytes bypass the queue entirely and are written immediately,
//     because a feed hold must never wait behind a pending 'ok'.

#include <Arduino.h>
#include "config.h"

enum class MachineState : uint8_t {
    Unknown, Idle, Run, Jog, Hold, Home, Alarm, Door, Check, Sleep
};

class Link {
public:
    void begin(HardwareSerial& port, int8_t rxPin, int8_t txPin);
    void update();

    // ---- outbound -------------------------------------------------------
    // Queued, acknowledged. Returns false if the queue is full.
    bool send(const char* line);
    bool sendf(const char* fmt, ...);

    // Immediate, unacknowledged, bypasses the queue.
    void realtime(uint8_t b);
    void statusQuery()  { realtime('?');  }
    void feedHold()     { realtime('!');  }
    void resume()       { realtime('~');  }
    void softReset()    { realtime(0x18); }
    void jogCancel()    { realtime(0x85); }

    // ---- reported state -------------------------------------------------
    MachineState state()      const { return state_; }
    const char*  stateName()  const;
    float        positionMm() const { return mposZ_; }
    uint16_t     feedRate()   const { return feed_; }
    uint16_t     spindle()    const { return spindle_; }
    bool         routerOn()   const { return spindle_ > 0; }

    // ---- link health ----------------------------------------------------
    // False once no status report has arrived for LinkCfg::TIMEOUT_MS.
    bool     isConnected() const;
    uint32_t msSinceReport() const { return millis() - lastReportMs_; }

    // ---- probe ----------------------------------------------------------
    // A probe report clears on read. triggered==false means the probe did NOT
    // make contact, which is a FAILED touch-off - Z0 must stay invalid.
    bool  takeProbeResult(float& zOut, bool& triggered);

    // ---- errors ---------------------------------------------------------
    bool        hasError() const { return errorCode_ != 0; }
    uint8_t     errorCode() const { return errorCode_; }
    uint8_t     alarmCode() const { return alarmCode_; }
    void        clearError() { errorCode_ = 0; alarmCode_ = 0; }
    const char* lastMessage() const { return message_; }

    bool  idleAndSynced() const { return inFlight_ == false && qCount_ == 0; }

private:
    void handleLine_(char* line);
    void parseStatus_(char* body);
    void parseProbe_(char* body);
    void pump_();

    HardwareSerial* port_ = nullptr;

    char     rx_[LinkCfg::LINE_BUFFER];
    uint16_t rxLen_ = 0;

    char     queue_[LinkCfg::TX_QUEUE_DEPTH][LinkCfg::LINE_BUFFER];
    uint8_t  qHead_ = 0, qTail_ = 0, qCount_ = 0;
    bool     inFlight_ = false;
    uint32_t sentAtMs_ = 0;

    MachineState state_ = MachineState::Unknown;
    float    mposZ_   = 0.0f;
    uint16_t feed_    = 0;
    uint16_t spindle_ = 0;

    uint32_t lastReportMs_ = 0;
    bool     everConnected_ = false;

    float probeZ_ = 0.0f;
    bool  probeTriggered_ = false;
    bool  probePending_ = false;

    uint8_t errorCode_ = 0;
    uint8_t alarmCode_ = 0;
    char    message_[64] = {0};
};

extern Link Motion;
