# M3: Cross-Market RG With-J

`M3` extends `M2` with explicit pairwise interaction terms.

## Definition

Add terms of the form:

```text
phi_i^B(t) * phi_j^B(t)
```

for selected market pairs and scales.

## Hypothesis

Pairwise interactions capture coupled market pressure that is not represented by additive synchronized fields.

## Risk

Interaction terms increase dimensionality and can overfit regime-specific co-movement. `M3` must be treated as an incremental test over `M2`.

## Claim Rule

Only claim `J` value when `M3 - M2` is positive, stable by day, and economically meaningful after thresholding.

