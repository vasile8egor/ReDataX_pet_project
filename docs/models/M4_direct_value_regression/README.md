---
model_id: M4
model_name: direct_value_regression
model_version: research_v1_0
task: non_negative_regression
status: accepted
serving_status: research_only
primary_policy: P2_direct_economic
owner: Egor Vasilev
framework: scikit-learn
source_commit: 2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe
---

# M4 - Direct Value Regression

## 1. Purpose

M4 predicts a non-negative positive-markout magnitude score in basis points. Policy P2 converts this score into a notional-constrained intervention ranking under explicit cost assumptions.

Primary use:

- direct economic baseline for M5;
- positive-markout magnitude ranking;
- capital-efficiency analysis under policy P2.

Non-goals:

- realized bank PnL estimation;
- standalone probability calibration;
- production hedge execution;
- direct online serving.

## 2. Status and lineage

| Field | Value |
|---|---|
| Model ID | `M4` |
| Component name | `direct_regressor` |
| Status | Accepted |
| Predecessor | `M2` cross-market classifier |
| Successor | `M5` hurdle economic model |
| Primary policy | `P2 direct_economic` |
| Selected horizon | 600 seconds |
| Decision stride | 10 seconds |
| Feature count | 208 |

The accepted M4 implementation is the direct regressor inside `hurdle_economic_policy.py`. The earlier 5-second linear prototype in `economic_value_policy.py` is historical and did not select a robust profitable policy.

## 3. Model contract

### 3.1 Prediction unit

One valid 10-second decision point for one target market.

### 3.2 Supported targets and inputs

```python
TARGET_SYMBOLS = ("BTCUSDT", "ETHUSDT")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "ETHBTC")
```

### 3.3 Dataset object

`build_hurdle_day_dataset()` returns:

| Field | Type | Shape | Description |
|---|---|---:|---|
| `seconds` | `int64` | `(n,)` | Valid second indices |
| `features` | `float32` | `(n, 208)` | Causal model matrix |
| `feature_names` | `tuple[str, ...]` | `(208,)` | Ordered schema |
| `markout_bps` | `float64` | `(n,)` | Realized signed markout |
| `positive_labels` | `uint8` | `(n,)` | `markout > 0` |
| `break_even_labels` | `uint8` | `(n,)` | `markout > break_even` |
| `notional_usdt` | `float64` | `(n,)` | Target-market quote notional |
| `adverse_loss_usdt` | `float64` | `(n,)` | Positive markout exposure |

### 3.4 Model output

`predict_hurdle()` exposes M4 as:

```python
PredictionBundle.direct_expected_positive_markout_bps
```

| Output | Type | Range | Unit |
|---|---|---|---|
| `direct_expected_positive_markout_bps` | `float64[n]` | `[0, target_clip_bps]` | basis points |

The name is retained from the implementation. Because log-target retransformation bias is not corrected, the value is best treated as a direct magnitude score rather than a guaranteed unbiased conditional expectation.

### 3.5 Policy output

P2 produces:

| Output | Type | Range | Meaning |
|---|---|---|---|
| `action_fraction` | `float64[n]` | `[0, 1]` | Fraction of row notional acted on |
| `predicted_net_bps` | `float64[n]` | unbounded | Scenario-adjusted predicted net value |
| `PolicyMetrics` | dataclass | n/a | Daily or aggregate economic metrics |

## 4. Dataset contract

### 4.1 Source

```text
raw.fact_real_market_agg_trades
```

Public Binance Spot aggregate trades are synchronized to a UTC second grid.

### 4.2 Valid observation mask

A row is valid when:

1. at least 600 seconds of history are available;
2. the second matches the configured 10-second decision stride;
3. the target market is active;
4. target-flow direction is nonzero;
5. current and future target VWAP are finite and positive;
6. target quote notional is finite and positive;
7. `t + horizon` stays inside the same day.

### 4.3 Leakage controls

- Feature windows use current and historical data only.
- Future VWAP is used only for target construction.
- Model and policy selection use chronological periods.
- Final-holdout dates are opened only after horizon selection.
- The scenario configuration is frozen before final evaluation.

## 5. Feature schema

M4 and M5 share one 208-column schema.

| Feature family | Count |
|---|---:|
| Current log quote volume | 3 |
| Multiscale flow transforms | 84 |
| Aligned and absolute historical returns | 42 |
| Realized volatility | 18 |
| Rolling flow imbalance and quote volume | 36 |
| Flow acceleration | 9 |
| Triangular residual changes | 14 |
| Time-of-day sine and cosine | 2 |
| **Total** | **208** |

Lookback configuration:

```python
RETURN_LOOKBACKS_SECONDS = (5, 10, 30, 60, 120, 300, 600)
VOLATILITY_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)
FLOW_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)
```

Schema authority:

```python
HurdleDayDataset.feature_names
```

Any change in count, order, scale grid, lookback grid, or market order requires a new model version.

## 6. Target definition

Signed markout:

$$
m_{A,H}(t)=
10^4\,d_A(t)
\frac{P_A(t+H)-P_A(t)}{P_A(t)}
$$

Positive target:

$$
S_{A,H}(t)=\max\{m_{A,H}(t),0\}
$$

Training target:

$$
y_i^{M4}=
\log\left(1+\min\{S_i,C\}\right)
$$

For the selected `medium` preset:

```text
C = 100 bps
```

Inverse transform:

$$
\widehat S_i^{M4}=
\operatorname{clip}
\left(\exp(\widehat y_i)-1,0,C\right)
$$

No smearing correction is applied.

## 7. Training specification

### 7.1 Estimator

```python
HistGradientBoostingRegressor(loss="squared_error")
```

Selected model preset:

| Hyperparameter | Value |
|---|---:|
| Preset | `medium` |
| Learning rate | 0.05 |
| Maximum iterations | 160 |
| Maximum leaf nodes | 31 |
| Minimum samples per leaf | 60 |
| L2 regularization | 1.0 |
| Maximum bins | 63 |
| Early stopping | disabled |
| Target clip | 100 bps |
| Notional weight power | 0.25 |

### 7.2 Sample weights

$$
w_i=
\operatorname{clip}\left[
\left(
\frac{N_i}{\operatorname{median}(N_{train})}
\right)^{0.25},
0.25,
4
\right]
$$

### 7.3 Candidate grid

| Parameter | Values |
|---|---|
| Horizon | `120`, `300`, `600` seconds |
| Model preset | `compact`, `medium` |
| Notional budget | `0.01`, `0.02`, `0.05`, `0.10` |
| Minimum net margin | `0`, `0.05`, `0.10` bps |
| Minimum break-even probability | `0`, `0.40`, `0.50`, `0.60` |
| Prediction multiplier | `1.0`, `1.25`, `1.50` |

M4 is trained inside the common M4-M5 state. The final model specification and policy configuration are selected through the M5 experiment path.

## 8. Inference and policy procedure

### 8.1 Model inference

1. build `HurdleDayDataset`;
2. call `predict_hurdle(state, dataset)`;
3. read `direct_expected_positive_markout_bps`;
4. apply the selected prediction multiplier.

### 8.2 Economic conversion

Base scenario:

```yaml
internalization_rate: 0.25
mitigation_efficiency: 0.50
protection_fraction: 0.125
action_cost_bps: 0.50
break_even_markout_bps: 4.00
```

Predicted net value:

$$
\widehat v_i^{M4}=
\rho\lambda\widehat S_i^{M4}-c
$$

### 8.3 Allocation

`direct_action_fraction()`:

1. computes predicted net value;
2. applies the minimum net-margin threshold;
3. applies the shared break-even probability gate;
4. ranks eligible rows by predicted net value;
5. allocates fractional notional until the daily budget is exhausted.

Important implementation detail: the selected BTCUSDT P2 policy uses the M5 break-even classifier gate at 40%. The selected ETHUSDT threshold is zero. Therefore the reported BTCUSDT P2 result is not a fully standalone direct-regression ablation.

## 9. Evaluation protocol

| Split | Dates | Purpose |
|---|---|---|
| Train | 2025-01-06 to 2025-01-26 | Initial model fit |
| Development | 2025-01-27 to 2025-02-02 | Model and policy selection within horizon |
| Validation | 2025-02-03 to 2025-02-09 | Horizon selection |
| Final holdout | 2025-02-10 to 2025-02-16 | One-time reporting |

Candidate acceptance:

$$
\overline V_{day}>0
$$

$$
R=
\overline V_{day}
-0.5\,\operatorname{sd}(V_{day})
>0
$$

and at least five of seven days must be positive.

Economic metrics:

- net value per 1 million USDT of total notional;
- affected notional fraction;
- captured adverse-exposure fraction;
- risk concentration;
- break-even action cost;
- benefit-cost ratio;
- positive-day fraction.

## 10. Validated results

P2 on the final holdout:

| Metric | BTCUSDT | ETHUSDT |
|---|---:|---:|
| Aggregate net value, USDT/$1M | 7.20 | 23.06 |
| Mean daily net value, USDT/$1M | 4.71 | 16.58 |
| Daily standard deviation | 8.66 | 18.39 |
| Positive days | 71.4% | 100.0% |
| Affected notional | 2.98% | 6.97% |
| Captured adverse exposure | 8.39% | 14.45% |
| Risk concentration | 2.82 | 2.07 |
| Benefit-cost ratio | 5.84 | 7.62 |

Aggregate value is notional-weighted across days. Mean daily value assigns equal weight to every day.

## 11. Artifact contract

Default result:

```text
/opt/airflow/data/real_market/results/hurdle_economic_policy.json
```

Relevant fields:

```text
configuration
targets.<symbol>.selected_final_candidate
targets.<symbol>.final_test.daily[].policies.direct_economic
targets.<symbol>.final_test.aggregate.direct_economic
targets.<symbol>.final_test.daily[].prediction_diagnostics.direct_expected_markout_p95_bps
targets.<symbol>.final_test.daily[].prediction_diagnostics.direct_predicted_net_positive_fraction
```

The JSON does not contain serialized gradient-boosting estimators. Re-running batch inference requires refitting from source data.

## 12. Repository integration

| Component | Path |
|---|---|
| Dataset, M4 model, P2 policy, metrics | `src/revolut_app/real_market/experiments/hurdle_economic_policy.py` |
| Launcher | `scripts/run_hurdle_economic_policy.sh` |
| Legacy prototype | `src/revolut_app/real_market/experiments/economic_value_policy.py` |
| Policy specification | `docs/decision_policies/P2_direct_economic.md` |
| Reporting loader | `src/revolut_app/analytics/load_research_reporting.py` |

## 13. Runbook

```bash
./scripts/run_hurdle_economic_policy.sh
```

Optional output override:

```bash
OUTPUT=/opt/airflow/data/real_market/results/hurdle_economic_policy.json \
  ./scripts/run_hurdle_economic_policy.sh
```

## 14. Tests and quality gates

Run:

```bash
pytest tests/unit/real_market/experiments/test_hurdle_economic_policy.py
```

Current tests cover:

- notional-budget allocation;
- predicted-net formula;
- probability-gate behavior;
- policy profitability calculation;
- candidate rejection;
- stride and markout construction;
- use of the direct prediction in P2.

Additional productionization gates:

- exact 208-column schema;
- model serialization parity;
- scenario-version compatibility;
- deterministic final-candidate reconstruction;
- inference latency and memory limits;
- missing-data fallback.

## 15. Monitoring and retraining

Recommended model monitoring:

- direct prediction median, p95, and maximum;
- fraction with positive predicted net value;
- feature drift and non-finite rate;
- target clipping rate;
- affected-notional fraction;
- captured-exposure fraction;
- net value per $1M;
- benefit-cost ratio;
- positive-day fraction.

Retraining is required when:

- the 208-column schema changes;
- target horizon or stride changes;
- economic assumptions change;
- the source-market universe changes;
- policy budget or gating semantics change.

## 16. Known limitations

- Public Binance flow is not client flow.
- Scenario parameters are assumptions, not institution-specific estimates.
- The target is clipped at 100 bps.
- Log-target retransformation bias is not corrected.
- P2 shares a break-even probability component with the M5 contour.
- The final holdout contains seven daily clusters.
- Positive scenario-adjusted value is not executable or realized PnL.

## 17. References

- [Extended M4 theory](./M4_Theory.pdf)
- [Scikit-learn HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)
- [Pinned implementation](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/hurdle_economic_policy.py)
