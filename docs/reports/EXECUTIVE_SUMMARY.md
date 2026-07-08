# Executive Summary

ReDataX is a research platform for FX-style inventory simulation and real-market adverse-selection modeling.

The strongest current research direction is short-horizon multiscale order-flow modeling. Local multiscale features have shown more stable signal than a single fixed-scale baseline in out-of-time tests on liquid Binance symbols.

The business question is not whether a model improves AP alone, but whether a calibrated score can drive a decision policy with positive unit economics after costs, acceptance effects, and risk constraints.

## Current Position

- `M1` local multiscale is the main supported predictive model family.
- Cross-market fields are promising but must be reported as incremental tests over `M1`.
- Explicit interaction terms should not be treated as proven until `M3 - M2` is stable.
- Economic policies require careful separation between markout proxy and realized PnL.

