# Model Registry

This registry defines canonical model IDs and the language used across reports.

| ID | Name | Role | Status |
|---|---|---|---|
| `M0` | Single-scale | Fixed-window baseline for adverse-selection prediction. | Baseline |
| `M1` | Local multiscale | Same market, multiple time scales. | Supported |
| `M2` | Cross-market RG no-J | Synchronized multiscale fields across markets, no explicit interactions. | Candidate/supported by experiment |
| `M3` | Cross-market RG with-J | `M2` plus pairwise interaction terms. | Incremental effect constrained |
| `M4` | Direct value regression | Predicts positive markout or value magnitude directly. | Economic modeling candidate |
| `M5` | Hurdle economic | Predicts probability and conditional value separately. | Economic modeling candidate |

## Naming Rules

- Use `M0` through `M5` in documents and artifact names.
- If a model uses additional symbols, horizons, or feature families, append them as configuration, not as a new model ID.
- A decision policy is not a model. Policies are documented in [../decision_policies](../decision_policies/README.md).

## Artifact Requirements

Each model run should save:

- model ID and version;
- feature set hash or explicit feature list;
- symbols and horizons;
- train, validation, test dates;
- calibration method;
- policy thresholds if evaluated economically;
- metrics by day and aggregate.

