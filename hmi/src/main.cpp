// routerLift HMI — ESP32-S3 operator panel.
//
// INCREMENT 2: link, handwheel, buttons, and the display.
//
// Enough to pass bench-test steps 1, 2, 4 and 5:
//   - the panel renders and touch tracks
//   - the link comes up and status is parsed
//   - one detent moves the axis exactly 0.01 / 0.10 mm
//   - buttons and the rough/fine selector read correctly
//
// ARCHITECTURE REMINDER (ELE-11): this board has no motion authority. Soft
// limits, hard limits, homing and probing are enforced by FluidNC. Nothing
// here may enforce a limit, and nothing here may be the last line of defence.

#include <Arduino.h>
#include "config.h"
#include "pins.h"
#include "Link.h"
#include "Wheel.h"
#include "Buttons.h"
#include "Display.h"
#include "Ui.h"

static uint32_t lastPrint = 0;
static bool     wasConnected = false;
static bool     z0Valid = false;    // owned here; FluidNC has no concept of it

static void onLinkLost() {
    // docs/UART-PROTOCOL.md §7.2. The feed hold may not arrive - that is
    // acceptable and expected. What matters is that we stop originating
    // motion and invalidate the reference.
    Motion.feedHold();
    Handwheel.inhibit(true);
    z0Valid = false;
    Screens.setZ0Valid(false);
    Screens.showMessage("LINK LOST");
    Serial.println("[LINK] LOST - feed hold sent, Z0 invalidated");
}

static void onLinkUp() {
    Handwheel.syncTo(Motion.positionMm());
    Handwheel.inhibit(false);
    Screens.showMessage("");
    Serial.println("[LINK] up");
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("\nrouterLift HMI - increment 1 (headless)");

    if (!Panel.begin()) {
        // Degraded, not fatal: the wheel and link still work, so the machine
        // is usable from the touchscreen once that exists. Mirrors the legacy
        // firmware's "MCP23017 not found - degraded mode" behaviour.
        Serial.println("[MCP] not found at 0x20 - panel buttons unavailable");
    } else {
        Serial.println("[MCP] ok");
    }

    if (!Screen.begin()) {
        Serial.println("[LVGL] display unavailable - continuing headless");
    } else {
        Screens.begin();
        Serial.println("[LVGL] ok");
    }

    Handwheel.begin(Pins::MPG_A, Pins::MPG_B);
    Motion.begin(Serial1, Pins::UART_RX, Pins::UART_TX);

    // Start from a known state, then read settings back to prove the link.
    Motion.softReset();
    delay(100);
    Motion.send("$$");

    Serial.println("Waiting for FluidNC status reports...");
}

void loop() {
    Motion.update();
    Screen.update();
    Screens.update();
    Panel.update();
    Handwheel.setRough(Panel.roughSelected());
    Handwheel.update();

    // ---- link state transitions ----
    const bool connected = Motion.isConnected();
    if (connected != wasConnected) {
        if (connected) onLinkUp(); else onLinkLost();
        wasConnected = connected;
    }

    // ---- router indicator ----
    Panel.setRouterLed(Motion.routerOn());

    // ---- probe results ----
    float pz; bool triggered;
    if (Motion.takeProbeResult(pz, triggered)) {
        if (triggered) {
            Serial.printf("[PROBE] contact at %.3f mm\n", pz);
        } else {
            // ':0' means no contact was made. A failed touch-off must leave
            // Z0 invalid - never assume the surface was where we expected.
            z0Valid = false;
            Screens.setZ0Valid(false);
            Screens.showMessage("PROBE: NO CONTACT");
            Serial.println("[PROBE] NO CONTACT - touch-off failed, Z0 invalid");
        }
    }

    // ---- buttons (increment 1: log only, no cycle logic yet) ----
    for (int i = 0; i < (int)Btn::COUNT; i++) {
        const Press p = Panel.take((Btn)i);
        if (p == Press::None) continue;
        static const char* names[] = {
            "CYCLE_START", "ROUTER", "BIT_CHANGE", "ZERO", "PRESET"
        };
        Serial.printf("[BTN] %s %s\n", names[i],
                      p == Press::Long ? "long" : "short");

        // Only the two that are safe without cycle state are wired up yet.
        if ((Btn)i == Btn::Router && p == Press::Short) {
            if (Motion.routerOn()) Motion.send("M5");
            else                   Motion.send("M3 S1000");
        }
    }

    // Foot switch release - the mirror that gives dead-man behaviour.
    // FluidNC owns the press via macro0_pin; we only handle the retract.
    if (Panel.takeFootReleased()) {
        Serial.println("[FOOT] released - retract would be commanded here");
    }

    // ---- periodic diagnostics ----
    if (millis() - lastPrint >= 1000) {
        lastPrint = millis();
        Serial.printf("%-6s Z=%8.3f  F=%4u S=%4u  %s  wheel=%s raw=%ld "
                      "jogs=%lu clamped=%lu  Z0=%s\n",
                      Motion.stateName(), Motion.positionMm(),
                      Motion.feedRate(), Motion.spindle(),
                      connected ? "LINK" : "NOLINK",
                      Handwheel.isRough() ? "ROUGH" : "FINE",
                      (long)Handwheel.rawCount(),
                      (unsigned long)Handwheel.jogsSent(),
                      (unsigned long)Handwheel.jogsClamped(),
                      z0Valid ? "OK" : "INVALID");

        if (Motion.hasError()) {
            Serial.printf("[ERR] %s\n", Motion.lastMessage());
            Motion.clearError();
        }
    }
}
