---
model_id: M3
model_name: rg_with_j
model_version: research_v1_0
task: binary_classification
status: rejected
serving_status: research_only
owner: Egor Vasilev
framework: scikit-learn
source_commit: 2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe
---

# M3 - Cross-Market Model with Explicit Interactions

## 1. Purpose

M3 tests whether explicit same-scale pairwise flow interactions improve the accepted M2 cross-market classifier.

Primary use:

- controlled M2 feature ablation;
- documentation of a rejected modeling hypothesis;
- analysis of explicit cross-market interaction coefficients.

M3 must not be selected as the default M0-M3 model in the current research version.

## 2. Status and lineage

| Field | Value |
|---|---|
| Model ID | `M3` |
| Experiment name | `rg_with_j` |
| Status | Rejected |
| Predecessor | `M2` cross-market `rg_no_j` |
| Base feature count | 87 |
| Interaction feature count | 21 |
| Total feature count | 108 |
| Forecast horizon | 5 seconds |

The explicit interaction block did not provide a stable improvement across BTCUSDT and ETHUSDT. M2 remains the selected classifier.

## 3. Model contract

### 3.1 Prediction unit

One valid completed UTC second for one target market.

### 3.2 Supported targets and inputs

```python
TARGET_SYMBOLS = ("BTCUSDT", "ETHUSDT")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "ETHBTC")
```

### 3.3 Required input

| Input | Type | Shape | Description |
|---|---|---:|---|
| `phi` | `float64` | `(86400, 3)` | Signed second-level flow |
| `log_volume` | `float64` | `(86400, 3)` | Current log quote volume |
| `vwap` | `float64` | `(86400, 3)` | Second-level VWAP |
| `active` | `bool` | `(86400, 3)` | Activity mask |
| `coarse_phi` | `float64` | `(86400, 7, 3)` | Trailing multiscale flow |
| `target_symbol` | `str` | scalar | Supported target market |
| `horizon_seconds` | `int` | scalar | Positive horizon |

### 3.4 Output

| Output | Type | Range | Meaning |
|---|---|---|---|
| `score` | `float` | `[0, 1]` | Estimated probability of positive signed markout |
| `label` | `uint8` | `{0, 1}` | Evaluation target |
| `markout_bps` | `float` | unbounded | Realized signed markout |

## 4. Dataset contract

M3 uses exactly the same source rows and valid observation mask as M2.

Source:

```text
raw.fact_real_market_agg_trades
```

Required equality for the M2-M3 ablation:

```text
target symbols          identical
forecast horizon        identical
valid timestamps        identical
target labels           identical
temporal splits         identical
classifier family       identical
metric implementation   identical
```

Only the 21 interaction columns may differ.

Leakage controls are inherited from M2:

- trailing features only;
- future VWAP used only for the label;
- training-only preprocessing;
- development-only hyperparameter selection;
- frozen final-test evaluation.

## 5. Feature schema

M3 includes all 87 M2 columns and adds pairwise products.

Market pairs:

```python
PAIRS = (
    ("BTCUSDT", "ETHUSDT"),
    ("BTCUSDT", "ETHBTC"),
    ("ETHUSDT", "ETHBTC"),
)
```

Scale grid:

```python
SCALES_SECONDS = (1, 2, 4, 8, 16, 32, 64)
```

Interaction at pair `(s, r)` and scale `B`:

$$
J_{s,r,B}(t)=
\bar\phi_s^{(B)}(t)\bar\phi_r^{(B)}(t)
$$

Only equal-scale products are generated. Cross-scale combinations such as `B=8` by `B=64` are not included.

Feature groups:

| Group | Count |
|---|---:|
| M2 base columns | 87 |
| Three market pairs by seven scales | 21 |
| **Total** | **108** |

Interaction column naming:

```text
J[BTCUSDT,ETHUSDT,B=1]
J[BTCUSDT,ETHBTC,B=1]
J[ETHUSDT,ETHBTC,B=1]
...
```

Schema authority:

```python
dataset.feature_names["rg_with_j"]
```

## 6. Target definition

M3 uses the same target as M2:

$$
m_{A,H}(t)=
10^4\,d_A(t)
\frac{P_A(t+H)-P_A(t)}{P_A(t)}
$$

$$
Y_{A,H}(t)=\mathbf 1\{m_{A,H}(t)>0\}
$$

Final horizon:

```text
H = 5 seconds
```

## 7. Training specification

| Component | Configuration |
|---|---|
| Preprocessing | model-specific `StandardScaler` |
| Estimator | `SGDClassifier` |
| Loss | `log_loss` |
| Penalty | `l2` |
| Learning rate | `optimal` |
| Coefficient averaging | enabled |
| Random seed | `20260628` |
| Candidate `alpha` | `1e-5`, `1e-4`, `1e-3` |
| Selection metric | mean daily development AP |
| Selected `alpha` | `1e-3` |

M3 has its own scaler. Reusing the M2 scaler is invalid because feature dimensionality and ordering differ.

## 8. Inference procedure

Research batch inference:

1. load a complete synchronized `MarketDay`;
2. call `build_feature_matrices()`;
3. select `features["rg_with_j"]`;
4. verify 108 columns and exact feature-name order;
5. transform with the fitted M3 scaler;
6. call `classifier.predict_proba(X)[:, 1]`.

M3 is not approved for downstream policy selection. Use M2 for the accepted M0-M3 classifier.

## 9. Evaluation protocol

| Split | Dates | Purpose |
|---|---|---|
| Train | 2025-01-06 to 2025-01-19 | Fit candidate models |
| Development | 2025-01-20 to 2025-01-26 | Select `alpha` |
| Final test | 2025-01-27 to 2025-02-02 | Compare frozen M3 with M2 |

Metrics:

- ROC-AUC;
- Average Precision;
- Brier score;
- top-decile lift;
- paired daily bootstrap difference with 5,000 repetitions.

Primary acceptance requirement:

```text
stable positive M3-minus-M2 improvement across target markets
```

This requirement was not met.

## 10. Validated results

REAL-05B mean daily M3 minus M2 difference:

| Market | Metric | Difference | 95% interval |
|---|---|---:|---:|
| BTCUSDT | ROC-AUC | -0.000075 | [-0.000191, 0.000018] |
| BTCUSDT | Average Precision | +0.000259 | [0.000113, 0.000396] |
| BTCUSDT | Brier improvement | -0.000057 | [-0.000173, 0.000056] |
| BTCUSDT | Top-decile lift | +0.000382 | [-0.001617, 0.002497] |
| ETHUSDT | ROC-AUC | -0.000284 | [-0.000471, -0.000096] |
| ETHUSDT | Average Precision | -0.000229 | [-0.000428, -0.000032] |
| ETHUSDT | Brier improvement | -0.000132 | [-0.000196, -0.000077] |
| ETHUSDT | Top-decile lift | -0.000257 | [-0.001045, 0.000810] |

Decision:

```text
M3 rejected
M2 retained
```

The rejection applies to this specific equal-scale bilinear interaction block, not to every possible nonlinear cross-market model.

## 11. Artifact contract

Default output:

```text
/opt/airflow/data/real_market/results/coupled_rg_final.json
```

Relevant fields:

```text
targets.<symbol>.selected_alphas.rg_with_j
targets.<symbol>.development_mean_daily_ap.rg_with_j
targets.<symbol>.final_test.pooled.rg_with_j
targets.<symbol>.final_test.bootstrap.rg_with_j_minus_no_j
targets.<symbol>.raw_scale_coefficients.rg_with_j
```

The coefficient output includes both M2 base coefficients and named `J[...]` coefficients. The JSON is not a serialized serving bundle.

## 12. Repository integration

| Component | Path |
|---|---|
| Feature construction and training | `src/revolut_app/real_market/experiments/coupled_rg_final.py` |
| Reporting loader | `src/revolut_app/analytics/load_research_reporting.py` |
| Model registry | `docs/models/MODEL_REGISTRY.md` |
| Result registry | `docs/results/experiment_registry.md` |

## 13. Runbook

M1, M2, and M3 are trained and evaluated in one command:

```bash
docker compose exec api python -m \
  revolut_app.real_market.experiments.coupled_rg_final \
  --target-symbols BTCUSDT ETHUSDT \
  --horizon-seconds 5 \
  --alphas 0.00001 0.0001 0.001 \
  --train-start 2025-01-06 \
  --train-end 2025-01-19 \
  --development-start 2025-01-20 \
  --development-end 2025-01-26 \
  --final-test-start 2025-01-27 \
  --final-test-end 2025-02-02 \
  --bootstrap-samples 5000 \
  --output /opt/airflow/data/real_market/results/coupled_rg_final.json
```

## 14. Tests and quality gates

There is no dedicated `test_coupled_rg_final.py` at the pinned commit.

Required M3-specific tests:

- exactly 21 interaction columns;
- exactly 108 total columns;
- all three unordered market pairs;
- equal-scale-only construction;
- target-side cancellation identity;
- M2 and M3 valid-mask equality;
- deterministic coefficient extraction;
- no feature-name collisions.

Related test command:

```bash
pytest tests/unit/real_market/experiments/test_adverse_selection_oos.py
```

## 15. Monitoring and retraining

M3 is rejected and should not be monitored as an active model. If retained for research diagnostics, monitor:

- M3-minus-M2 daily AP;
- cross-market interaction feature drift;
- coefficient stability by pair and scale;
- non-finite and near-constant interaction columns.

Any new interaction family requires a new model version and a new untouched comparison period.

## 16. Known limitations

- Interaction form is restricted to bilinear equal-scale products.
- Nested windows produce correlated interaction columns.
- L2-regularized coefficients are not independently identifiable effects.
- Cross-market association does not establish causal coupling.
- Only two target markets and seven final-test days were evaluated.
- Aggregate trades omit order-book, inventory, fill, fee, and hedge information.

## 17. References

- [Extended M3 theory](./M3_Theory.pdf)
- [Scikit-learn SGDClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.SGDClassifier.html)
- [Pinned implementation](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/coupled_rg_final.py)
