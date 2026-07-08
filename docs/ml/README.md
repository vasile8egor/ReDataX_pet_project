# ML Protocol

The ML layer turns event data into causal features, targets, models, calibrated scores, and policy-ready artifacts.

## Canonical Flow

1. Load and validate event data.
2. Build causal features.
3. Build targets by horizon.
4. Split by time.
5. Train baseline and candidate models.
6. Calibrate scores when policies need probabilities.
7. Evaluate predictive and economic metrics.
8. Save artifacts and report status.

## Required Documents

- [feature_engineering.md](feature_engineering.md)
- [targets.md](targets.md)
- [temporal_validation.md](temporal_validation.md)
- [calibration.md](calibration.md)
- [model_selection.md](model_selection.md)
- [leakage_checklist.md](leakage_checklist.md)

