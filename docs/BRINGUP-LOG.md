# Bench bring-up log

Where the hardware actually stands, session by session. Newest first. The design docs say what
the machine *should* be; this file says what has been *proven on the bench*.

---

## 2026-09-13 (later) — Step B: UART link ✅ passed

Supplied P4 lead wired as planned (red GND, blue IO17 → D17, black IO18 → D16, yellow
insulated), D33/D25 jumpered to GND.

| Check | Result |
| --- | --- |
| Link comes up | ✅ screen shows **LINK**, Z 0.00 mm, message "ALARM – re-home required"; log `[LINK] up`, `ALARM Z= 0.000 … LINK … Z0=INVALID(alarm)` |
| Link loss | ✅ pressing FluidNC **EN** → immediate `[LINK] LOST - feed hold sent, Z0 invalidated` |
| Recovery | ✅ link returns on its own; **Z0 stays INVALID(link lost)** until re-probed, as FW-09 requires |

**Bug found and fixed:** the HMI never polled for status. `LinkCfg::POLL_MS` existed but was
unused, and FluidNC's `report_interval_ms` only reports *on change* — so an idle machine sitting
in Alarm sends nothing and the screen showed NO LINK with correct wiring. `Link::update()` now
sends the `?` realtime byte every 100 ms. This also settles `firmware/README.md` item 2: the
interval setting exists but is not a heartbeat; polling is required.

**FluidNC console without USB:** the FluidNC board was running (linked, web UI up at
`routerlift.local`) but its USB serial port did not appear on the Mac — likely a charge-only
cable. Not needed: FluidNC's **telnet console on port 23** gives the same `?`, `$` commands and
messages over WiFi (`routerlift.local:23`). Queried that way it reported
`<Alarm|MPos:0.000,0.000,0.000|FS:0,0|Pn:Z>`. `$Limits` (exit with `!`, not any key — it
otherwise keeps running) showed the **positive limit, GPIO 25**, active. Reseating did not clear
it; **swapping the D25 and D33 jumper wires did** — status back to `<Alarm|…|FS:0,0>` with no
active inputs. GPIO 25 is fine; the cause was a poor-contact jumper. Bench jumpers are unreliable
for limit inputs; real sensors go through proper terminals.

---

## 2026-09-13 — motion board and screen board, bare

**Paused here for about a week, waiting on the MPG level shifters.**

### Resume checklist (start here next session)

1. **Before wiring the level shifters, check which part arrived.** The design now specifies a
   **74LVC14 powered from 3.3 V** (5 V-tolerant inputs, Schmitt hysteresis, two stages per
   channel = non-inverting, `SIGNALS_INVERTED = false`). The BOM originally said 74HCT14: that
   needs a 5 V supply and drives 5 V into the ESP32-S3. If a 74HCT14 is what arrived, do not
   connect its outputs to the S3.
2. ~~**Step B — join the two boards over UART.**~~ ✅ Passed later the same day — see the entry
   above. Next is the MPG through the shifters on P3 (GPIO 6/7).
3. **Foot-switch edge test — can run now, no pedal needed** (pedal ordered 2026-09-13). Decides
   whether FluidNC's `macro0_pin` fires on release as well as press, i.e. whether the MCP A6
   mirror wire is needed for the dead-man retract (`firmware/README.md`, "the foot switch needs
   both edges"). Nothing can move: FluidNC is in Alarm and the macro only prints.
   1. Over WiFi (`telnet routerlift.local 23`): `$Macro0=$G` — a print-only command.
   2. Touch a jumper **D13 → GND** (= press), hold 2 s, remove (= release). Repeat twice.
   3. Watch the console: `[GC:…]` parser-state output on press only → fires on assert only, keep
      the A6 mirror; output on press **and** release → both edges fire, the mirror can go.
   4. Restore: `$Macro0=` (empty). Record the result here and in `firmware/README.md` item 4.
4. **Push status:** everything below is committed and pushed.

### Motion controller — FluidNC ESP32 ✅ bare-board acceptance passed

| Item | Result |
| --- | --- |
| Board | 30-pin USB-C devkit, ESP32-D0WD-V3 **rev 3.1**, CH340, 4 MB, MAC `d4:8a:fc:a4:a9:f8` |
| Firmware | **FluidNC v4.1.0 (esp32-wifi)**, via installer.fluidnc.com |
| Config | `firmware/config.yaml` parses clean. Fix needed and made: spindle key is `Relay:`, not `relay_spindle:`; no comments or quotes on section-header lines |
| Verified | Z axis 0–65 mm, step 26 / dir 27 / disable 14, limits 33/25, STOP 21, foot 13, probe 32, relay 4, UART1 17/16 @ 115200 with 100 ms reports |
| Limits | Unwired → `ALARM: Hard Limit` + `Pn:Z` (correct, NC wiring). D33 + D25 jumpered to GND → clears, boot ends at `ALARM:14` Unhomed (correct, `must_home`) |
| Network | Joins home WiFi as `routerlift.local` / **192.168.1.82**, falls back to AP `FluidNC` (default password `12345678` — change before commissioning, or `$WiFi/Mode=Off`) |

Full detail and flashing steps: `firmware/README.md`.

### Screen board — ✅ display and touch working, ⏸ not yet linked

**The board is a Guition JC4827W543C, not the ESP32-4827S043 that Rev H recorded.** The Rev G
spec had it right. Firmware built for the RGB-parallel Sunton board booted cleanly and showed
nothing. Identified from strings in the factory demo (`guition.com`, `Arduino_ESP32QSPI`) and
the board silkscreen. Docs corrected in commit `e676627`.

| Item | Result |
| --- | --- |
| Module | sparkleIoT XH-S3E **N4R8** — ESP32-S3 rev 0.2, 4 MB flash, **8 MB octal PSRAM**, MAC `a4:cb:8f:ec:16:7c` |
| USB | Native S3 USB → `/dev/cu.usbmodem*`. Upload auto-resets; download mode (hold BOOT, tap RST) only needed if the app has hung |
| Factory demo | Backed up in full: `~/Documents/routerLift-firmware-backups/screen-original-dashboard.bin` (4 MB, sha256 `ba5adbf6…6f2f`). Restore: `esptool.py --chip esp32s3 write_flash 0 screen-original-dashboard.bin` |
| Display | NV3041A over QSPI (CS 45, SCK 47, D0–D3 21/48/40/39), backlight GPIO 1. Main screen renders |
| Touch | GT911 on SDA 8 / SCL 4, INT 3, RST 38. **Both axes mirrored** — flipped in `Display.cpp`. Top-left tap reads ~25,25 |
| I²C | Touch on bus 0 (8/4, on-board only). MCP23017 on **bus 1, GPIO 15/16** — initialises, reports not found (not wired) |
| Build fixes | `huge_app.csv` partitions (stock table was 8 MB layout → boot loop); `qio_opi` confirmed (quad → PSRAM ID read error) |
| Diagnostics | `pio run -e hmi-diag` — skips I²C, waits for USB, logs display bring-up, colour cycle |

#### Connector map (silkscreen, JST 1.25 mm / MX1.25, 4-pin)

| Connector | Pins | Allocated to |
| --- | --- | --- |
| P1 | GND · RXD · TXD · +5V | UART0 + 5 V in |
| P2 | IO46 · IO9 · IO14 · IO5 | spares 5, 9, 14 — **avoid 46** (boot strap) |
| P3 | IO6 · IO7 · IO15 · IO16 | **MPG A/B = 6/7**, **MCP I²C SDA/SCL = 15/16** |
| P4 "UART1" | GND · 3.3V · IO17 · IO18 | **UART to FluidNC** |
| P5 | GND · 3.3V · IO17 · IO18 | same as P4 — use one, never both |

P3 has no power pins; take GND and 3.3 V for the shifter and expander from P4. The MCP23017 bus
needs external 4.7 kΩ pull-ups to 3.3 V.

**Cables:** only one lead came with the board. Buy single-ended (plug one end, bare wire the
other) **MX1.25 / Molex 51021-compatible 4-pin** leads. Measure pin 1 to pin 4 on P4 first:
≈3.75 mm confirms 1.25 mm pitch.

#### Step B wiring — decided, not yet connected

Supplied lead in P4, colours confirmed by the user:

| Wire | P4 pin | → FluidNC ESP32 |
| --- | --- | --- |
| Red | GND | GND |
| Yellow | 3.3V | **nothing — insulate** (never tie two 3.3 V rails) |
| Blue | IO17 (screen RX) | D17 (FluidNC TX) |
| Black | IO18 (screen TX) | D16 (FluidNC RX) |

Keep D33/D25 jumpered to GND. **Pass:** screen goes from NO LINK to linked, state Alarm;
resetting FluidNC shows link lost then recovered.

### Open items

| # | Item | Where |
| --- | --- | --- |
| 1 | ~~74HCT14 vs 74LVC14 for the MPG shifter~~ ✅ decided: **74LVC14 on 3.3 V**; BOM, drawings and code comments corrected. Still check the part that actually arrives | `docs/BOM.md` block G |
| 2 | ~~Input-conditioning pull-up placement~~ ✅ documented: pull-up on the sensor side of the 10 kΩ, clamp + 100 nF on the GPIO side | `docs/BOM.md` block E, `docs/WIRING-RevH.md` diagram 4 |
| 3 | Contactor coil voltage assumed 230 V AC in the wiring map | `docs/WIRING-RevH.md` diagram 5 |
| 4 | ~~Buck sizing justified by the old RGB panel~~ ✅ re-derived: ≈0.6–0.7 A load at 5 V, ≥2 A kept for ≈3× margin | `docs/BOM.md` block A |
| 5 | ~~Panel cutout unchecked~~ ✅ 120 × 70.2 mm from the Guition spec — still measure the board in hand before cutting | `docs/BOM.md` block F |
| 6 | ~~Pin table said "No MCP23017"~~ ✅ corrected: expander on its own I²C bus 1 (15/16) | `docs/DESIGN-PLAN-RevH.md` |
| 7 | ~~TB6600 common anode +5 V in one place~~ ✅ +3.3 V everywhere | `docs/DESIGN-PLAN-RevH.md` |
| 8 | Foot-switch release edge (dead-man retract) still unverified in FluidNC. Pedal **ordered 2026-09-13**; the edge behaviour can be tested before it arrives with a jumper on GPIO 13 | `firmware/README.md` |
| 9 | `steps_per_mm` 1066.67 is derived, not measured — needs a dial indicator | `firmware/README.md` |
| 10 | ~~Published wiring-map artifact still shows the old board~~ ✅ republished 2026-09-13 (version 2) | claude.ai artifact |
