# ReDataX — Synthetic Banking Data Platform

ReDataX is a data engineering pet project that simulates a banking transaction system and processes the generated data through a local Medallion ELT architecture.

The project focuses on three ideas:

1. Synthetic generation of realistic banking accounts and transactions.
2. Modular Airflow orchestration with business logic moved outside DAG files.
3. Analytical data processing through PostgreSQL Bronze/Silver layers and ClickHouse Gold.

The project is designed as a local data platform for demonstrating data engineering skills: data generation, batch loading, ELT modeling, Airflow orchestration, PostgreSQL JSONB storage, ClickHouse analytics, and Docker-based infrastructure.

---

## 1. Project Overview

ReDataX models a simplified banking data platform.

The system generates synthetic banking accounts and transactions, stores raw payloads in PostgreSQL Bronze tables, exposes typed SQL views in Silver, and loads deduplicated analytical data into ClickHouse Gold.

The project also contains a Revolut Open Banking API integration path, but the main demo flow can be run fully locally with synthetic data.

### Main goals

* Simulate account registration over time.
* Generate transaction histories with daily and hourly activity patterns.
* Store raw banking payloads as JSONB.
* Move transformations from Python/Pandas into SQL-based Silver views.
* Load analytical transaction data into ClickHouse.
* Keep Airflow DAGs slim and move business logic into reusable Python modules.
* Measure and optimize historical bootstrap performance.

---

## 2. Tech Stack

| Component      | Role                                         |
| -------------- | -------------------------------------------- |
| Python         | Generators, ETL pipelines, loaders           |
| Apache Airflow | DAG orchestration                            |
| PostgreSQL     | Bronze JSONB storage and Silver SQL views    |
| ClickHouse     | Gold serving layer for analytical queries    |
| MinIO          | S3-compatible raw landing zone for API JSON  |
| Docker Compose | Local infrastructure                         |
| SQL            | DDL, ELT transformations, analytical queries |
| Faker / NumPy  | Synthetic data generation                    |
| psycopg2       | Batched PostgreSQL loading                   |

---

## 3. Architecture

```text
Synthetic Generators / Revolut API
              |
              v
src/revolut_app/etl/pipelines
              |
              +--> MinIO raw landing zone
              |
              +--> PostgreSQL Bronze JSONB
                         |
                         v
                PostgreSQL Silver SQL Views
                         |
                         v
                  ClickHouse Gold Layer
```

### Medallion layers

| Layer  | Storage              | Description                                    |
| ------ | -------------------- | ---------------------------------------------- |
| Bronze | PostgreSQL JSONB     | Raw account and transaction payloads           |
| Silver | PostgreSQL SQL views | Typed and normalized analytical views          |
| Gold   | ClickHouse           | Serving layer for fast analytical aggregations |

The project intentionally keeps Bronze close to the source format. Raw payloads are inserted as JSONB and transformed later through SQL views. This makes the ingestion layer simple and allows schema evolution without rewriting the loading code.

---

## 4. Data Generation Model

The main feature of the project is not just data loading, but synthetic generation of banking behavior.

The generator creates two main entities:

1. Accounts
2. Transactions

The generated data is designed to resemble a simplified banking product: users register over time, receive account metadata, perform card payments, transfers, salary transactions, refunds, withdrawals, and fees.

---

## 5. Account Generation

Account generation is handled by:

```text
src/revolut_app/generators/accounts_gen.py
```

Each generated account contains:

* account ID;
* currency;
* account type;
* account subtype;
* IBAN-like account identification;
* sort-code-like account number;
* customer profile;
* acquisition channel;
* registration timestamp;
* initial deposit;
* churn risk;
* lifetime value segment.

### Daily account flow

The generator creates a different number of accounts depending on the day type:

* weekdays: higher expected registration volume;
* weekends: lower expected registration volume.

This is modeled through a Poisson distribution.

Conceptually:

```text
daily_accounts_count ~ Poisson(lambda)
```

where lambda is higher for weekdays and lower for weekends.

This gives the project a more realistic time dimension: the number of newly registered users changes from day to day instead of being a fixed constant.

### Account payload example

```json
{
  "AccountId": "d3f8...",
  "Currency": "GBP",
  "AccountType": "Personal",
  "AccountSubType": "CurrentAccount",
  "Customer": {
    "FirstName": "John",
    "LastName": "Smith",
    "Email": "john.smith@example.com",
    "Phone": "447..."
  },
  "Acquisition": {
    "Channel": "organic",
    "RegistrationDatetime": "2026-06-01T14:25:10",
    "InitialDeposit": 350.25
  },
  "Scoring": {
    "ChurnRisk": "medium",
    "LifetimeValue": "high"
  }
}
```

---

## 6. Transaction Generation

Transaction generation is handled by:

```text
src/revolut_app/generators/transactions_gen.py
```

The transaction generator simulates several transaction types:

| Transaction type  | Meaning                             |
| ----------------- | ----------------------------------- |
| card_payment      | Card purchases                      |
| internal_transfer | Transfer between generated accounts |
| bank_transfer_out | Outgoing external bank transfer     |
| bank_transfer_in  | Incoming external bank transfer     |
| salary            | Salary-like incoming payment        |
| cash_withdrawal   | ATM withdrawal                      |
| fee               | Bank fee                            |
| refund            | Merchant refund                     |

Each transaction contains:

* transaction ID;
* account ID;
* source account;
* target account;
* external counterparty;
* counterparty type;
* amount;
* currency;
* direction;
* transaction type;
* status;
* timestamp;
* merchant name;
* category.

---

## 7. MCMC-Based Activity Profile

The hourly distribution of transactions is generated using a Metropolis-style MCMC procedure.

The project defines a target 24-hour activity distribution. This distribution describes when users are more likely to perform transactions during the day.

Instead of assigning transaction hours uniformly, the generator samples hours according to the learned activity intensity.

Conceptually:

```text
target_intensity = normalized 24-hour activity distribution
current_intensity = target_intensity copy

for each MCMC iteration:
    propose a new 24-hour intensity vector
    compute current energy
    compute proposed energy
    accept the proposal if:
        proposed energy is lower
        or random probability passes Metropolis criterion
```

The energy function measures the distance between the current intensity and the target profile:

```text
E = sum((current_intensity - target_intensity)^2)
```

The Metropolis criterion allows the model to accept not only better states, but sometimes worse states too. This prevents the generator from being completely deterministic and gives the synthetic data a more natural distribution.

After the activity profile is computed, it is reused during historical generation instead of being recalculated for every day. This was one of the bootstrap optimizations.

---

## 8. Transaction Amount Model

Transaction amounts are generated using lognormal distributions.

This is useful because financial transaction amounts are usually not normally distributed. Most transactions are small or medium-sized, while large transactions are rarer but still possible.

Different transaction types use different distribution parameters.

Examples:

| Transaction type  | Typical behavior                            |
| ----------------- | ------------------------------------------- |
| card_payment      | Smaller frequent payments                   |
| internal_transfer | Medium transfers                            |
| bank_transfer_out | Larger external transfers                   |
| salary            | Large incoming payments with lower variance |
| fee               | Small fixed-like payments                   |
| refund            | Small or medium incoming payments           |

This makes the generated data better suited for analytical dashboards than purely random values.

---

## 9. Internal Transfers and Contact Book

For internal transfers, the generator builds a contact book between generated accounts.

Each account receives a small list of likely contacts. When an internal transfer is generated, the target account is selected mostly from this contact book.

This creates a simple network effect:

* some users repeatedly transfer money to known contacts;
* internal transfers are not completely random;
* transaction data can later be used for network-style analytics.

Conceptually:

```text
account_id -> [contact_account_1, contact_account_2, ...]
```

When choosing an internal transfer target:

```text
80% probability: choose from known contacts
20% probability: choose from all available accounts
```

---

## 10. Historical Bootstrap Pipeline

The historical bootstrap pipeline generates several months of account and transaction history.

Pipeline file:

```text
src/revolut_app/etl/pipelines/history.py
```

Airflow DAG:

```text
dags/bootstrap_data.py
```

The pipeline:

1. Initializes database schemas and tables.
2. Creates account and transaction generators.
3. Runs the MCMC activity model once.
4. Iterates over the historical date range.
5. Generates daily account batches.
6. Generates transactions for a rolling sample of accounts.
7. Buffers accounts and transactions in memory.
8. Flushes data to PostgreSQL Bronze tables in batches.

Default historical bootstrap configuration:

| Parameter                   |       Value |
| --------------------------- | ----------: |
| Historical period           |    6 months |
| Account sample size         |         500 |
| Flush batch size            | 50,000 rows |
| PostgreSQL insert page size |  5,000 rows |

---

## 11. Bootstrap Performance Optimization

The historical bootstrap pipeline was optimized because the first version was too slow and too tightly coupled to Airflow DAG files.

### Before optimization

Main bottlenecks:

* generation and loading logic lived inside the DAG file;
* part of the mapping was done in Python/Pandas before loading;
* transactions were inserted through less efficient insert mechanisms;
* MCMC activity profile was recalculated inside the daily loop;
* data was flushed in large calendar blocks, increasing memory and heartbeat risks.

### After optimization

Changes:

* moved historical generation logic to `src/revolut_app/etl/pipelines/history.py`;
* moved PostgreSQL loading into `PostgresLoader`;
* replaced row-wise / executemany-style inserts with `psycopg2.extras.execute_values`;
* inserted JSONB rows through batched multi-row insert;
* increased batch buffer to 50,000 rows;
* configured `execute_values` with `page_size=5000`;
* moved MCMC calculation outside the daily loop;
* removed Pandas mapping from the critical path;
* moved typing and transformation logic to SQL Silver views.

### Measured results

| Run date   |   Period | Accounts loaded | Transactions loaded | Duration |      Throughput |
| ---------- | -------: | --------------: | ------------------: | -------: | --------------: |
| 2026-06-09 | 6 months |           1,508 |           4,946,561 |   ~4m52s | ~16.9k rows/sec |
| 2026-06-08 | 6 months |           1,534 |           4,959,839 |   ~4m49s | ~17.2k rows/sec |

Approximate improvement:

| Metric                 |  Before |  After |
| ---------------------- | ------: | -----: |
| Runtime                | ~12 min | ~4m50s |
| Speedup                |       — |  ~2.5x |
| Runtime reduction      |       — |   ~60% |
| Transactions processed |     ~5M |    ~5M |

---

## 12. Slim DAG Design

One of the architectural goals was to keep Airflow DAGs lightweight.

Airflow is used only for orchestration. DAG files should not contain:

* SQL strings;
* API business logic;
* Pandas transformations;
* data generation internals;
* database loading implementation details.

Instead, these parts live in:

```text
src/revolut_app/
```

### Refactoring result

| DAG file                |    Before |    After | Reduction |
| ----------------------- | --------: | -------: | --------: |
| bootstrap_data.py       | 140 lines | 14 lines |      ~90% |
| new_accounts_gen_dag.py |  91 lines | 16 lines |      ~82% |
| transactions_gen_dag.py |  72 lines | 18 lines |      ~75% |
| extract_dag.py          | 113 lines | 33 lines |      ~71% |

This makes DAGs easier to test, read, and maintain.

---

## 13. Airflow DAGs

| DAG ID                          | File                           | Purpose                                                                     |
| ------------------------------- | ------------------------------ | --------------------------------------------------------------------------- |
| `revolut_bootstrap_history`     | `dags/bootstrap_data.py`       | Generate historical accounts and transactions into Bronze                   |
| `revolut_generate_new_accounts` | `dags/new_accounts_gen_dag.py` | Generate daily new raw accounts                                             |
| `revolut_generate_transactions` | `dags/transactions_gen_dag.py` | Generate daily raw transactions                                             |
| `revolut_extract_api`           | `dags/extract_dag.py`          | Extract data from Revolut API, save to MinIO and Bronze                     |
| `revolut_load_gold`             | `dags/gold_load.py`            | Load deduplicated Silver transactions into ClickHouse Gold                  |
| `revolut_master_pipeline`       | `dags/master_orchestrator.py`  | Orchestrate daily account generation, transaction generation, and Gold load |

---

## 14. Project Structure

```text
ReDataX_pet_project/
├── dags/
│   ├── bootstrap_data.py
│   ├── extract_dag.py
│   ├── gold_load.py
│   ├── master_orchestrator.py
│   ├── new_accounts_gen_dag.py
│   └── transactions_gen_dag.py
├── sql/
│   ├── bronze/
│   │   ├── accounts_raw.sql
│   │   └── transactions_raw.sql
│   ├── silver/
│   │   ├── v_accounts.sql
│   │   └── v_transactions.sql
│   ├── gold/
│   │   └── load_fact_transactions.sql
│   └── clickhouse/
│       └── init_gold.sql
├── src/revolut_app/
│   ├── api/
│   ├── core/
│   ├── etl/
│   │   ├── pipelines/
│   │   └── support/
│   ├── generators/
│   └── loaders/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

---

## 15. Local Deployment

### 1. Clone repository

```bash
git clone https://github.com/vasile8egor/ReDataX_pet_project.git
cd ReDataX_pet_project
```

### 2. Build Docker images

```bash
docker compose build
```

### 3. Start infrastructure

```bash
docker compose up -d
```

### 4. Check containers

```bash
docker compose ps
```

Expected services:

```text
airflow_webserver
airflow_scheduler
airflow_init
postgres_main
minio
clickhouse
```

### 5. Open Airflow

```text
http://localhost:8080
```

Default credentials:

```text
airflow / airflow
```

### 6. Open MinIO

```text
http://localhost:9001
```

Default credentials:

```text
minioadmin / minioadmin
```

---

## 16. Recommended Demo Flow

For local synthetic data demo:

1. Start the infrastructure.
2. Open Airflow.
3. Run `revolut_bootstrap_history`.
4. Run `revolut_load_gold`.
5. Query PostgreSQL Silver views and ClickHouse Gold table.
6. Open Metabase dashboards if configured.

For daily flow:

1. Run `revolut_master_pipeline`.
2. Check generated accounts.
3. Check generated transactions.
4. Check updated Gold layer.

For real Revolut API extraction:

1. Configure Revolut credentials and certificates.
2. Run `revolut_extract_api`.
3. Check raw JSON in MinIO.
4. Load Gold layer.

---

## 17. Useful Commands

Rebuild Airflow images after dependency changes:

```bash
docker compose build --no-cache airflow-webserver airflow-scheduler airflow-init
docker compose up -d --force-recreate
```

Watch scheduler logs:

```bash
docker compose logs -f airflow-scheduler
```

Connect to PostgreSQL:

```bash
docker compose exec postgres_main psql -U airflow -d airflow
```

Connect to ClickHouse:

```bash
docker compose exec clickhouse clickhouse-client
```

Stop containers:

```bash
docker compose down
```

Stop containers and remove volumes:

```bash
docker compose down -v
```

---

## 18. Example SQL Queries

### PostgreSQL: Bronze account count

```sql
SELECT COUNT(*) AS raw_accounts_count
FROM bronze.revolut_accounts_raw;
```

### PostgreSQL: Bronze transaction count

```sql
SELECT COUNT(*) AS raw_transactions_count
FROM bronze.revolut_transactions_raw;
```

### PostgreSQL: Silver transactions sample

```sql
SELECT
    transaction_id,
    account_id,
    amount,
    currency,
    tx_timestamp,
    transaction_type,
    merchant_name,
    category
FROM silver.v_transactions
ORDER BY tx_timestamp DESC
LIMIT 10;
```

### PostgreSQL: Daily transaction volume

```sql
SELECT
    tx_timestamp::DATE AS tx_date,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM silver.v_transactions
GROUP BY tx_timestamp::DATE
ORDER BY tx_date DESC
LIMIT 30;
```

### PostgreSQL: Top accounts by transaction amount

```sql
SELECT
    account_id,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM silver.v_transactions
GROUP BY account_id
ORDER BY total_amount DESC
LIMIT 10;
```

### ClickHouse: Gold transaction count

```sql
SELECT COUNT(*) AS gold_transactions_count
FROM gold.fact_transactions;
```

### ClickHouse: Daily Gold aggregation

```sql
SELECT
    toDate(tx_timestamp) AS tx_date,
    count() AS transaction_count,
    sum(amount) AS total_amount
FROM gold.fact_transactions
GROUP BY tx_date
ORDER BY tx_date DESC
LIMIT 30;
```

### ClickHouse: Currency breakdown

```sql
SELECT
    currency,
    count() AS transaction_count,
    sum(amount) AS total_amount
FROM gold.fact_transactions
GROUP BY currency
ORDER BY total_amount DESC;
```

---

## 19. Suggested Metabase Dashboard

The project can be documented with a Metabase dashboard to make the generated data easier to understand.

Recommended dashboard sections:

### 1. Bootstrap Performance

Charts:

* Historical bootstrap runtime by run date.
* Transactions loaded by run date.
* Throughput rows/sec by run date.
* Accounts loaded by run date.

Purpose:

Show that the pipeline is measurable and optimized, not just implemented.

### 2. Transaction Activity

Charts:

* Daily transaction count over time.
* Daily transaction amount over time.
* Hourly transaction distribution.
* Heatmap: day of week vs hour of day.

Purpose:

Show that generation produces time-dependent behavioral patterns.

### 3. Transaction Mix

Charts:

* Transaction count by transaction type.
* Transaction amount by transaction type.
* Incoming vs outgoing transaction share.
* Card payment categories breakdown.

Purpose:

Show that the generator creates heterogeneous banking behavior.

### 4. Account Base

Charts:

* New accounts by day.
* Accounts by acquisition channel.
* Accounts by churn risk.
* Accounts by lifetime value segment.
* Initial deposit distribution.

Purpose:

Show how synthetic customers are distributed across acquisition and scoring dimensions.

### 5. Top Entities

Charts:

* Top accounts by transaction count.
* Top accounts by transaction amount.
* Top merchants by transaction amount.
* Top categories by card payment volume.

Purpose:

Show that the generated data supports practical analytical questions.

---

## 20. Dashboard Screenshot Ideas

Recommended screenshots for README:

```text
docs/images/metabase_daily_transactions.png
docs/images/metabase_hourly_activity.png
docs/images/metabase_transaction_type_mix.png
docs/images/metabase_bootstrap_performance.png
docs/images/metabase_top_accounts.png
```

Suggested README layout:

```md
## Metabase Dashboard

### Daily Transaction Volume

![Daily Transaction Volume](docs/images/metabase_daily_transactions.png)

### Hourly Activity Profile

![Hourly Activity Profile](docs/images/metabase_hourly_activity.png)

### Transaction Type Mix

![Transaction Type Mix](docs/images/metabase_transaction_type_mix.png)

### Bootstrap Performance

![Bootstrap Performance](docs/images/metabase_bootstrap_performance.png)
```

---

## 21. What This Project Demonstrates

ReDataX demonstrates the following data engineering skills:

* synthetic data generation;
* MCMC-based behavioral simulation;
* Airflow DAG orchestration;
* Slim DAG architecture;
* modular Python pipeline design;
* PostgreSQL JSONB ingestion;
* SQL-based Silver transformations;
* ClickHouse analytical serving layer;
* batched PostgreSQL loading with `execute_values`;
* local infrastructure with Docker Compose;
* benchmark-driven optimization;
* dashboard-oriented analytical modeling.

---

## 22. Author

Created by Egor Vasilev as a data engineering pet project.

GitHub: https://github.com/vasile8egor






































