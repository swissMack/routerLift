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

**Loose end:** the FluidNC board did not enumerate on the Mac during this test (only the screen's
`usbmodem` port appeared), though it was powered and linked. Likely a charge-only cable or a
power-only port. Needs a data cable before the next FluidNC-side test.

---

## 2026-09-13 — motion board and screen board, bare

**Paused here for about a week, waiting on the MPG level shifters.**

### Resume checklist (start here next session)

1. **Before wiring the level shifters, check which part arrived.** The BOM
   (`docs/BOM.md:111`) specifies a **74HCT14**. Powered at 5 V its outputs swing to 5 V, which the
   ESP32-S3 is not rated for; powered at 3.3 V it is out of spec. The safe part is a **74LVC14
   on 3.3 V** (5 V-tolerant inputs, same Schmitt hysteresis, two stages per channel stay
   non-inverting). If a 74HCT14 arrived, do not connect its outputs to the S3 until this is
   settled. Either way, `MPG::SIGNALS_INVERTED` must match the circuit.
2. ~~**Step B — join the two boards over UART.**~~ ✅ Passed later the same day — see the entry
   above. Next is the MPG through the shifters on P3 (GPIO 6/7).
3. **Push status:** everything below is committed and pushed.

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
| 1 | 74HCT14 vs 74LVC14 for the MPG shifter — see resume checklist | `docs/BOM.md:111`, `hmi/include/pins.h:30` |
| 2 | Input conditioning: pull-up placement is a drawing decision, not in the BOM. Sensor side of the 10 kΩ is required, or a closed switch only pulls the GPIO to ~2.2 V | `docs/WIRING-RevH.md` diagram 4 |
| 3 | Contactor coil voltage assumed 230 V AC in the wiring map | `docs/WIRING-RevH.md` diagram 5 |
| 4 | Buck sizing (≥2 A) still justified by the old RGB panel's draw | `docs/BOM.md:29` |
| 5 | Panel cutout 120 × 70 mm not checked against the JC4827W543C | `docs/BOM.md` |
| 6 | Pin table says "No MCP23017", contradicting the design (pre-existing) | `docs/DESIGN-PLAN-RevH.md:65` |
| 7 | TB6600 common anode still +5 V in one place; +3.3 V everywhere else | `docs/DESIGN-PLAN-RevH.md:77` |
| 8 | Foot-switch release edge (dead-man retract) still unverified in FluidNC | `firmware/README.md` |
| 9 | `steps_per_mm` 1066.67 is derived, not measured — needs a dial indicator | `firmware/README.md` |
| 10 | Published wiring-map artifact still shows the old board; republish from `docs/WIRING-RevH.md` | claude.ai artifact |
