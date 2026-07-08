# Leakage Checklist

Use this checklist before accepting a result.

- Features use only information available at or before decision time.
- Target horizon starts after the decision timestamp.
- Train, validation, test, and holdout periods do not overlap.
- Scaling, imputation, calibration, and threshold selection are fit only on allowed splits.
- Cross-market joins do not use future timestamps from lagging feeds.
- Duplicate trades and late data are handled deterministically.
- Daily bootstrap resamples days, not individual neighboring events.
- Artifact metadata records symbols, dates, horizons, features, and code version.

