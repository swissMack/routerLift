# UX

> **SUPERSEDED — this describes the single-board v1 UI** (3.5" ILI9488 at 480×320, x1/x10/x100 rate
> switch, SSR router power, touch MENU/PARK/POWER buttons). **Do not build from it.** Rev H uses a
> 480×272 JC4827W543C panel, six physical buttons and a rough/fine switch. See
> `docs/DESIGN-PLAN-RevH.md` Phase 4 (modules, safety invariants) and Phase 4b, `docs/REVIEW-RevH.md`
> §10 (physical control panel) and `docs/DESIGN-QA.md` (display and panel decisions). The input-
> separation principle below (MPG jogs, touch navigates) still holds. See `docs/SUPERSEDED.md`.

## Input separation

| Input | Role | Rationale |
| --- | --- | --- |
| MPG | Jog the lift, edit calibration values | Tactile precision, no false touches |
| Rate switch | Set MPG step band | Muscle memory from CNC machines |
| Touch | Menu navigation, button taps | Comfortable for menu tree, but never moves the cutter |
| Foot switch | Plunge cycle | Hands-free during cuts |

## Main screen

```
┌─ Router Lift ─────────────────────── v1.0.0 ─┐
│                                              │
│     +12.45 mm                                │   ← live position, big
│                                              │
│   Target: +10.00 mm                          │
│   Park  : -1.00 mm                           │
│   Rate x10 | 0.010 mm/pulse                  │   ← live step size
│                                              │
│   Preset 2: 15.00 mm                         │
│                                              │
│ [ MENU ]   [ PARK ]   [ POWER ON ]           │   ← touch buttons
└──────────────────────────────────────────────┘
```

- Spinning the MPG jogs the lift. Step size = `rate × velocity scaling`.
- `MENU` → root menu screen.
- `PARK` → immediate move to Park position.
- `POWER` → toggles SSR. Warmup state shown in status bar.

## Menu screen

Each row is a touch target. Tap a row to enter that screen.
`BACK` (top-right) returns to the previous screen.

```
┌─ Menu ─────────────────────────────── BACK ──┐
│ Recall Preset                                │
│ Save Preset                                  │
│ Set Target                                   │
│ Home                                         │
│ Zero Tool                                    │
│ Router Power                                 │
│ Calibrate Motor                              │
│ Calibrate Motion                             │
│ Calibrate Limits                             │
│ Calibrate Sensors                            │
└──────────────────────────────────────────────┘
```

## Set Target screen

Spin the MPG to adjust the target value. Step size shows live. Tap
`OK` to commit, `CANCEL` to discard.

```
┌─ Set Target Height ──────────────── BACK ──┐
│                                            │
│       +10.00 mm                            │   ← big value
│                                            │
│   Spin MPG to adjust                       │
│   Rate x10, 0.010 mm/pulse                 │
│                                            │
│  [   OK   ]        [ CANCEL ]              │
└────────────────────────────────────────────┘
```

## Calibration screens

Tap a row to select it (row turns green). Tap again to enter edit mode
(row turns amber). While in edit mode, the MPG changes the value. Tap
the row a third time to commit (or tap a different row to switch
fields). Tap `BACK` to leave.

```
┌─ Calibrate Motor ──────────────── BACK ──┐
│ Steps/rev          1000                  │ ← selected (green)
│ Pitch              4.000 mm              │
│ Dir invert         no                    │
└──────────────────────────────────────────┘
```

## Foot switch

| Event | Behaviour |
| --- | --- |
| Press (in IDLE) | Lift drives to Target — only if relay is ON and warmed up |
| Release | Lift returns to Park |
| Press (in any other state) | Ignored |

Plunge is silently refused if the spindle isn't running or hasn't yet
passed the startup delay. A serial log line explains why.

## Fault screen

Red header, big fault code, message, and one big `ACKNOWLEDGE`
button. Acknowledgement clears the fault and returns to MAIN; the lift
remains where it stopped — no automatic motion after an acknowledgement.

## Rate switch effect

Visible everywhere via the status bar (`Rate: x10`) and on the main
screen with current effective `mm/pulse`. Changing the switch mid-jog
takes effect on the next pulse.

| Switch | Slow spin | Fast spin |
| --- | --- | --- |
| x1   | 0.001 mm/pulse | 0.010 mm/pulse |
| x10  | 0.010 mm/pulse | 0.100 mm/pulse |
| x100 | 0.100 mm/pulse | 1.000 mm/pulse |
