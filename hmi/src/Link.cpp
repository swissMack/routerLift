#include "Link.h"
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>

Link Motion;

void Link::begin(HardwareSerial& port, int8_t rxPin, int8_t txPin) {
    port_ = &port;
    port_->begin(LinkCfg::BAUD, SERIAL_8N1, rxPin, txPin);
    rxLen_ = 0;
    qHead_ = qTail_ = qCount_ = 0;
    inFlight_ = false;
    lastReportMs_ = 0;
    everConnected_ = false;
}

// ---------------------------------------------------------------- outbound

bool Link::send(const char* line) {
    if (!port_ || qCount_ >= LinkCfg::TX_QUEUE_DEPTH) return false;
    strncpy(queue_[qHead_], line, LinkCfg::LINE_BUFFER - 1);
    queue_[qHead_][LinkCfg::LINE_BUFFER - 1] = '\0';
    qHead_ = (qHead_ + 1) % LinkCfg::TX_QUEUE_DEPTH;
    qCount_++;
    pump_();
    return true;
}

bool Link::sendf(const char* fmt, ...) {
    char buf[LinkCfg::LINE_BUFFER];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    return send(buf);
}

// Realtime bytes bypass the queue and the in-flight window entirely. This is
// the whole point of them: a feed hold must not sit behind a pending 'ok'.
void Link::realtime(uint8_t b) {
    if (port_) port_->write(b);
}

void Link::pump_() {
    if (!port_ || inFlight_ || qCount_ == 0) return;
    port_->print(queue_[qTail_]);
    port_->print('\n');
    qTail_ = (qTail_ + 1) % LinkCfg::TX_QUEUE_DEPTH;
    qCount_--;
    inFlight_ = true;
    sentAtMs_ = millis();
}

// ----------------------------------------------------------------- inbound

void Link::update() {
    if (!port_) return;

    while (port_->available()) {
        char c = (char)port_->read();
        if (c == '\n' || c == '\r') {
            if (rxLen_ > 0) {
                rx_[rxLen_] = '\0';
                handleLine_(rx_);
                rxLen_ = 0;
            }
        } else if (rxLen_ < LinkCfg::LINE_BUFFER - 1) {
            rx_[rxLen_++] = c;
        } else {
            rxLen_ = 0;   // overlong line, resynchronise
        }
    }

    // A command that never gets acknowledged would wedge the queue forever.
    if (inFlight_ && (millis() - sentAtMs_) > LinkCfg::ACK_TIMEOUT_MS) {
        inFlight_ = false;
        errorCode_ = 255;
        strncpy(message_, "no response from controller", sizeof(message_) - 1);
    }

    pump_();
}

void Link::handleLine_(char* line) {
    if (line[0] == '<') {                       // status report
        char* end = strchr(line, '>');
        if (end) *end = '\0';
        parseStatus_(line + 1);
        lastReportMs_ = millis();
        everConnected_ = true;
        return;
    }

    if (strncmp(line, "ok", 2) == 0) {
        inFlight_ = false;
        return;
    }

    if (strncmp(line, "error:", 6) == 0) {
        errorCode_ = (uint8_t)atoi(line + 6);
        inFlight_ = false;
        snprintf(message_, sizeof(message_), "error %u", errorCode_);
        return;
    }

    if (strncmp(line, "ALARM:", 6) == 0) {
        alarmCode_ = (uint8_t)atoi(line + 6);
        inFlight_ = false;
        snprintf(message_, sizeof(message_), "alarm %u", alarmCode_);
        return;
    }

    if (line[0] == '[') {
        if (strncmp(line + 1, "PRB:", 4) == 0) parseProbe_(line + 5);
        else if (strncmp(line + 1, "MSG:", 4) == 0)
            strncpy(message_, line + 5, sizeof(message_) - 1);
        return;
    }
    // Banner and $$ settings lines are ignored here; the UI reads them
    // separately during startup if it wants the version string.
}

// Body looks like:  Idle|MPos:0.000,0.000,12.345|FS:0,0
void Link::parseStatus_(char* body) {
    char* save = nullptr;
    char* tok = strtok_r(body, "|", &save);
    if (!tok) return;

    if      (!strncmp(tok, "Idle",  4)) state_ = MachineState::Idle;
    else if (!strncmp(tok, "Run",   3)) state_ = MachineState::Run;
    else if (!strncmp(tok, "Jog",   3)) state_ = MachineState::Jog;
    else if (!strncmp(tok, "Hold",  4)) state_ = MachineState::Hold;
    else if (!strncmp(tok, "Home",  4)) state_ = MachineState::Home;
    else if (!strncmp(tok, "Alarm", 5)) state_ = MachineState::Alarm;
    else if (!strncmp(tok, "Door",  4)) state_ = MachineState::Door;
    else if (!strncmp(tok, "Check", 5)) state_ = MachineState::Check;
    else if (!strncmp(tok, "Sleep", 5)) state_ = MachineState::Sleep;
    else                                state_ = MachineState::Unknown;

    while ((tok = strtok_r(nullptr, "|", &save)) != nullptr) {
        if (!strncmp(tok, "MPos:", 5)) {
            // X,Y,Z - we are a single-axis machine but FluidNC still reports
            // three, so take the third field.
            char* p = tok + 5;
            char* c1 = strchr(p, ',');
            if (!c1) continue;
            char* c2 = strchr(c1 + 1, ',');
            if (!c2) continue;
            mposZ_ = atof(c2 + 1);
        } else if (!strncmp(tok, "FS:", 3)) {
            char* p = tok + 3;
            feed_ = (uint16_t)atoi(p);
            char* c = strchr(p, ',');
            spindle_ = c ? (uint16_t)atoi(c + 1) : 0;
        } else if (!strncmp(tok, "F:", 2)) {
            feed_ = (uint16_t)atoi(tok + 2);
        }
    }
}

// Body looks like:  0.000,0.000,-12.345:1
// The trailing flag is what matters. ':0' means the probe never made contact,
// which is a FAILED touch-off - Z0 must stay invalid.
void Link::parseProbe_(char* body) {
    char* colon = strrchr(body, ':');
    probeTriggered_ = colon && colon[1] == '1';
    if (colon) *colon = '\0';

    char* c1 = strchr(body, ',');
    if (c1) {
        char* c2 = strchr(c1 + 1, ',');
        if (c2) probeZ_ = atof(c2 + 1);
    }
    probePending_ = true;
}

bool Link::takeProbeResult(float& zOut, bool& triggered) {
    if (!probePending_) return false;
    zOut = probeZ_;
    triggered = probeTriggered_;
    probePending_ = false;
    return true;
}

// ------------------------------------------------------------------ health

bool Link::isConnected() const {
    if (!everConnected_) return false;
    return (millis() - lastReportMs_) < LinkCfg::TIMEOUT_MS;
}

const char* Link::stateName() const {
    switch (state_) {
        case MachineState::Idle:  return "IDLE";
        case MachineState::Run:   return "RUN";
        case MachineState::Jog:   return "JOG";
        case MachineState::Hold:  return "HOLD";
        case MachineState::Home:  return "HOMING";
        case MachineState::Alarm: return "ALARM";
        case MachineState::Door:  return "DOOR";
        case MachineState::Check: return "CHECK";
        case MachineState::Sleep: return "SLEEP";
        default:                  return "----";
    }
}
