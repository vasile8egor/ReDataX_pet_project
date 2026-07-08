# M2: Cross-Market RG No-J

`M2` adds synchronized multiscale fields from related markets without explicit pairwise interactions.

## Definition

For a target symbol, include multiscale fields from:

- BTCUSDT
- ETHUSDT
- ETHBTC

No feature should be a direct product `phi_i * phi_j`.

## Hypothesis

Related markets carry common state information that can improve adverse-selection prediction for the target market.

## Use

`M2` is the clean cross-market test before adding interaction terms. It should be compared against `M1`, not only against `M0`.

## Required Checks

- timestamp alignment;
- causal availability at decision time;
- missing-market handling;
- per-day paired comparison against `M1`.

