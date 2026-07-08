# Decision Policies

Decision policies convert model scores, inventory state, and unit economics into actions.

Policies are evaluated separately from model training. A stronger classifier is not automatically a better policy.

## Registry

| ID | Name | Purpose |
|---|---|---|
| `P0` | No action | Baseline. |
| `P1` | Probability budget | Act on top probability scores under capacity. |
| `P2` | Direct economic | Act when predicted value exceeds cost. |
| `P3` | Hurdle economic | Combine probability and conditional value. |
| `P4` | Oracle upper bound | Diagnostic upper bound using realized outcomes. |

See [unit_economics.md](unit_economics.md) for cost assumptions.

