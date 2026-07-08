# System Architecture

ReDataX combines API services, batch ingestion, orchestration, analytical storage, and experiment runners.

## Components

| Component | Role |
|---|---|
| FastAPI | Transaction and FX quote service. |
| Airflow | ETL orchestration and scheduled workflows. |
| PostgreSQL | Operational storage. |
| MinIO | Object storage for raw and intermediate files. |
| ClickHouse | Analytical storage and experiment tables. |
| Metabase | BI dashboards. |
| Python CLIs | Reproducible experiment execution. |

## Data Flow

Synthetic and market data are ingested into storage, transformed into features, evaluated by experiment scripts, loaded into ClickHouse, and summarized in dashboards and reports.

