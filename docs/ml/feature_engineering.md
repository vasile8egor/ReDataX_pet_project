# Feature Engineering

Features must be available at decision time.

## Core Families

| Family | Examples |
|---|---|
| Local flow | signed volume imbalance, trade count, total volume. |
| Multiscale flow | `phi` over `B={1,2,4,8,16,32,64}`. |
| Cross-market state | synchronized fields from related symbols. |
| Interaction terms | pairwise products for `M3` only. |
| Inventory state | synthetic FX exposure, stress, and Hamiltonian components. |

## Rules

- Use closed-left or otherwise explicitly causal windows.
- Do not include future price, future volume, or future event count.
- Store feature-generation parameters with each artifact.
- Prefer deterministic transformations that can be replayed by date.

