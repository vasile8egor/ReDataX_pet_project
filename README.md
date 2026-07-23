<div align="center">

# ReDataX

### A research platform for market-flow intelligence and economically constrained risk decisions

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.10.5-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-required-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![ClickHouse](https://img.shields.io/badge/ClickHouse-analytics-FFCC01?logo=clickhouse&logoColor=black)](https://clickhouse.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-service-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Market microstructure | multiscale flow | adverse selection | decision policies | reproducible analytics**

</div>

> [!IMPORTANT]
> ReDataX is an independent research and educational project. It is not affiliated with Revolut or Binance, does not reproduce their internal algorithms, and is not a trading system or a source of investment advice.

## Contents

- [Why ReDataX](#why-redatax)
- [Inspired by Revolut's operating principles](#inspired-by-revoluts-operating-principles)
- [What the project contains](#what-the-project-contains)
- [Models and decision policies](#models-and-decision-policies)
- [Headline research snapshot](#headline-research-snapshot)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Quick start](#quick-start)
- [API examples](#api-examples)
- [Data workflows](#data-workflows)
- [Running experiments](#running-experiments)
- [Analytics](#analytics)
- [Testing](#testing)
- [Reproducibility and claim discipline](#reproducibility-and-claim-discipline)
- [Limitations](#limitations)

## Why ReDataX

A predictive score is not a decision.

In a financial system, a model matters only when its signal can be converted into an action whose expected benefit survives costs, capacity limits, and uncertainty. ReDataX explores that full path:

```text
raw events
    -> causal market-flow features
    -> adverse-selection probability and severity
    -> constrained intervention policy
    -> scenario-adjusted economic value
```

The main empirical question is deliberately narrow:

> Can public, short-horizon order-flow structure identify adverse moves that are large enough to justify an intervention after action cost and notional budget are taken into account?

ReDataX answers this question through a model sequence from `M0` to `M5`, temporal validation, explicit policy rules, unit economics, and reproducible reporting. Alongside the real-market study, the repository includes a synthetic FX laboratory for inventory-aware pricing, risk, hedging, and transaction workflows.

## Inspired by Revolut's operating principles

The way the project is built is inspired by four of Revolut's [public operating principles](https://www.revolut.com/en-US/careers/team/engineering-data/):

| Principle | How it appears in ReDataX |
|---|---|
| **Deliver WOW** | A coherent path from raw data and APIs to models, policy economics, and decision dashboards |
| **Get It Done** | A runnable Docker stack, executable experiment scripts, tests, and reproducibility checks |
| **Think Deeper** | Causal features, temporal holdouts, leakage controls, uncertainty, and economically meaningful metrics |
| **Never Settle** | A documented progression from `M0` to `M5`, including rejected hypotheses and remaining limitations |

This is inspiration from publicly stated principles, not a claim about Revolut's internal data, models, infrastructure, or decision processes.

## What the project contains

ReDataX has two connected research tracks.

| Track | Data | Main purpose |
|---|---|---|
| Synthetic FX laboratory | Generated customer requests, transactions, inventory states, and clustered flow | Study pricing, inventory pressure, stress regimes, hedging, and policy behavior in a controlled environment |
| Real-market microstructure study | Public Binance `aggTrades` for `BTCUSDT` and `ETHUSDT` | Test whether causal multiscale signed flow predicts short-horizon adverse selection and supports positive-value interventions |

These tracks share the same engineering spine:

- FastAPI for transaction and synthetic FX workflows;
- PostgreSQL for operational records;
- ClickHouse for analytical and reporting tables;
- Airflow for orchestration;
- MinIO for object storage;
- Python experiment runners for model and policy research;
- Metabase for decision-oriented analytics.

The repository is a compact research platform, not a single notebook. Ingestion, feature construction, experiments, economic evaluation, reporting, and documentation are kept separate so that each claim can be traced to an explicit method or artifact.

## Research scope and definitions

The real-market study uses Binance aggregate trades as a public proxy for market flow. It does not observe bank client flow, internal inventory, routing, fill quality, or proprietary hedging decisions.

| Term | Meaning in this project |
|---|---|
| Aggressive trade | An `aggTrades` event with buyer or seller aggression inferred from exchange fields |
| Signed flow | Buy-minus-sell volume, normalized within a causal time bucket |
| Multiscale state | A set of flow features computed over several backward-looking windows |
| Markout | Future price movement measured after a fixed decision horizon |
| Adverse markout | A future move against the side of the observed aggressive flow or retained exposure |
| Decision policy | A rule that converts model output and economic assumptions into action or no action |
| Protected value | Scenario-adjusted adverse-markout value that an intervention could mitigate |
| Oracle policy | A non-deployable upper bound that uses future information |

The multiscale construction is inspired by coarse-graining in statistical physics. It is an analogy for moving from microscopic trades to effective flow states across time scales, not a claim of implementing a strict Wilsonian renormalization-group procedure.

## Models and decision policies

### Model progression

| ID | Model | Hypothesis tested | Current role |
|---|---|---|---|
| `M0` | Single-scale | A fixed local window contains useful adverse-selection signal | Baseline |
| `M1` | Local multiscale | Several causal windows outperform a single scale | Supported |
| `M2` | Cross-market RG no-J | Synchronized states across markets add information | Candidate / supported by experiment |
| `M3` | Cross-market RG with-J | Explicit pairwise interactions add stable incremental value | Constrained / not supported as a stable improvement |
| `M4` | Direct value regression | Expected adverse-markout magnitude can be predicted directly | Economic baseline |
| `M5` | Hurdle economic | Separating event probability from conditional severity improves economic decisions | Final candidate |

The sequence is an experimental record, not just a leaderboard. A model remains documented when its hypothesis is rejected because negative results constrain the next design.

The canonical registry and per-model documentation are under [`docs/models/`](docs/models/), beginning with [`docs/models/MODEL_REGISTRY.md`](docs/models/MODEL_REGISTRY.md).

### Policy progression

| ID | Policy | Decision basis | Deployable |
|---|---|---|---|
| `P0` | No action | Reference outcome | Yes |
| `P1` | Probability budget | Ranked adverse-event probability under a notional budget | Yes |
| `P2` | Direct economic | Predicted value after intervention cost | Yes |
| `P3` | Hurdle economic | Event probability multiplied by conditional severity, net of cost | Yes |
| `P4` | Oracle upper bound | Realized future markout | No |

Model output and policy logic are intentionally separate. A better ranking metric does not automatically imply a better economic policy.

## Headline research snapshot

The current research version evaluates a 600-second decision horizon under a fixed scenario:

| Parameter | Value |
|---|---:|
| Markets | `BTCUSDT`, `ETHUSDT` |
| Decision stride | 10 seconds |
| Candidate horizons | 120, 300, 600 seconds |
| Selected horizon | 600 seconds |
| Internalization rate | 25% |
| Mitigation efficiency | 50% |
| Action cost | 0.50 bps |
| Break-even markout | 4.00 bps |
| Final notional budget | 10% |

Under those assumptions, the final hurdle policy `P3` reports positive scenario-adjusted value on both final holdouts:

| Market | Policy | Net value, USDT per $1M | Benefit / cost |
|---|---|---:|---:|
| `BTCUSDT` | `P3` | `+12.86` | `3.59` |
| `ETHUSDT` | `P3` | `+24.76` | `5.95` |

These figures are not realized bank PnL. They are conditional estimates for the selected markets, dates, horizon, notional budget, and manually specified unit-economics scenario. The oracle gap remains material, and the final holdout must not be reused for tuning.

See the [results](docs/research/03_results.md), [business interpretation](docs/research/04_business_interpretation.md), and [limitations](docs/research/05_limitations.md) before quoting these numbers.

## Architecture

```text
                               RESEARCH PLANE

  Binance archives      ingestion / features       model + policy runners
     aggTrades       ->   causal flow states    ->   M0-M5 and P0-P4
          |                       |                         |
          v                       v                         v
       local data              ClickHouse          reporting artifacts
          ^                       |                         |
          |                       +-------------> Metabase dashboards
        MinIO


                              APPLICATION PLANE

   client request  ->  FastAPI  ->  PostgreSQL
                         |
                         +-----> synthetic FX inventory, pricing,
                                 stress, hedging, and PnL services


                              ORCHESTRATION

                  Airflow coordinates ETL and data generation
```

| Component | Responsibility |
|---|---|
| `src/revolut_app/real_market` | Binance ingestion, flow features, and real-market experiments |
| `src/revolut_app/fx_lab` | Synthetic FX simulation, inventory, pricing, risk, and hedging |
| `src/revolut_app/api_service` | Transaction ingestion and FX API |
| `dags/` | Airflow workflows |
| `sql/` | PostgreSQL bronze/silver/gold and ClickHouse schemas |
| `scripts/` | Ingestion, experiments, reporting, and verification |
| `docs/` | Research, model, ML, policy, analytics, data, and engineering documentation |

For the detailed design, see [`docs/engineering/system_architecture.md`](docs/engineering/system_architecture.md).

## Documentation

The root README is the entry point. The research argument and technical contracts live in `docs/`.

> [!NOTE]
> The formal problem statement is in [`docs/research/00_problem_statement.md`](docs/research/00_problem_statement.md). Model documentation and the canonical `M0-M5` registry are in [`docs/models/`](docs/models/).

| Area | Start here | Contents |
|---|---|---|
| Research | [`00_problem_statement.md`](docs/research/00_problem_statement.md) | Problem, theory, experimental design, results, interpretation, limitations |
| Models | [`MODEL_REGISTRY.md`](docs/models/MODEL_REGISTRY.md) | Canonical model IDs and per-model documentation |
| ML protocol | [`docs/ml/README.md`](docs/ml/README.md) | Features, targets, temporal validation, calibration, selection, leakage |
| Decision policies | [`docs/decision_policies/README.md`](docs/decision_policies/README.md) | `P0-P4` and unit economics |
| Data | [`data_sources.md`](docs/data/data_sources.md) | Sources, contracts, lineage, Binance ingestion |
| Analytics | [`docs/analytics/README.md`](docs/analytics/README.md) | Metrics, ClickHouse reporting model, dashboards |
| Engineering | [`system_architecture.md`](docs/engineering/system_architecture.md) | Architecture, experiment runner, deployment, troubleshooting |
| Reports | [`EXECUTIVE_SUMMARY.md`](docs/reports/EXECUTIVE_SUMMARY.md) | Executive and final research reports |

Recommended review path:

1. [Problem statement](docs/research/00_problem_statement.md)
2. [Theoretical framework](docs/research/01_theoretical_framework.md)
3. [Experimental design](docs/research/02_experimental_design.md)
4. [Model registry](docs/models/MODEL_REGISTRY.md)
5. [Unit economics](docs/decision_policies/unit_economics.md)
6. [Research results](docs/research/03_results.md)
7. [Limitations](docs/research/05_limitations.md)

## Repository layout

```text
ReDataX_pet_project/
├── dags/                    # Airflow DAGs
├── scripts/                 # ingestion, experiments, reporting, verification
├── sql/
│   ├── bronze/              # operational raw tables
│   ├── silver/              # typed views and transformations
│   ├── gold/                # analytical SQL
│   └── clickhouse/          # ClickHouse initialization
├── src/revolut_app/
│   ├── api_service/         # FastAPI application
│   ├── etl/                 # ETL pipelines
│   ├── experiments/         # synthetic experiment logic
│   ├── fx_lab/              # FX simulation and decision services
│   ├── generators/          # synthetic data generators
│   ├── loaders/             # database loaders
│   └── real_market/         # market ingestion, features, models, policies
├── tests/                   # unit and integration tests
├── analytics/               # analytical assets
├── artifacts/               # experiment outputs
├── docs/                    # canonical project documentation
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## Quick start

### Prerequisites

- Git;
- Docker Engine;
- Docker Compose v2;
- 4 CPU and at least 8 GB RAM;
- 12-16 GB RAM for heavier market experiments;
- at least 20 GB of free disk space.

Linux, macOS, and Windows through WSL2 are the intended local environments.

### 1. Clone and prepare the workspace

```bash
git clone https://github.com/vasile8egor/ReDataX_pet_project.git
cd ReDataX_pet_project

mkdir -p data logs metabase/plugins
```

On Linux, map Airflow's container user to your local user:

```bash
printf 'AIRFLOW_UID=%s\n' "$(id -u)" > .env
```

### 2. Build and initialize

```bash
docker compose build
docker compose up airflow-init
docker compose --profile api up -d
```

The API profile also starts PostgreSQL, ClickHouse, Airflow, MinIO, and Metabase.

### 3. Initialize the transaction ingestion table

```bash
docker compose exec -T postgres_main \
  psql -U airflow -d airflow \
  < sql/bronze/transaction_events_raw.sql
```

### 4. Verify the stack

```bash
docker compose --profile api ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8123/ping
docker compose exec postgres_main pg_isready -U airflow
```

Expected API response:

```json
{"status":"ok"}
```

### Local services

| Service | URL or port | Local credentials |
|---|---|---|
| FastAPI Swagger UI | [http://localhost:8000/docs](http://localhost:8000/docs) | none |
| Airflow | [http://localhost:8080](http://localhost:8080) | `airflow` / `airflow` |
| Metabase | [http://localhost:3001](http://localhost:3001) | created at first login |
| MinIO Console | [http://localhost:9001](http://localhost:9001) | `minioadmin` / `minioadmin` |
| ClickHouse HTTP | `localhost:8123` | `default` / `default` |
| PostgreSQL | `localhost:5432` | `airflow` / `airflow` |

All listed credentials are local development defaults. Change them and add authentication, TLS, secret management, and network controls before adapting any component for a shared or production-like environment.

## API examples

Set a base URL once:

```bash
export REDATAX_API=http://localhost:8000
```

The complete interactive contract is available at `$REDATAX_API/docs`.

### Endpoint overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/events/transactions` | Idempotent transaction ingestion |
| `GET` | `/events/transactions/{transaction_id}` | Retrieve an ingested transaction |
| `POST` | `/fx/quote` | Preview or execute a synthetic FX quote |
| `POST` | `/fx/stress-shock` | Apply a volatility and hedge-capacity shock |
| `POST` | `/fx/simulate-day` | Run a clustered-flow day simulation |
| `POST` | `/fx/rg-flow` | Compute multiscale flow diagnostics |
| `POST` | `/fx/hedge-recommendation` | Request a hedge recommendation |
| `POST` | `/fx/execute-hedge` | Apply a synthetic hedge |
| `POST` | `/fx/policy-comparison` | Compare synthetic quote policies |
| `GET` | `/fx/risk-snapshot` | Inspect current inventory risk |
| `GET` | `/fx/pnl-snapshot` | Inspect current synthetic PnL state |

### Health

```bash
curl -sS "$REDATAX_API/health"
```

```json
{"status":"ok"}
```

### Ingest a transaction

```bash
curl -sS -X POST \
  "$REDATAX_API/events/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-demo-0001",
    "idempotency_key": "idem-demo-0001",
    "transaction_id": "txn-demo-0001",
    "account_id": "acc-demo-0001",
    "amount": 125.50,
    "currency": "EUR",
    "transaction_type": "card_payment",
    "category": "groceries",
    "merchant_name": "Demo Market",
    "created_at": "2026-06-30T10:00:00Z"
  }' | python -m json.tool
```

The first request is accepted. Repeating the same request demonstrates idempotency and returns the transaction as a duplicate rather than inserting it again.

```json
{
  "status": "duplicate",
  "transaction_id": "txn-demo-0001",
  "risk_score": 0.0,
  "risk_level": "low",
  "is_duplicate": true
}
```

The exact risk fields depend on the active rule service.

Retrieve the stored transaction:

```bash
curl -sS \
  "$REDATAX_API/events/transactions/txn-demo-0001" \
  | python -m json.tool
```

Supported transaction currencies are `EUR`, `GBP`, and `USD`. Transaction types are defined by the OpenAPI schema and include card payments, transfers, salary, cash withdrawal, fees, and refunds.

### Preview an FX quote

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/quote" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "customer-demo-001",
    "base_currency": "EUR",
    "quote_currency": "USD",
    "side": "buy",
    "amount": 1000.0,
    "segment": "retail",
    "channel": "app",
    "execute": false
  }' | python -m json.tool
```

The response includes the mid-rate, client rate, spread components, inventory pressure, and detected stress regime. With `execute: false`, the quote does not mutate inventory.

### Execute an FX quote

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/quote" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "customer-demo-002",
    "base_currency": "GBP",
    "quote_currency": "USD",
    "side": "sell",
    "amount": 2500.0,
    "segment": "premium",
    "channel": "app",
    "execute": true
  }' | python -m json.tool
```

Executed quotes update the synthetic inventory ledger. That ledger is held in the API process, so restarting the API resets it unless an experiment persists state through a separate path.

Inspect the resulting risk and PnL state:

```bash
curl -sS "$REDATX_API/fx/risk-snapshot" | python -m json.tool
curl -sS "$REDATAX_API/fx/pnl-snapshot" | python -m json.tool
```

### Apply a stress shock

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/stress-shock" \
  -H "Content-Type: application/json" \
  -d '{
    "volatility_multiplier": 2.0,
    "hedge_capacity_multiplier": 0.7
  }' | python -m json.tool
```

### Simulate a day of clustered FX flow

Use service defaults:

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/simulate-day" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
```

Run a reproducible simulation:

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/simulate-day" \
  -H "Content-Type: application/json" \
  -d '{
    "seed": 42,
    "reset_state": true,
    "amount_multiplier": 1.0,
    "max_snapshots": 200
  }' | python -m json.tool
```

## Data workflows

### Synthetic data with Airflow

List available DAGs:

```bash
docker compose exec airflow-webserver airflow dags list
```

Bootstrap synthetic history:

```bash
docker compose exec airflow-webserver \
  airflow dags trigger revolut_bootstrap_history
```

Run the master pipeline:

```bash
docker compose exec airflow-webserver \
  airflow dags trigger revolut_master_pipeline
```

Inspect recent runs:

```bash
docker compose exec airflow-webserver \
  airflow dags list-runs \
  --dag-id revolut_master_pipeline \
  --limit 10
```

The master DAG coordinates account generation, transaction generation, and the gold-layer load.

### Public Binance aggregate trades

The range-ingestion script accepts a start date, end date, and one or more symbols:

```bash
./scripts/ingest_binance_range.sh \
  2025-01-06 \
  2025-01-06 \
  BTCUSDT ETHUSDT ETHBTC
```

Downloaded files are mounted into the stack under `/opt/airflow/data/real_market/binance` and remain in the host's local `data/` directory.

Validate loaded rows in ClickHouse:

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

> [!WARNING]
> Exchange archives can be large. The local `data/` directory is intentionally excluded from version control.

See [`docs/data/binance_aggtrades.md`](docs/data/binance_aggtrades.md) for source semantics and ingestion details.

## Running experiments

Experiment entry points live in `scripts/`. Representative commands are grouped below.

### Baselines and observer studies

```bash
bash scripts/run_baseline_experiments.sh
bash scripts/run_current_observer_comparison.sh
bash scripts/run_hamiltonian_observer_normal_load.sh
bash scripts/run_hamiltonian_rg_diagnostic_b16.sh
```

### Economic policies and horizon analysis

```bash
bash scripts/run_hurdle_economic_policy.sh
bash scripts/run_oracle_horizon_scan.sh
```

### Reporting and verification

```bash
bash scripts/load_research_reporting.sh
bash scripts/verify_research_reporting.sh
```

Some runners expect preloaded data, a particular artifact version, or an existing reporting schema. Read the script and [`docs/engineering/experiment_runner.md`](docs/engineering/experiment_runner.md) before running a long experiment.

## Analytics

Research artifacts are loaded into ClickHouse and presented through Metabase. The reporting layer is organized around four questions:

| View | Question |
|---|---|
| FX Risk Decision Value | Does the selected policy create positive scenario-adjusted value? |
| Model Evolution | Which hypotheses improved the system, and which failed? |
| Policy Economics and Capital Efficiency | Where do protected value, action cost, and net value come from? |
| Validation, Robustness and Reproducibility | Is the result stable, temporally valid, and reproducible? |

Dashboard exports and their supporting documentation are in [`docs/analytics/`](docs/analytics/). These artifacts are evidence and diagnostic aids; the canonical definitions remain in the research, model, policy, and metric documentation.

For a local Metabase connection to ClickHouse, use:

| Setting | Value |
|---|---|
| Host | `clickhouse` |
| Port | `8123` |
| Database | `gold` |
| Username | `default` |
| Password | `default` |
| SSL | off |

## Testing

Run unit tests in the API image:

```bash
docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q /opt/airflow/tests
```

Check Python syntax:

```bash
docker compose --profile api run --rm \
  api \
  python -m compileall /opt/airflow/src
```

Run integration tests against a live stack:

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

## Reproducibility and claim discipline

The project follows several rules:

- feature windows are backward-looking and causal;
- model comparison uses temporally separated data;
- the final holdout is separated from development and tuning;
- model quality and policy value are reported separately;
- economic results include action cost and a notional budget;
- oracle results are labeled non-deployable;
- supported, exploratory, rejected, and historical claims are distinguished;
- each research run should record model version, feature set, symbols, horizons, data splits, calibration, policy thresholds, and metrics.

The detailed protocol is in:

- [`docs/ml/temporal_validation.md`](docs/ml/temporal_validation.md)
- [`docs/ml/leakage_checklist.md`](docs/ml/leakage_checklist.md)
- [`docs/analytics/reporting_protocol.md`](docs/analytics/reporting_protocol.md)
- [`docs/results/experiment_registry.md`](docs/results/experiment_registry.md)

## Limitations

- Binance `aggTrades` are a public market-flow proxy, not bank client flow.
- The project does not observe real internal inventory, routing, hedging, or execution quality.
- Scenario assumptions are manually specified rather than estimated from proprietary data.
- Reported protected value is not realized PnL.
- `P4` uses future information and cannot be deployed.
- Multiscale flow is inspired by coarse-graining but is not a strict physical RG calculation.
- Results are limited to the tested markets, periods, horizons, and cost assumptions.
- Positive holdout performance does not establish causal impact or production readiness.

Read the full discussion in [`docs/research/05_limitations.md`](docs/research/05_limitations.md).

## Operations

View service logs:

```bash
docker compose logs -f api
docker compose logs -f airflow-scheduler
docker compose logs -f clickhouse
```

Stop the stack without deleting data volumes:

```bash
docker compose --profile api down
```

For deployment details and common failure modes, see:

- [`docs/engineering/deployment.md`](docs/engineering/deployment.md)
- [`docs/engineering/troubleshooting.md`](docs/engineering/troubleshooting.md)

## Project status

ReDataX is a portfolio research and engineering project under active development. The current repository supports:

- a documented `M0-M5` research progression;
- deployable and oracle decision-policy comparisons;
- synthetic FX API and experiment workflows;
- public Binance data ingestion;
- ClickHouse reporting and Metabase analytics;
- unit and integration testing.

It should be treated as a reproducible case study, not a production trading or banking system.

## Author

**Egor Vasiliev**

- GitHub: [@vasile8egor](https://github.com/vasile8egor)
- Repository: [ReDataX_pet_project](https://github.com/vasile8egor/ReDataX_pet_project)

ReDataX was developed as an independent case study combining data engineering, backend development, market microstructure, applied machine learning, decision economics, analytics, and statistical-physics-inspired reasoning.

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE).
