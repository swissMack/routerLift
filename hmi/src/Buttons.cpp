#include "Buttons.h"
#include <Wire.h>

Buttons Panel;

// MCP23017 registers (IOCON.BANK = 0, the power-on default)
static constexpr uint8_t REG_IODIRA = 0x00;
static constexpr uint8_t REG_IODIRB = 0x01;
static constexpr uint8_t REG_GPPUA  = 0x0C;
static constexpr uint8_t REG_GPIOA  = 0x12;
static constexpr uint8_t REG_OLATB  = 0x15;

static bool wr(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(Pins::MCP_ADDR);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

static bool rd(uint8_t reg, uint8_t& out) {
    Wire.beginTransmission(Pins::MCP_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom((int)Pins::MCP_ADDR, 1) != 1) return false;
    out = Wire.read();
    return true;
}

bool Buttons::begin() {
    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL, 400000);

    // Port A all inputs with pull-ups; buttons are NO to GND so pressed = LOW.
    // Port B all outputs for indicators.
    present_  = wr(REG_IODIRA, 0xFF);
    present_ &= wr(REG_GPPUA,  0xFF);
    present_ &= wr(REG_IODIRB, 0x00);
    present_ &= wr(REG_OLATB,  0x00);

    portB_ = 0;
    lastPollMs_ = millis();
    return present_;
}

uint8_t Buttons::readPortA_() {
    uint8_t v = 0xFF;
    if (!rd(REG_GPIOA, v)) { present_ = false; return 0xFF; }
    return v;
}

void Buttons::writePortB_(uint8_t v) {
    if (present_) wr(REG_OLATB, v);
}

void Buttons::update() {
    const uint32_t now = millis();

    // Router LED blink, independent of the poll rate so warming is visible.
    if (ledBlink_ && (now - lastBlinkMs_) >= 400) {
        lastBlinkMs_ = now;
        ledPhase_ = !ledPhase_;
        uint8_t b = portB_;
        if (ledPhase_) b |=  (1 << Expander::B_ROUTER_LED);
        else           b &= ~(1 << Expander::B_ROUTER_LED);
        portB_ = b;
        writePortB_(portB_);
    }

    if ((now - lastPollMs_) < ButtonCfg::POLL_MS) return;
    lastPollMs_ = now;
    if (!present_) return;

    const uint8_t a = readPortA_();
    static const uint8_t bit[(int)Btn::COUNT] = {
        Expander::A_CYCLE_START, Expander::A_ROUTER, Expander::A_BIT_CHANGE,
        Expander::A_ZERO,        Expander::A_PRESET
    };

    for (int i = 0; i < (int)Btn::COUNT; i++) {
        const bool down = ((a >> bit[i]) & 1) == 0;   // active LOW

        if (down != raw_[i]) { raw_[i] = down; changedMs_[i] = now; }

        if ((now - changedMs_[i]) >= ButtonCfg::DEBOUNCE_MS && stable_[i] != raw_[i]) {
            stable_[i] = raw_[i];
            if (stable_[i]) {
                downMs_[i] = now;
                longFired_[i] = false;
            } else if (!longFired_[i]) {
                pending_[i] = Press::Short;    // released before long threshold
            }
        }

        // Long press fires while still held, so the operator gets feedback at
        // the moment the threshold passes rather than on release.
        if (stable_[i] && !longFired_[i] &&
            (now - downMs_[i]) >= ButtonCfg::LONG_PRESS_MS) {
            longFired_[i] = true;
            pending_[i] = Press::Long;
        }
    }

    rough_ = ((a >> Expander::A_ROUGH_FINE) & 1) == 0;

    footPrev_ = foot_;
    foot_ = ((a >> Expander::A_FOOT_MIRROR) & 1) == 0;
    if (footPrev_ && !foot_) footReleased_ = true;
}

Press Buttons::take(Btn b) {
    const int i = (int)b;
    if (i < 0 || i >= (int)Btn::COUNT) return Press::None;
    Press p = pending_[i];
    pending_[i] = Press::None;
    return p;
}

bool Buttons::takeFootReleased() {
    bool r = footReleased_;
    footReleased_ = false;
    return r;
}

void Buttons::setRouterLed(bool on) {
    ledOn_ = on;
    if (!ledBlink_) {
        if (on) portB_ |=  (1 << Expander::B_ROUTER_LED);
        else    portB_ &= ~(1 << Expander::B_ROUTER_LED);
        writePortB_(portB_);
    }
}
