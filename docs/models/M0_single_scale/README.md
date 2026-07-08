# M0: Single-Scale Baseline

`M0` is the fixed-window baseline for real-market adverse-selection prediction.

## Definition

Use signed order-flow features from one canonical bucket, typically `B=16s`, for the target market only.

## Purpose

- Provide the minimal reference model.
- Establish whether any short-horizon flow signal exists.
- Anchor `M1` and later incremental tests.

## Expected Features

- signed buy/sell volume imbalance at one scale;
- local trade count and volume controls where already established;
- no cross-market fields;
- no pairwise interaction terms.

## Reporting

Report `M1 - M0`, `M2 - M0`, or policy uplift relative to `M0`, never only standalone `M0` performance.

