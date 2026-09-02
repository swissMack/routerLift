// routerLift HMI — ESP32-S3 operator panel.
//
// INCREMENT 3: link, handwheel, buttons, display, Z0 validity, named presets.
//
// Enough to pass bench-test steps 1, 2, 4, 5 and the probe half of 7:
//   - the panel renders and touch tracks
//   - the link comes up and status is parsed
//   - one detent moves the axis exactly 0.01 / 0.10 mm
//   - buttons and the rough/fine selector read correctly
//   - a two-touch probe sets Z0, and a failed probe leaves it invalid
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
#include "Zero.h"
#include "Store.h"

static uint32_t lastPrint = 0;
static bool     wasConnected = false;
static bool     wasAlarm = false;

static void onLinkLost() {
    // docs/UART-PROTOCOL.md §7.2. The feed hold may not arrive - that is
    // acceptable and expected. What matters is that we stop originating
    // motion and invalidate the reference.
    Motion.feedHold();
    Handwheel.inhibit(true);
    Z0.invalidate(ZeroLost::LinkLost);
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
    Serial.println("\nrouterLift HMI - increment 3");

    if (!Panel.begin()) {
        // Degraded, not fatal: the wheel, link and touchscreen still work.
        // Mirrors the legacy firmware's "MCP23017 not found" behaviour.
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

    Presets.begin();
    Z0.begin();
    Z0.setPlateMm(Presets.plateMm());
    Serial.printf("[NVS] %u presets, plate %.2f mm\n",
                  Presets.count(), Presets.plateMm());

    Handwheel.begin(Pins::MPG_A, Pins::MPG_B);
    Motion.begin(Serial1, Pins::UART_RX, Pins::UART_TX);

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
    Presets.update();
    Handwheel.setRough(Panel.roughSelected());
    Handwheel.update();
    Z0.update();

    // The wheel must never fight a probe sequence for the axis.
    Handwheel.inhibit(Z0.isBusy() || !Motion.isConnected());

    Screens.setZ0Valid(Z0.isValid());

    // ---- link transitions ----
    const bool connected = Motion.isConnected();
    if (connected != wasConnected) {
        if (connected) onLinkUp(); else onLinkLost();
        wasConnected = connected;
    }

    // ---- alarm transitions (FW-09) ----
    const bool alarm = (Motion.state() == MachineState::Alarm);
    if (alarm && !wasAlarm) {
        Z0.invalidate(ZeroLost::Alarm);
        Screens.showMessage("ALARM - re-home required");
        Serial.println("[ALARM] Z0 invalidated");
    }
    wasAlarm = alarm;

    Panel.setRouterLed(Motion.routerOn());

    // ---- probe progress ----
    static ZeroState lastZs = ZeroState::Idle;
    if (Z0.state() != lastZs) {
        lastZs = Z0.state();
        const char* t = Z0.stateText();
        if (t[0]) Screens.showMessage(t);
        Serial.printf("[ZERO] %s%s%s\n", t,
                      Z0.lastError()[0] ? " - " : "", Z0.lastError());
    }

    // ---- buttons ----
    for (int i = 0; i < (int)Btn::COUNT; i++) {
        const Press p = Panel.take((Btn)i);
        if (p == Press::None) continue;
        Screen.noteActivity();

        static const char* names[] = {
            "CYCLE_START", "ROUTER", "BIT_CHANGE", "ZERO", "PRESET"
        };
        Serial.printf("[BTN] %s %s\n", names[i], p == Press::Long ? "long" : "short");

        switch ((Btn)i) {

        case Btn::Router:
            if (p == Press::Short) {
                if (Motion.routerOn()) Motion.send("M5");
                else                   Motion.send("M3 S1000");
            }
            break;

        case Btn::Zero:
            if (p == Press::Short) {
                if (!Z0.start()) Screens.showMessage(Z0.lastError());
            } else {
                // Long-press: set zero here without probing. Separate path so
                // it can never be mistaken for a measured touch-off.
                Z0.setHereUnprobed();
                Screens.showMessage("ZERO SET (unprobed)");
            }
            break;

        case Btn::BitChange:
            // Increment 4 builds the full state machine. Invalidating Z0 on
            // entry is correct now and safe to do early: every bit differs in
            // length, so a stale Z0 after a tool change is simply wrong (Q22).
            if (p == Press::Short) {
                Z0.invalidate(ZeroLost::BitChange);
                Screens.showMessage("BIT CHANGE - re-probe required");
            }
            break;

        case Btn::Preset: {
            const Preset* ps = Presets.get(Presets.activeSlot());
            if (p == Press::Short) {
                if (!ps) { Screens.showMessage("no preset in slot"); break; }
                if (!Z0.isValid()) {
                    // FW-08: presets lock when Z0 is invalid. A stored depth
                    // means nothing without a trustworthy reference.
                    Screens.showMessage("Z0 invalid - probe first");
                    break;
                }
                Motion.sendf("G90 G21 G1 Z%.3f F%u",
                             ps->depthMm, MotionCfg::PLUNGE_FEED_MM_MIN);
                Handwheel.syncTo(ps->depthMm);
            } else {
                // Long-press saves. Naming happens on the touchscreen; an
                // auto-name keeps the button usable before that screen exists.
                char nm[UiCfg::PRESET_NAME_LEN + 1];
                snprintf(nm, sizeof(nm), "P%u", Presets.activeSlot() + 1);
                Presets.save(Presets.activeSlot(), nm, Motion.positionMm());
                Screens.showMessage("PRESET SAVED");
            }
            break;
        }

        case Btn::CycleStart:
            // Increment 4.
            break;

        default:
            break;
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
        Serial.printf("%-6s Z=%8.3f  F=%4u S=%4u  %s  %s raw=%ld "
                      "jogs=%lu clamp=%lu  Z0=%s(%s)\n",
                      Motion.stateName(), Motion.positionMm(),
                      Motion.feedRate(), Motion.spindle(),
                      connected ? "LINK" : "NOLINK",
                      Handwheel.isRough() ? "ROUGH" : "FINE",
                      (long)Handwheel.rawCount(),
                      (unsigned long)Handwheel.jogsSent(),
                      (unsigned long)Handwheel.jogsClamped(),
                      Z0.isValid() ? "OK" : "INVALID",
                      Z0.isValid() ? "" : Z0.lostReasonText());

        if (Motion.hasError()) {
            Serial.printf("[ERR] %s\n", Motion.lastMessage());
            Motion.clearError();
        }
    }
}
