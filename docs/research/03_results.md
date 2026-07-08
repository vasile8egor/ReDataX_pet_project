# Results

This file summarizes current research claims. The detailed historical registry remains in [../results/experiment_registry.md](../results/experiment_registry.md).

## Supported Claims

- Local multiscale order-flow features improve short-horizon adverse-selection prediction over a single fixed scale on BTCUSDT and ETHUSDT in out-of-time tests.
- Simple RG-inspired local scale transformations did not provide stable incremental value beyond the multiscale feature vector.
- Cross-market synchronized fields can add predictive information, but explicit pairwise interaction terms require strict incremental testing before being used as a headline claim.
- Inventory-aware synthetic policies can improve simulated risk-return under the assumptions of the generator.

## Rejected or Constrained Claims

- Do not claim that RG-style coefficients are physical market constants.
- Do not claim real realized trading PnL from markout exposure.
- Do not publish historical controller uplift as a current-main result unless a reproducible artifact exists.

## Evidence Requirements

Each result should include:

- command or script path;
- input date range and symbols;
- artifact path;
- baseline and candidate model;
- metric definition;
- confidence interval or paired day-level comparison.

