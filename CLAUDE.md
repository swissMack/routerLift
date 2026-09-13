# Project: routerLift — handoff for Claude Code

## ▶ Current state (2026-09-13) — read this first

**Bench status and the resume checklist live in `docs/BRINGUP-LOG.md`.** Design detail lives in
`docs/DESIGN-PLAN-RevH.md`. In short:

- **FluidNC board:** FluidNC v4.1.0 (esp32-wifi) flashed, `firmware/config.yaml` parses and is
  verified, bare-board acceptance passed (limits NC-correct, `uart1`/`uart_channel1` keys work).
- **Screen board:** Guition JC4827W543C — display and touch working.
- **UART link (Step B):** passed — link up, link-loss detection (feed hold + Z0 invalidated) and
  recovery (Z0 stays invalid) verified. The HMI polls `?` every 100 ms because FluidNC's
  `report_interval_ms` only reports on change.
- **Waiting on the MPG level shifters.** The right part is a **74LVC14 on 3.3 V**; the BOM's
  74HCT14 needs 5 V and would drive 5 V into the S3. Check the part before wiring it.
- **Next:** the foot-switch edge test (jumper on GPIO 13, no hardware needed — procedure in
  `docs/BRINGUP-LOG.md` resume checklist); then MPG through the shifters on P3 (GPIO 6/7), then
  the MCP23017 buttons. Foot pedal ordered 2026-09-13.
- **Not yet done:** panel buttons and MPG unwired; HMI increments 4 and 5 not started; lift body
  not bought; `steps_per_mm` 1066.67 is derived, not measured; foot-switch release edge unverified.

FluidNC: `routerlift.local` / 192.168.1.82 (AP fallback `FluidNC`). Screen: `/dev/cu.usbmodem*`.

---

## What this repo is

Open-firmware automated router lift, **Rev H split architecture**:

- **Motion** — stock, unmodified FluidNC on a classic ESP32-WROOM-32 devkit (30-pin, USB-C,
  CH340). TB6600 driver at 1/8 step, NPN NC limits, `G38.2` touch plate, `Relay` spindle output.
  Host lift: sauter FML-P (1.5 mm lead, 65 mm travel).
- **HMI** — our C++ (PlatformIO, Arduino, LVGL 8.4) on a **Guition JC4827W543C** ESP32-S3 4.3"
  panel (NV3041A QSPI, GT911 touch, 4 MB flash, 8 MB octal PSRAM). It is a GRBL sender over
  UART, with a 100 PPR MPG handwheel and panel buttons on an MCP23017.

The v1.x single-ESP32 design (DM542, ILI9488, `MotorControl`, …) is retired. It lives in
`legacy/` (reference only, not built) and in git history (tag `v1.1.0-bespoke`).

Repo: `git@github.com:swissMack/routerLift.git` (private).

## Key paths

| Path | What |
| --- | --- |
| `docs/BRINGUP-LOG.md` | What has been proven on the bench — newest first |
| `docs/DESIGN-PLAN-RevH.md` | The Rev H design, phase by phase |
| `docs/UART-PROTOCOL.md` | HMI ↔ FluidNC command vocabulary |
| `docs/BOM.md`, `docs/WIRING-RevH.*`, `docs/PINOUT.svg` | Parts and wiring |
| `firmware/config.yaml` | The entire motion-side implementation (no source) |
| `firmware/README.md` | Flashing, YAML gotchas, pre-power-up checks, commissioning |
| `platformio.ini` | Root; builds `hmi/` only |
| `hmi/include/pins.h` | The only place panel GPIO numbers appear |
| `hmi/include/config.h` | Tunable constants, each citing its Q&A item |
| `hmi/src/` | `Link`, `Wheel`, `Buttons`, `Display`, `Ui`, `Zero`, `Store`, `main` |
| `legacy/` | Retired v1.x firmware, not built |

## Build, flash, console

HMI (from the repo root):

```sh
pio run -e hmi                 # build
pio run -e hmi -t upload       # flash the panel (native USB, auto-resets)
pio run -e hmi-diag -t upload  # bring-up build: skips I2C, waits for USB, logs display, colour cycle
pio device monitor             # 115200
```

If the app has hung and upload cannot connect: hold **BOOT**, tap **RST**, upload again.
Factory demo backup: `~/Documents/routerLift-firmware-backups/screen-original-dashboard.bin`.

FluidNC:

- Flash with **installer.fluidnc.com** (Chrome/Edge, WiFi build).
- Upload config: `$Xmodem/Receive=/localfs/config.yaml` from the installer terminal, check the
  byte count, then **`$Bye`** to restart (`$CD` shows what loaded at last boot, not the file).
- Console over WiFi: `telnet routerlift.local 23` — same `?` / `$` commands as USB.
- `$Limits` shows live input state; exit with `!`.

## Architectural invariants (Rev H)

Don't relitigate these:

- **FluidNC owns motion safety.** Soft/hard limits, homing, probing and step generation are
  FluidNC's. It stays **stock** — the machine is defined by `config.yaml` only. Any proposal that
  needs FluidNC source edits forfeits this.
- **The HMI has no motion authority (ELE-11).** A bug in `hmi/` may give a wrong depth, never an
  unsafe move. Nothing in `hmi/` enforces a limit.
- **`Link` is the only UART writer.** That keeps `docs/UART-PROTOCOL.md` exhaustive.
- **STOP is FluidNC's `feed_hold_pin`** (GPIO 21), not an HMI input — it works if the HMI has
  crashed. The E-stop mushroom kills mains and is separate.
- **Foot-switch plunge is local on FluidNC** (`macro0_pin`, `$Macro0` rewritten by the HMI). The
  release/retract half via an HMI mirror input is still unverified.
- **Z0 belongs to the HMI, with no override anywhere.** Invalidated by link loss, alarm,
  bit-change entry, failed probe, and never-set at boot; it stays invalid after link recovery
  until re-probed (FW-09).
- **Link loss** (no status for 500 ms) sends a feed hold and invalidates Z0.
- **`hmi/include/pins.h` is the only place panel GPIOs appear.**
- **MPG shifter is a 74LVC14, two stages per channel, non-inverting** → `SIGNALS_INVERTED = false`.

## Working conventions

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`)
- One logical change per commit; safety-relevant changes bench-tested first
- Build before pushing (`pio run -e hmi`)
- Concise plain-language responses; show the plan before changes; ask before destructive operations
- Never delete or overwrite files without explicit user approval

---

# context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
