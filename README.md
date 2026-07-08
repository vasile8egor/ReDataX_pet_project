<div align="center">

# ReDataX

### Исследовательская платформа для оценки неблагоприятного отбора, рыночного потока и решений о вмешательстве

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.10.5-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-required-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![ClickHouse](https://img.shields.io/badge/ClickHouse-analytics-FFCC01?logo=clickhouse&logoColor=black)](https://clickhouse.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-service-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Market flow · adverse selection · multiscale features · decision policies · ClickHouse analytics · Metabase reporting**

</div>

> [!IMPORTANT]
> ReDataX is a research and educational project. It does not reproduce internal algorithms of Revolut, Binance, or any other financial institution. It is not a trading system and does not provide investment advice.

---

## 1. Project overview

**ReDataX** studies whether public market-flow data can be used to estimate short-horizon adverse-selection risk and support an economically constrained intervention policy.

The project does **not** try to predict the full future price path. Instead, it asks a narrower question:

> Given the current state of market flow, is a future adverse move likely and large enough to justify an intervention after accounting for action cost and notional budget?

The empirical part uses public Binance `aggTrades` data for:

- `BTCUSDT`;
- `ETHUSDT`.

These data are treated as a public proxy for market flow. They do not contain bank client flow, internal inventory, routing logic, execution quality, or proprietary hedging decisions. For that reason, all monetary results are reported as **scenario-adjusted potential protected value**, not realized bank profit and loss.

---

## 2. What the project demonstrates

ReDataX combines several layers:

| Layer | What it demonstrates |
|---|---|
| Research design | Adverse-selection problem statement, temporal validation, final holdout |
| Market data processing | Binance aggregate trades ingestion and feature construction |
| Machine learning | Model progression from baseline ranking to economic decision models |
| Decision policies | Conversion of predictions into constrained actions |
| Unit economics | Gross protected value, action cost, net value, break-even cost |
| Data engineering | PostgreSQL, ClickHouse, MinIO, Airflow, Docker Compose |
| Analytics | Gold-layer views and Metabase dashboards |
| Backend | FastAPI service for synthetic FX and transaction workflows |

The project is intentionally broader than a single notebook. It is structured as a small research platform: data ingestion, experiments, reporting tables, dashboards, documentation, and reproducibility flow are separated.

---

## 3. Core research idea

A financial platform may temporarily keep exposure after serving customer or market flow. If the price then moves against this exposure, the platform faces adverse-selection loss.

ReDataX models this as a decision problem:

```text
market flow state
        -> adverse-selection probability
        -> adverse-markout severity
        -> intervention decision
        -> scenario-adjusted protected value
```

The project uses multiscale flow features inspired by the idea of coarse-graining from statistical physics. This is not presented as a strict physical renormalization-group calculation. The analogy is used more modestly: individual trades are treated as microscopic events, while rolling flow features at several horizons describe the effective state of the market.

---

## 4. Model and policy structure

### 4.1 Models

| Model | Role | Status |
|---|---|---|
| `M0` | single-scale local baseline | baseline |
| `M1` | local multiscale model | accepted |
| `M1R` | local RG-flow diagnostic | diagnostic |
| `M2` | cross-market model without explicit pairwise interactions | accepted |
| `M3` | cross-market model with explicit pairwise interactions | rejected |
| `M4` | direct expected adverse-markout regression | economic baseline |
| `M5` | hurdle model: probability and conditional severity | final candidate |

The model path is not only a leaderboard. It is an experimental sequence: each model tests a concrete hypothesis about scale, cross-market state, interaction terms, or economic decision quality.

### 4.2 Policies

| Policy | Meaning | Deployable |
|---|---|---|
| `P0` | no action | yes |
| `P1` | probability-based budget policy | yes |
| `P2` | direct economic policy | yes |
| `P3` | hurdle economic policy | yes |
| `P4` | oracle upper bound using future information | no |

`P4` is used only as a diagnostic upper bound. It is not a real policy because it uses information that is known only after the forecast horizon.

---

## 5. Scenario assumptions

The current research version uses the following scenario:

| Parameter | Value |
|---|---:|
| Markets | BTCUSDT, ETHUSDT |
| Decision stride | 10 seconds |
| Candidate deployable horizons | 120, 300, 600 seconds |
| Selected horizon | 600 seconds |
| Internalization rate | 25% |
| Mitigation efficiency | 50% |
| Action cost | 0.50 bps |
| Break-even markout | 4.00 bps |
| Final notional budget | 10% |

These values are scenario assumptions. They are not estimates of any real financial institution.

---

## 6. Main research results

The current research version reports that the final hurdle policy `P3` produces positive scenario-adjusted value on the final holdout for both markets.

| Market | Final policy | Net value, USDT/$1M | Benefit/cost |
|---|---|---:|---:|
| BTCUSDT | `P3` | `+12.86` | `3.59` |
| ETHUSDT | `P3` | `+24.76` | `5.95` |

Interpretation:

- `P3` is positive versus no action on both final holdouts.
- `P3` is not claimed to dominate every alternative on every metric.
- The oracle gap remains material, so the model captures only part of the available scenario headroom.
- Results are conditional on the public market proxy, selected period, selected horizon, and scenario assumptions.

Detailed interpretation is provided in the research documentation and dashboards.

---

## 7. Dashboards

The project includes four Metabase dashboards exported as research artifacts.

| Dashboard | Main question |
|---|---|
| `ReDataX - FX Risk Decision Value` | Does the final policy generate positive decision value? |
| `ReDataX - Model Evolution` | Which research hypotheses improved or failed? |
| `ReDataX - Policy Economics and Capital Efficiency` | Where does net value come from? |
| `ReDataX - Validation, Robustness and Reproducibility` | Is the result stable and reproducible? |

Suggested artifact path:

```text
artifacts/research_v1_0/dashboards/
├── fx_risk_decision_value.pdf
├── model_evolution.pdf
├── policy_economics_and_capital_efficiency.pdf
└── validation_robustness_and_reproducibility.pdf
```

---

## 8. Documentation map

Root `README.md` is only the landing page. Detailed explanations are split across the documentation tree.

```text
docs/
├── research/
│   ├── 00_problem_statement.md
│   ├── 01_theoretical_framework.md
│   ├── 02_research_design.md
│   ├── 03_experimental_results.md
│   ├── 04_interpretation.md
│   └── 05_limitations.md
│
├── models/
│   ├── MODEL_REGISTRY.md
│   ├── M0_single_scale/
│   ├── M1_local_multiscale/
│   ├── M2_cross_market_rg_no_j/
│   ├── M3_cross_market_rg_with_j/
│   ├── M4_direct_value_regression/
│   └── M5_hurdle_economic_model/
│
├── ml/
│   ├── feature_engineering.md
│   ├── targets.md
│   ├── temporal_validation.md
│   ├── calibration.md
│   ├── model_selection.md
│   └── leakage_checklist.md
│
├── decision_policies/
│   ├── P0_no_action.md
│   ├── P1_probability_budget.md
│   ├── P2_direct_economic.md
│   ├── P3_hurdle_economic.md
│   ├── P4_oracle.md
│   └── unit_economics.md
│
├── analytics/
│   ├── metric_dictionary.md
│   ├── clickhouse_data_model.md
│   ├── metabase_dashboards.md
│   └── reporting_protocol.md
│
├── data/
│   ├── data_sources.md
│   ├── data_contracts.md
│   ├── lineage.md
│   └── binance_aggtrades.md
│
├── engineering/
│   ├── system_architecture.md
│   ├── experiment_runner.md
│   ├── deployment.md
│   └── troubleshooting.md
│
└── reports/
    ├── EXECUTIVE_SUMMARY.md
    └── FINAL_RESEARCH_REPORT.md
```

Recommended reading order for a first review:

1. [`docs/research/00_problem_statement.md`](docs/research/00_problem_statement.md)
2. [`docs/research/02_research_design.md`](docs/research/02_research_design.md)
3. [`docs/models/MODEL_REGISTRY.md`](docs/models/MODEL_REGISTRY.md)
4. [`docs/decision_policies/unit_economics.md`](docs/decision_policies/unit_economics.md)
5. [`docs/analytics/metabase_dashboards.md`](docs/analytics/metabase_dashboards.md)
6. [`docs/engineering/system_architecture.md`](docs/engineering/system_architecture.md)

---

## 9. System architecture

ReDataX uses a multi-service local stack.

```text
                 ┌────────────────────┐
                 │   Binance archives  │
                 │      aggTrades      │
                 └─────────┬──────────┘
                           │
                           ▼
┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐
│   MinIO      │   │   Airflow        │   │   Python runners  │
│ file layer   │◄──┤ orchestration    │──►│ experiments       │
└──────────────┘   └─────────────────┘   └─────────┬────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │ ClickHouse   │
                                            │ analytics    │
                                            └──────┬───────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │  Metabase    │
                                            │ dashboards   │
                                            └──────────────┘

┌──────────────┐   ┌─────────────────┐
│ PostgreSQL   │◄──┤ FastAPI service │
│ operational  │   │ synthetic FX    │
└──────────────┘   └─────────────────┘
```

Main services:

| Service | Role |
|---|---|
| FastAPI | synthetic FX and transaction API |
| PostgreSQL | operational storage |
| ClickHouse | analytical storage and reporting layer |
| MinIO | object/file storage |
| Airflow | workflow orchestration |
| Metabase | BI dashboards |
| Python runners | research experiments and artifact generation |

Detailed system design is documented in [`docs/engineering/system_architecture.md`](docs/engineering/system_architecture.md).

---

## 10. Repository structure

```text
ReDataX_pet_project/
├── dags/                 # Airflow DAGs
├── scripts/              # ingestion, experiments, reporting scripts
├── sql/
│   ├── bronze/           # raw PostgreSQL tables
│   ├── silver/           # typed views and transformations
│   ├── gold/             # analytical SQL
│   └── clickhouse/       # ClickHouse initialization
├── src/revolut_app/
│   ├── api_service/      # FastAPI application
│   ├── core/             # shared constants and configuration
│   ├── etl/              # ETL pipelines
│   ├── experiments/      # synthetic experiment logic
│   ├── fx_lab/           # FX simulation, pricing, risk, inventory
│   ├── generators/       # synthetic data generators
│   ├── loaders/          # database loaders
│   └── real_market/      # Binance ingestion and market-flow models
├── tests/                # unit and integration tests
├── analytics/            # analytical assets
├── artifacts/            # experiment outputs
├── docs/                 # research and engineering documentation
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 11. Quick start

### Requirements

- Git;
- Docker Engine;
- Docker Compose v2.

Recommended resources:

- 4 CPU;
- 8 GB RAM minimum;
- 12-16 GB RAM for heavier market experiments;
- at least 20 GB free disk space.

### Clone

```bash
git clone https://github.com/vasile8egor/ReDataX_pet_project.git
cd ReDataX_pet_project
```

### Prepare local folders

```bash
mkdir -p data logs metabase/plugins
```

On Linux:

```bash
printf 'AIRFLOW_UID=%s\n' "$(id -u)" > .env
```

### Build and initialize

```bash
docker compose build
docker compose up airflow-init
```

### Start the full local stack

```bash
docker compose --profile api up -d
```

### Check services

```bash
docker compose --profile api ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8123/ping
docker compose exec postgres_main pg_isready -U airflow
```

Expected API health response:

```json
{"status":"ok"}
```

---

## 12. Local service URLs

| Service | URL | Credentials |
|---|---|---|
| FastAPI Swagger | http://localhost:8000/docs | none |
| Airflow | http://localhost:8080 | `airflow` / `airflow` |
| Metabase | http://localhost:3001 | created on first login |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| ClickHouse HTTP | http://localhost:8123 | `default` / `default` |
| PostgreSQL | `localhost:5432` | `airflow` / `airflow` |

Detailed deployment notes are in [`docs/engineering/deployment.md`](docs/engineering/deployment.md).

---

## 13. Working with real market data

The main ingestion script accepts a date range and symbols:

```bash
scripts/ingest_binance_range.sh START_DATE END_DATE [SYMBOL ...]
```

Example:

```bash
chmod +x scripts/ingest_binance_range.sh

./scripts/ingest_binance_range.sh \
  2025-01-06 \
  2025-01-06 \
  BTCUSDT ETHUSDT ETHBTC
```

Check loaded rows in ClickHouse:

```bash
docker compose exec clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --query "
    SELECT
        trade_date,
        symbol,
        count() AS rows
    FROM raw.fact_real_market_agg_trades FINAL
    GROUP BY trade_date, symbol
    ORDER BY trade_date, symbol
  "
```

> [!IMPORTANT]
> Binance archives can be large. Do not commit the local `data/` directory.

More details are in [`docs/data/binance_aggtrades.md`](docs/data/binance_aggtrades.md).

---

## 14. Running experiments

Experiment scripts are located in `scripts/`.

Examples:

```bash
bash scripts/run_baseline_experiments.sh
bash scripts/run_current_observer_comparison.sh
bash scripts/run_hamiltonian_observer_normal_load.sh
bash scripts/run_hamiltonian_rg_diagnostic_b16.sh
```

Before running any experiment script, inspect it:

```bash
sed -n '1,240p' scripts/<script_name>.sh
```

Some scripts may assume preloaded data, a specific model version, or a specific artifact directory.

Experiment methodology is documented in:

- [`docs/research/02_research_design.md`](docs/research/02_research_design.md)
- [`docs/engineering/experiment_runner.md`](docs/engineering/experiment_runner.md)

---

## 15. Testing

Unit tests can be run inside the API image:

```bash
docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q /opt/airflow/tests
```

Syntax check:

```bash
docker compose --profile api run --rm \
  api \
  python -m compileall /opt/airflow/src
```

Integration tests require the stack to be running:

```bash
docker compose --profile api up -d

docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q \
  -o addopts="" \
  -m integration \
  /opt/airflow/tests
```

---

## 16. Known limitations

1. Binance `aggTrades` are a public market-flow proxy, not bank client flow.
2. The project does not observe real internal inventory, routing, hedging, or execution quality.
3. Scenario assumptions are fixed manually and are not estimated from proprietary data.
4. Reported values are not realized PnL.
5. Oracle policy uses future information and is not deployable.
6. Multiscale modeling is inspired by coarse-graining, but it is not a strict Wilsonian renormalization-group procedure.
7. Results are limited to the tested markets, period, horizons, and scenario assumptions.
8. The final holdout must not be reused for further tuning.

A fuller discussion is in [`docs/research/05_limitations.md`](docs/research/05_limitations.md).

---

## 17. Status

Research version `1.0` is suitable as a portfolio case study after the documentation tree is completed.

Current focus:

- finalize research documentation;
- align README, dashboards, and model cards;
- improve reproducibility notes;
- keep scenario assumptions and final holdout interpretation explicit.

---

## 18. Author

**Егор Васильев**

- GitHub: [@vasile8egor](https://github.com/vasile8egor)
- Repository: [ReDataX_pet_project](https://github.com/vasile8egor/ReDataX_pet_project)

The project was developed as an independent research and engineering case study combining data engineering, backend development, market-flow modeling, applied machine learning, analytics, and statistical-physics-inspired reasoning.

---

## 19. License

This project is distributed under the MIT License. See [`LICENSE`](LICENSE).
