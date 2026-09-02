#pragma once
//
// Buttons — MCP23017 panel input.
//
// Five buttons plus the rough/fine selector and the foot-switch mirror, all on
// one I2C expander sharing the GT911's bus. Costs zero GPIOs, which is what
// makes a physical control panel possible at all on a board whose RGB display
// consumes twenty pins.
//
// Short/long press doubling gives twelve functions from six buttons - the FXBB
// convention (its Set Zero long-press enters setup, Set Speed long-press sets
// the travel ceiling).
//
// STOP is NOT here. It is wired to FluidNC's own feed_hold_pin so it halts
// motion even if this board has crashed. See docs/UART-PROTOCOL.md §7.2.
//
// Polling and debounce are ported from legacy/src/IOExpander.cpp, which was
// sound; the board-ID logic is dropped.

#include <Arduino.h>
#include "config.h"
#include "pins.h"

enum class Btn : uint8_t {
    CycleStart = 0, Router, BitChange, Zero, Preset, COUNT
};

enum class Press : uint8_t { None, Short, Long };

class Buttons {
public:
    bool begin();                 // false if the expander does not answer
    void update();

    bool isPresent() const { return present_; }

    // Consumed on read - one press yields one event.
    Press take(Btn b);

    // Level inputs, not events.
    bool roughSelected() const { return rough_; }
    bool footPressed()   const { return foot_; }

    // The release edge of the foot switch, which is what gives Q39's
    // dead-man behaviour. FluidNC owns the press (macro0_pin, plunges
    // locally with no link latency); this board watches for the release
    // and commands the retract.
    //
    // UNRESOLVED - this mirror exists because a FluidNC macro pin may only
    // fire on assert. See firmware/README.md.
    bool takeFootReleased();

    void setRouterLed(bool on);
    void blinkRouterLed(bool blinking) { ledBlink_ = blinking; }

private:
    uint8_t readPortA_();
    void    writePortB_(uint8_t v);

    bool present_ = false;

    // per-button debounce and press timing
    bool     raw_[(int)Btn::COUNT]     = {false};
    bool     stable_[(int)Btn::COUNT]  = {false};
    uint32_t changedMs_[(int)Btn::COUNT] = {0};
    uint32_t downMs_[(int)Btn::COUNT]  = {0};
    bool     longFired_[(int)Btn::COUNT] = {false};
    Press    pending_[(int)Btn::COUNT] = {Press::None};

    bool rough_ = false;
    bool foot_ = false, footPrev_ = false, footReleased_ = false;

    bool     ledOn_ = false, ledBlink_ = false, ledPhase_ = false;
    uint32_t lastPollMs_ = 0, lastBlinkMs_ = 0;
    uint8_t  portB_ = 0;
};

extern Buttons Panel;
