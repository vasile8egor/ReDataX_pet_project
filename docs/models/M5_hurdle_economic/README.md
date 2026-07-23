---
model_id: M5
model_name: hurdle_economic
model_version: research_v1_0
task: hurdle_expected_value
status: final_candidate
serving_status: research_only
primary_policy: P3_hurdle_economic
owner: Egor Vasilev
framework: scikit-learn
source_commit: 2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe
---

# M5 - Hurdle Economic Model

## 1. Purpose

M5 separates positive-markout occurrence from positive-markout severity and adds an independent break-even probability gate. Policy P3 converts the combined score into a notional-constrained economic decision.

Primary use:

- final ReDataX economic research candidate;
- scenario-adjusted intervention ranking;
- comparison with no action, probability ranking, and M4 direct regression.

Non-goals:

- guaranteed realized PnL;
- causal market-impact estimation;
- direct production hedge execution;
- online serving without additional packaging.

## 2. Status and lineage

| Field | Value |
|---|---|
| Model ID | `M5` |
| Component name | `hurdle` |
| Status | Final candidate with qualification |
| Predecessor | `M4` direct value regression |
| Primary policy | `P3 hurdle_economic` |
| Selected horizon | 600 seconds |
| Decision stride | 10 seconds |
| Feature count | 208 |

M5 is positive relative to no action on both final target markets. It does not demonstrate universal superiority over every deployable baseline.

## 3. Model contract

### 3.1 Prediction unit

One valid 10-second decision point for one target market.

### 3.2 Supported targets and inputs

```python
TARGET_SYMBOLS = ("BTCUSDT", "ETHUSDT")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "ETHBTC")
```

### 3.3 Dataset object

`HurdleDayDataset`:

| Field | Type | Shape | Description |
|---|---|---:|---|
| `seconds` | `int64` | `(n,)` | Valid second indices |
| `features` | `float32` | `(n, 208)` | Causal feature matrix |
| `feature_names` | `tuple[str, ...]` | `(208,)` | Ordered feature schema |
| `markout_bps` | `float64` | `(n,)` | Realized signed markout |
| `positive_labels` | `uint8` | `(n,)` | `markout > 0` |
| `break_even_labels` | `uint8` | `(n,)` | `markout > break_even` |
| `notional_usdt` | `float64` | `(n,)` | Target-market quote notional |
| `adverse_loss_usdt` | `float64` | `(n,)` | Positive markout exposure |

### 3.4 Prediction output

`PredictionBundle`:

| Field | Type | Range | Meaning |
|---|---|---|---|
| `probability_positive` | `float64[n]` | `[0, 1]` | Probability of positive markout |
| `probability_break_even` | `float64[n]` | `[0, 1]` | Probability of markout above break-even |
| `conditional_positive_markout_bps` | `float64[n]` | `[0, C]` | Severity score conditional on positive markout |
| `expected_positive_markout_bps` | `float64[n]` | `[0, C]` | `probability_positive * conditional severity` |
| `direct_expected_positive_markout_bps` | `float64[n]` | `[0, C]` | M4 baseline output |

### 3.5 Policy output

P3 returns:

| Output | Type | Range | Meaning |
|---|---|---|---|
| `action_fraction` | `float64[n]` | `[0, 1]` | Fraction of row notional acted on |
| `predicted_net_bps` | `float64[n]` | unbounded | Predicted net value after scenario cost |
| `PolicyMetrics` | dataclass | n/a | Daily or aggregate policy metrics |

## 4. Dataset contract

### 4.1 Source

```text
raw.fact_real_market_agg_trades
```

The source contains public Binance Spot aggregate trades synchronized to a UTC second grid.

### 4.2 Valid observation mask

A row is valid only when:

1. 600 seconds of history are available;
2. the second matches the 10-second decision stride;
3. the target market is active;
4. target-flow direction is nonzero;
5. current and future target VWAP values are finite and positive;
6. target notional is finite and positive;
7. the target timestamp remains in the same day.

### 4.3 Leakage controls

- All features are current or trailing.
- Future VWAP defines targets only.
- Development selects model-policy candidates within each horizon.
- Validation selects one horizon.
- Final holdout is reporting-only.
- Scenario assumptions are frozen before final evaluation.

## 5. Feature schema

M5 shares the 208-column schema with M4.

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

Configured lookbacks:

```python
RETURN_LOOKBACKS_SECONDS = (5, 10, 30, 60, 120, 300, 600)
VOLATILITY_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)
FLOW_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)
```

Schema authority:

```python
HurdleDayDataset.feature_names
```

## 6. Target definition

Signed markout:

$$
m_{A,H}(t)=
10^4\,d_A(t)
\frac{P_A(t+H)-P_A(t)}{P_A(t)}
$$

Positive magnitude:

$$
S_i=\max\{m_i,0\}
$$

M5 labels:

$$
Z_i=\mathbf 1\{m_i>0\}
$$

$$
B_i=\mathbf 1\{m_i>m_{BE}\}
$$

Severity target for rows with `Z_i = 1`:

$$
y_i^+=
\log\left(1+\min\{m_i,C\}\right)
$$

The break-even label is scenario-dependent.

## 7. Model architecture

`HurdleState` contains four fitted estimators:

| Component | Estimator | Training rows | Target |
|---|---|---|---|
| Positive classifier | `HistGradientBoostingClassifier` | all | `Z_i` |
| Break-even classifier | `HistGradientBoostingClassifier` | all | `B_i` |
| Severity regressor | `HistGradientBoostingRegressor` | `Z_i = 1` only | `log1p(clipped markout)` |
| Direct regressor | `HistGradientBoostingRegressor` | all | M4 target |

M5 score:

$$
\widehat S_i^{M5}=
\widehat p_i\widehat\mu_i
$$

where:

$$
\widehat p_i=
\widehat{\Pr}(Z_i=1\mid X_i)
$$

and:

$$
\widehat\mu_i=
\operatorname{clip}
\left(\exp(\widehat y_i^+)-1,0,C\right)
$$

The break-even probability is a separate gate:

$$
\widehat q_i=
\widehat{\Pr}(B_i=1\mid X_i)
$$

No separate probability calibration or retransformation-bias correction is applied.

## 8. Training specification

Selected `medium` preset:

| Hyperparameter | Value |
|---|---:|
| Learning rate | 0.05 |
| Maximum iterations | 160 |
| Maximum leaf nodes | 31 |
| Minimum samples per leaf | 60 |
| L2 regularization | 1.0 |
| Maximum bins | 63 |
| Early stopping | disabled |
| Target clip | 100 bps |
| Notional weight power | 0.25 |

Sample weights:

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

Candidate grid:

| Parameter | Values |
|---|---|
| Horizon | `120`, `300`, `600` seconds |
| Model preset | `compact`, `medium` |
| Notional budget | `0.01`, `0.02`, `0.05`, `0.10` |
| Minimum net margin | `0`, `0.05`, `0.10` bps |
| Minimum break-even probability | `0`, `0.40`, `0.50`, `0.60` |
| Prediction multiplier | `1.0`, `1.25`, `1.50` |

## 9. Inference and policy procedure

### 9.1 Prediction

1. build `HurdleDayDataset`;
2. call both classifiers;
3. call the conditional severity regressor;
4. inverse-transform and clip severity;
5. calculate `probability_positive * conditional_positive_markout`;
6. retain `probability_break_even` for gating.

### 9.2 Scenario

```yaml
internalization_rate: 0.25
mitigation_efficiency: 0.50
protection_fraction: 0.125
action_cost_bps: 0.50
break_even_markout_bps: 4.00
```

If any scenario parameter changes, recompute the break-even threshold and retrain the break-even classifier.

### 9.3 P3 decision

Predicted net value:

$$
\widehat v_i^{M5}=
\rho\lambda\widehat p_i\widehat\mu_i-c
$$

Eligibility:

$$
\widehat v_i^{M5}\ge\delta
\quad\text{and}\quad
\widehat q_i\ge\tau
$$

Allocation:

1. rank eligible rows by predicted net value;
2. allocate full or fractional row notional;
3. stop at the daily notional budget;
4. compute scenario-adjusted realized value from future markouts.

## 10. Evaluation protocol

| Split | Dates | Allowed use |
|---|---|---|
| Train | 2025-01-06 to 2025-01-26 | Fit model parameters |
| Development | 2025-01-27 to 2025-02-02 | Select model and policy per horizon |
| Validation | 2025-02-03 to 2025-02-09 | Select one horizon |
| Final holdout | 2025-02-10 to 2025-02-16 | Reporting only |

Acceptance criteria:

$$
\overline V_{day}>0
$$

$$
R=
\overline V_{day}
-0.5\,\operatorname{sd}(V_{day})
>0
$$

and:

```text
positive days >= 5 / 7
```

Uncertainty is estimated with 5,000 paired bootstrap resamples of daily policy differences.

## 11. Selected configuration

| Market | Horizon | Preset | Budget | Minimum margin | Minimum P(BE) |
|---|---:|---|---:|---:|---:|
| BTCUSDT | 600 s | `medium` | 10% | 0.10 bps | 40% |
| ETHUSDT | 600 s | `medium` | 10% | 0.10 bps | 0% |

The selected prediction multiplier is stored in:

```text
targets.<symbol>.selected_final_candidate.policy_spec.prediction_multiplier
```

It must be read from the result artifact rather than inferred from the README.

## 12. Validated results

### 12.1 Final P3 metrics

| Metric | BTCUSDT | ETHUSDT |
|---|---:|---:|
| Aggregate net value, USDT/$1M | 12.86 | 24.76 |
| Mean daily net value, USDT/$1M | 9.25 | 20.08 |
| 95% interval versus P0 | [2.85, 18.05] | [11.52, 32.31] |
| Daily standard deviation | 10.62 | 14.77 |
| Worst day, USDT/$1M | -1.88 | 5.10 |
| Positive days | 85.7% | 100.0% |
| Affected notional | 9.93% | 10.00% |
| Captured adverse exposure | 17.21% | 16.20% |
| Benefit-cost ratio | 3.59 | 5.95 |
| Oracle-value capture | 26.6% | 28.6% |

### 12.2 Paired comparisons

| Market | Comparison | Mean daily difference | 95% interval | Decision |
|---|---|---:|---:|---|
| BTCUSDT | P3 minus P2 | +4.54 | [1.79, 7.06] | positive |
| BTCUSDT | P3 minus P1 | +1.56 | [-0.30, 3.44] | not established |
| ETHUSDT | P3 minus P2 | +3.50 | [-0.13, 7.47] | not established |
| ETHUSDT | P3 minus P1 | -2.06 | [-4.21, 0.24] | not established |

Approved interpretation:

- P3 is positive relative to no action on both final markets.
- P3 improves on P2 with positive paired evidence for BTCUSDT.
- P3 does not establish universal superiority over P1 or P2.

## 13. Artifact contract

Default result:

```text
/opt/airflow/data/real_market/results/hurdle_economic_policy.json
```

Top-level structure:

```text
configuration
targets
```

Per-target structure:

```text
development
validation
selected_final_candidate
status
final_test.daily
final_test.aggregate
final_test.oracle_capture_fraction
final_test.bootstrap
```

The JSON is the reporting source of truth for selected policy parameters and metrics. It does not serialize the four fitted estimators.

## 14. Repository integration

| Component | Path |
|---|---|
| Dataset, models, policies, selection, metrics | `src/revolut_app/real_market/experiments/hurdle_economic_policy.py` |
| Launcher | `scripts/run_hurdle_economic_policy.sh` |
| Human-readable result display | `scripts/show_hurdle_economic_policy.py` |
| Policy specification | `docs/decision_policies/P3_hurdle_economic.md` |
| Reporting loader | `src/revolut_app/analytics/load_research_reporting.py` |

## 15. Runbook

```bash
./scripts/run_hurdle_economic_policy.sh
```

Optional output override:

```bash
OUTPUT=/opt/airflow/data/real_market/results/hurdle_economic_policy.json \
  ./scripts/run_hurdle_economic_policy.sh
```

## 16. Tests and quality gates

Run:

```bash
pytest tests/unit/real_market/experiments/test_hurdle_economic_policy.py
```

Current tests cover:

- exact notional-budget allocation;
- predicted-net-value formula;
- break-even probability gating;
- profitable policy metrics;
- candidate rejection;
- stride and markout construction;
- direct-policy prediction selection.

Required additional gates before serving:

- exact 208-column feature schema;
- classifier class-order validation;
- calibration diagnostics;
- model serialization parity;
- scenario compatibility checks;
- inference-latency budget;
- missing-data fallback;
- deterministic final-candidate reconstruction.

## 17. Monitoring and retraining

### Model monitoring

- mean and quantiles of `probability_positive`;
- mean and quantiles of `probability_break_even`;
- conditional severity distribution;
- expected-positive-markout p95 and maximum;
- calibration by probability bin;
- target clipping rate;
- feature drift and non-finite rate.

### Policy monitoring

- eligible-event fraction;
- affected-notional fraction;
- captured-exposure fraction;
- net value per $1M;
- benefit-cost ratio;
- positive-day fraction;
- P3-minus-P1 and P3-minus-P2 daily differences;
- oracle-value capture.

### Retraining triggers

Retrain and issue a new model version when:

- feature schema or market universe changes;
- horizon or decision stride changes;
- scenario parameters change;
- break-even definition changes;
- sustained feature or score drift is observed;
- daily economic acceptance criteria fail.

Do not reuse the previous final holdout as a new untouched final period.

## 18. Known limitations

- Public Binance trades are a market proxy, not proprietary client flow.
- Internalization, mitigation, and action cost are assumptions.
- Probability outputs are not separately calibrated.
- Severity retransformation bias is not corrected.
- The final holdout contains seven daily clusters.
- The oracle uses future information and is diagnostic only.
- M5 captures less than one third of oracle scenario value.
- M5 does not dominate every alternative policy.
- Positive scenario value is not guaranteed executable or realized PnL.

## 19. References

- [Extended M5 theory](./M5_Theory.pdf)
- [Scikit-learn HistGradientBoostingClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
- [Scikit-learn HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)
- [Pinned implementation](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/hurdle_economic_policy.py)
