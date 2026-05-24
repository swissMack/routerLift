#include "Relay.h"
#include "config.h"

Relay RouterRelay;

bool Relay::begin() {
    pinMode(Pins::RELAY, OUTPUT);
    digitalWrite(Pins::RELAY, LOW);   // Default OFF on boot.
    startupDelayMs_ = Safety::RELAY_STARTUP_DELAY_MS;
    return true;
}

void Relay::turnOn() {
    if (on_) return;
    digitalWrite(Pins::RELAY, HIGH);
    onAtMs_ = millis();
    on_ = true;
}

void Relay::turnOff() {
    digitalWrite(Pins::RELAY, LOW);
    on_ = false;
    onAtMs_ = 0;
}

bool Relay::isReady() const {
    if (!on_) return false;
    return (millis() - onAtMs_) >= startupDelayMs_;
}

uint32_t Relay::msSincePowerOn() const {
    if (!on_) return 0;
    return millis() - onAtMs_;
}
