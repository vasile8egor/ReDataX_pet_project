# Model Selection

Model selection must be performed on training and validation periods only.

## Selection Criteria

- primary predictive metric, usually Average Precision for imbalanced adverse-selection labels;
- secondary metrics, such as ROC-AUC, top-decile lift, and calibration;
- economic metric after applying a policy;
- stability by day and symbol;
- implementation complexity.

## Incremental Comparisons

| Candidate | Compare Against |
|---|---|
| `M1` | `M0` |
| `M2` | `M1` |
| `M3` | `M2` |
| `M4` | classification policy baseline |
| `M5` | `M4` and probability-only policy |

## Freeze Rule

Once a final holdout run is planned, feature set, model class, calibration, thresholds, and metrics must be frozen.

