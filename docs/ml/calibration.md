# Calibration

Calibration maps raw model scores to probabilities or expected values that decision policies can consume.

## Methods

- Platt scaling for simple probability calibration.
- Isotonic regression when validation data is sufficient.
- Bucket calibration for reporting score bands.
- Direct expected-value calibration for economic policies.

## Reporting

Include:

- calibration split dates;
- Brier score or calibration error;
- reliability by score bucket;
- threshold sensitivity.

## Caution

Calibration can decay across regimes. Refit or audit it separately from feature coefficients.

