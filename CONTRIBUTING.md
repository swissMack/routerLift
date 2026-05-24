# Contributing

## Style

- C++14, Arduino-ESP32 framework
- File layout: one class per `.h/.cpp` pair, named CamelCase
- Member variables: `trailingUnderscore_`
- Constants: in a `namespace` block in `config.h`
- Each module exposes a single global instance (e.g. `extern MotorControl Motor;`)
- Comments explain *why*, not *what* — assume the reader can read the code

## Safety-critical changes

Any change that touches motion or fault handling needs review before merge:

- `MotorControl` — soft-limit enforcement lives here
- `Safety` — fault state machine
- `Homing`, `Zeroing` — they suppress endstop faults during their routines
- The `checkEndstops()` / `enforceSoftLimits()` calls in `main.cpp`

Bench-test on the hardware with the router unpowered before opening a PR
that touches any of the above.

## Commits

Conventional Commits style:

```
feat: short imperative summary
fix:  short imperative summary
chore:
docs:
refactor:
```

One logical change per commit. Keep summaries under 72 chars; explain
the why in the body if it isn't obvious.

## Branches

- `main` — always buildable and tagged for release
- `feature/<name>` — work in progress
- `fix/<name>` — bug fixes

## Build before pushing

```sh
pio run
```

CI is not (yet) set up — verify locally.
