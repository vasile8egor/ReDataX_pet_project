# M1: Local Multiscale

`M1` extends `M0` by using several temporal scales for the same market.

## Definition

Use target-market signed flow over:

```text
B = {1, 2, 4, 8, 16, 32, 64} seconds
```

## Hypothesis

Short-horizon adverse selection depends on flow persistence and reversal across multiple scales, not only one fixed bucket.

## Included

- target-market multiscale `phi`;
- optional local volume/trade-count controls;
- causal features only.

## Excluded

- synchronized fields from other markets;
- explicit `J_ij phi_i phi_j` interactions;
- future-looking realized markout features.

## Current Interpretation

`M1` is the primary supported predictive baseline for BTCUSDT and ETHUSDT short horizons.

