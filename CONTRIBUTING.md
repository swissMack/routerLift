# Contributing

## Style

- C++14, Arduino-ESP32 framework
- File layout: one class per `.h/.cpp` pair, named CamelCase
- Member variables: `trailingUnderscore_`
- Constants: in a `namespace` block in `config.h`
- Each module exposes a single global instance (e.g. `extern Link Motion;`)
- GPIO numbers appear only in `hmi/include/pins.h`
- Comments explain *why*, not *what* — assume the reader can read the code
- `firmware/` stays stock FluidNC: `config.yaml` only, no source edits

## Safety-critical changes

Any change that touches motion or fault handling needs review before merge:

- `firmware/config.yaml` — limits, homing, probe, STOP, relay (FluidNC owns motion safety)
- `hmi/src/Zero.*` — Z0 validity and invalidation rules; no override anywhere
- `hmi/src/Link.*` — the only UART writer; link-loss feed hold
- `hmi/src/Wheel.*` — jog coalescing, look-ahead clamp, cancel-on-reversal

Bench-test on the hardware with the router unpowered before opening a PR
that touches any of the above.

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
pio run -e hmi
pio run -e hmi-diag
```

CI is not (yet) set up — verify locally.
