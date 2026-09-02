# HMI ↔ Motion Controller Protocol

Document: RTL-PROTO-001 · Rev A · 2 September 2026

Closes the RevG §14 open item *"HMI↔controller UART protocol definition."*

The HMI (ESP32-S3) speaks to the motion controller (ESP32 running **stock** FluidNC) as an
ordinary **GRBL sender**. There is no custom protocol, no framing layer of our own, and no
modification to FluidNC. Everything below is standard GRBL/FluidNC traffic.

> **Why this matters architecturally.** Because the HMI is just another GRBL client, FluidNC
> remains a stock binary configured by one YAML file. Nothing we write runs on the motion side.
> That is what keeps homing, limits, probing and step generation out of our hands — and it is
> forfeited the moment anyone proposes a custom message type.

---

## 1. Physical layer

| Property | Value |
| --- | --- |
| Interface | UART1 on FluidNC, UART1 on the HMI |
| Baud | 115200, 8N1, no flow control |
| Levels | **3.3 V both ends — no level shifting** |
| FluidNC pins | `GPIO 17` TX → HMI `GPIO 17` RX · `GPIO 16` RX ← HMI `GPIO 18` TX |
| Cable | 2-core + common ground, inside the enclosure |

A common ground between the two boards is required and is easy to forget when they are fed from
the same 5 V rail through separate leads.

**Verify before writing `config.yaml`:** FluidNC exposes a secondary GRBL channel through a
`uart1:` section plus a `uart_channel1:` block. Confirm the exact key names against the installed
release. If the version in hand lacks a second channel, the HMI must share the USB serial port,
which costs the debug console — a real loss during bring-up.

---

## 2. Framing rules

GRBL is line-oriented. Two distinct classes of traffic share the link.

### 2.1 Line commands — acknowledged

Terminated with `\n`. Each produces exactly one response: `ok`, or `error:N`.

**The HMI keeps a single command in flight.** It does not send the next line until the previous
one is acknowledged. This is deliberately more conservative than the character-counting flow
control a file streamer would use — we are sending short interactive commands, not streaming a
program, so throughput is irrelevant and simplicity is worth more.

```
HMI → $H\n
      ... (blocks; homing runs)
    ← ok
HMI → G90 G21 G53 G0 Z-2.000\n
    ← ok
```

### 2.2 Realtime bytes — never acknowledged

Single bytes, no terminator, no `ok`. FluidNC acts on them **immediately**, including while a
motion is executing and while a line command is still unacknowledged.

| Byte | Meaning | Used for |
| --- | --- | --- |
| `?` | Status query | Polling position and state |
| `!` | Feed hold | STOP button, link-loss handling |
| `~` | Cycle start / resume | Resuming after a hold |
| `0x18` | Soft reset | STOP long-press |
| `0x85` | Jog cancel | Handwheel direction reversal |

**These bypass the in-flight window entirely.** That is the whole point: a feed hold must not
queue behind a pending `ok`.

---

## 3. Status reporting

The HMI's entire display is driven by the status report.

```
<Idle|MPos:0.000,0.000,12.345|FS:0,0>
<Jog|MPos:0.000,0.000,12.410|FS:300,0>
<Alarm|MPos:0.000,0.000,0.000|FS:0,0>
```

| Field | Use |
| --- | --- |
| State | `Idle` `Run` `Jog` `Hold` `Home` `Alarm` `Door` `Check` — drives the status strip |
| `MPos` | Machine position. The Z component is the height display |
| `FS` | Feed and spindle. Spindle non-zero ⇒ router live, drives the ROUTER LED |

**Preferred: FluidNC's automatic reporting** (`$Report/Interval`, target ~10 Hz) rather than the
HMI polling `?`. Auto-reporting halves the link traffic and removes a timer from the HMI.
**Verify this setting exists in the installed release**; fall back to polling `?` at 10 Hz if not.

### 3.1 Probe result

After a successful `G38.2`, FluidNC emits a probe report before the `ok`:

```
[PRB:0.000,0.000,-12.345:1]
```

The trailing `:1` means the probe triggered; `:0` means it did not. **A `:0` must be treated as a
failed touch-off** — Z0 stays invalid and no cycle may start.

---

## 4. Command vocabulary

Everything the HMI ever sends. If a needed action is not on this list, that is a signal to
reconsider the design rather than to extend the protocol.

| Purpose | Command |
| --- | --- |
| Home | `$H` |
| Unlock after alarm | `$X` |
| Jog one detent | `$J=G91 G21 Z<delta> F<rate>` |
| Cancel jog | `0x85` |
| Probe toward table | `G38.2 Z<target> F<feed>` |
| Set work zero | `G10 L20 P1 Z<value>` |
| Absolute move | `G90 G21 G0 Z<target>` (rapid) or `G1 Z<target> F<rate>` (fed) |
| Machine-coordinate move | `G53 G0 Z<target>` |
| Router on / off | `M3 S1000` / `M5` |
| Feed hold / resume | `!` / `~` |
| Soft reset | `0x18` |
| Read settings | `$$` |

**Jogs use `$J=`, never `G91 G0`.** Jog commands live outside the queued motion buffer, so `0x85`
can cancel them instantly. A `G0` jog would sit in the planner queue and keep executing after the
operator stops turning the wheel — precisely the behaviour the look-ahead clamp exists to prevent.

---

## 5. Handwheel handling

The most latency-sensitive path in the system, and the one place the split architecture is
measurably worse than a single-board design.

```
detent → PCNT count → × scale → $J= → UART → FluidNC planner → steps
```

**Scale** (ELE-09, B.8): fine 0.01 mm/detent, rough 0.1 mm/detent — 100 PPR gives 1 mm or 10 mm
per revolution.

**Three rules, all mandatory:**

1. **Coalesce.** Accumulate detents over a 20–50 ms window and emit one `$J=` for the sum. One
   command per detent would flood the link on a fast spin.
2. **Clamp look-ahead.** Never let queued jog distance exceed **one motor revolution** ahead of
   the reported `MPos`. Adopted from FXBB (`ino:282-289`), and it matters more here than there
   because our commands cross a UART hop.
3. **Cancel on reversal.** Send `0x85` when the wheel changes direction, then start fresh. Without
   this, reversing means waiting for queued motion in the old direction to finish.

---

## 6. Cycle sequences

### 6.1 Startup

```
HMI  → 0x18                     soft reset to a known state
     ← Grbl 1.1 / FluidNC banner
HMI  → $$                       read settings, confirm link and version
     ← $0=... (settings)
     ← ok
                                display: "NOT HOMED", all cycles locked
HMI  → $H                       on operator command
     ← ok
                                display: "Z0 INVALID", cycles still locked
```

Nothing moves until homed; no cycle until Z0 is probed. Neither has an override.

### 6.2 Touch-off (ZERO button)

```
                                pre-check: probe must not read triggered.
                                If it does → fault, no override (FLT-02).
HMI  → G38.2 Z-50 F300          fast find, 5 mm/s
     ← [PRB:...:1]  ok
HMI  → G91 G0 Z1                retract 1 mm
     ← ok
HMI  → G38.2 Z-3 F30            slow confirm, 0.5 mm/s
     ← [PRB:...:1]  ok
HMI  → G10 L20 P1 Z<plate>      set work zero, allowing for plate thickness
     ← ok
                                Z0 now valid; cycles unlocked
```

### 6.3 Standard cut

For a 10 mm groove with scribe on, rough 2.0 mm, finish 0.3 mm, the HMI computes
`0.30 · 2.72 · 5.13 · 7.55 · 10.00` and then, **for each pass**:

```
                                wait for CYCLE START (no auto-advance)
HMI  → G90 G21 G1 Z<depth> F120 plunge at 2 mm/s
     ← ok
                                poll state until Idle
                                display "PASS n OF m — PRESS CYCLE START"
```

All final approaches are from below (MOT-07), which falls out naturally: passes only ever
increase in depth.

### 6.4 Bit change

```
HMI  → M5                       router off first
     ← ok
HMI  → G53 G0 Z<top>            rapid to the top limit
     ← ok
                                "AT TOP — CHANGE BIT", motion locked out
                                (long-press BIT CHANGE to exit)
                                Z0 invalidated — re-probe mandatory
```

The key switch is turned and the key removed before anyone reaches into the cutter. That is a
hardware interlock (SAF-02); the software lockout above is a convenience, not the protection.

### 6.5 Keyhole

Built last. The only cycle where the cutter moves under power while engaged.

```
                                confirm workpiece clamped, router running
HMI  → G90 G1 Z<depth> F120     controlled plunge
     ← ok
                                operator feeds workpiece to the stop and back
                                retract BLOCKED until entry point confirmed (OPS-09)
HMI  → G90 G0 Z<clear>          lower clear once confirmed
     ← ok
HMI  → M5
```

---

## 7. Fault and link-loss handling

### 7.1 Alarms

An `ALARM` state or `error:N` response stops everything. The HMI shows the cause, offers
acknowledgement, and then requires `$X` followed by a **mandatory re-home**. Z0 is invalidated on
the way through (FW-09). There is no resume.

| Condition | HMI behaviour |
| --- | --- |
| Hard limit hit | Alarm; name which switch; require re-home |
| Soft limit rejected | Report the rejected target; no motion occurred |
| Probe failed (`:0`) | Touch-off failed; Z0 stays invalid |
| Probe shorted at start | Refuse the cycle; no override |
| Homing pull-off failure | Report as a **stuck switch or inverted polarity**, not as a limit — the FXBB diagnostic (`ino:427-435`) |

### 7.2 Link loss

**Detection:** no status report for **500 ms** (five missed intervals at 10 Hz).

**Response, in order:**

1. Send `!` (feed hold) — it may not arrive, and that is acceptable
2. Show `LINK LOST` prominently
3. Invalidate Z0
4. Refuse to originate any motion
5. On reconnection: require `$X` if alarmed, then a full re-home and re-probe

**What link loss must never do**, per ELE-11:

- It must not **start** motion.
- It must not **block a stop.** STOP is wired to FluidNC's own `feed_hold_pin` and does not
  traverse this link at all. The E-stop is mains hardware and traverses nothing.

The asymmetry is deliberate. A dead link should cost you a cut, never control of the machine.

---

## 8. Verification

Maps to bench-test steps 5 and 6.

| # | Test | Pass criterion |
| --- | --- | --- |
| 1 | Link up | `$$` returns settings; version shown on the HMI splash |
| 2 | Status tracking | Jog from the USB console; the HMI height display follows |
| 3 | Jog out | One detent moves exactly 0.01 mm (fine) / 0.1 mm (rough) |
| 4 | Coalescing | A fast wheel spin does not lag or overrun; queued distance stays within one motor revolution |
| 5 | Jog cancel | Reversing direction stops the old direction immediately |
| 6 | Feed hold | STOP halts motion mid-jog — **test with the HMI unplugged**, since it is wired to FluidNC |
| 7 | Probe report | `G38.2` returns `[PRB:...]` and the HMI parses the Z value |
| 8 | Probe miss | With no plate fitted, `:0` is reported and Z0 stays invalid |
| 9 | Soft limit | A move beyond the envelope returns an error; **no motion occurs** |
| 10 | **Link loss** | Pull the cable mid-jog: motion stops or completes safely, never starts; HMI shows `LINK LOST`; `$H` still works from USB |

Test 10 is the important one. It is the failure mode a single-board design cannot have, and the
only proof that the boundary in section 7.2 holds in practice rather than on paper.

---

## 9. Items to verify against the installed FluidNC release

Everything here is from working knowledge of GRBL and FluidNC, not from reading the docs of the
specific build in hand. Confirm before writing `config.yaml`:

1. `uart1:` / `uart_channel1:` key names for the second GRBL channel.
2. `$Report/Interval` for automatic status reporting, and whether ~10 Hz is achievable.
3. Whether homing pull-off failure surfaces as a distinct alarm code the HMI can name.
4. `$Macro0` length limits, and whether a macro can be conditioned on spindle-ready for the
   foot-switch plunge gate (SAF-03). If it cannot, that gate moves into the HMI and the macro
   stays a bare move.
5. Whether `relay_spindle` reports a non-zero `S` value in the status report — the ROUTER LED
   depends on it.
