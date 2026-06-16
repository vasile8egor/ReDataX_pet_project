# ReData: Revolut ELT Pipeline

## Описание

ReData - учебный data engineering проект, моделирующий ELT-платформу для обработки данных Revolut Open Banking API и синтетических банковских транзакций.

Проект построен вокруг Medallion Architecture:

- **Bronze**: сырые JSON payloads сохраняются в PostgreSQL JSONB.
- **Silver**: типизация и бизнес-маппинг выполняются SQL views поверх Bronze.
- **Gold**: аналитический слой выгружается в ClickHouse.

Airflow используется только для оркестрации. DAG-файлы остаются легковесными: они не содержат API-вызовов, SQL-строк, Pandas-трансформаций или тяжелой бизнес-логики. Вся логика пайплайнов, генераторов, API-клиента и загрузчиков вынесена в `src/revolut_app`.

Проект демонстрирует:

- интеграцию с Revolut Open Banking API;
- работу с OAuth/certificate-based API flow;
- загрузку raw API responses в MinIO;
- хранение raw данных в PostgreSQL JSONB;
- SQL-driven ELT без Pandas row-by-row mapping;
- загрузку Gold-слоя в ClickHouse;
- синтетическую генерацию аккаунтов и транзакций;
- модульную структуру Airflow-проекта.

## Стек Технологий

| Компонент | Назначение |
|---|---|
| Apache Airflow | Оркестрация DAG-пайплайнов |
| PostgreSQL | DWH для Bronze JSONB и Silver SQL views |
| ClickHouse | Gold serving layer для аналитических витрин |
| MinIO | S3-compatible raw landing zone для API JSON |
| Metabase | BI-интерфейс для визуализации и построения дашбордов |
| Docker Compose | Локальное развертывание инфраструктуры |
| Python | Генераторы, API-клиент, ETL pipelines |
| Revolut Open Banking API | Источник реальных банковских данных |
| SQL | DDL и ELT-трансформации |

Основные Python-библиотеки:

- `apache-airflow`
- `psycopg2-binary`
- `clickhouse-driver`
- `apache-airflow-providers-amazon`
- `requests`
- `PyJWT`
- `Faker`
- `numpy`

## Архитектура

```text
Revolut API / Synthetic Generators
              |
              v
      src/revolut_app/etl/pipelines
              |
              +--> MinIO raw JSON landing
              |
              +--> PostgreSQL Bronze JSONB
                         |
                         v
                PostgreSQL Silver SQL Views
                         |
                         v
                    ClickHouse Gold
```

## Структура Проекта

```text
revolut_pet_project/
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
├── certs/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

## Airflow DAGs

| DAG ID | Файл | Назначение |
|---|---|---|
| `revolut_bootstrap_history` | `dags/bootstrap_data.py` | Генерация исторических аккаунтов и транзакций в Bronze |
| `revolut_generate_new_accounts` | `dags/new_accounts_gen_dag.py` | Ежедневная генерация новых raw accounts |
| `revolut_generate_transactions` | `dags/transactions_gen_dag.py` | Ежедневная генерация raw transactions |
| `revolut_extract_api` | `dags/extract_dag.py` | Извлечение данных из Revolut API, сохранение в MinIO и Bronze |
| `revolut_load_gold` | `dags/gold_load.py` | Загрузка deduplicated Silver transactions в ClickHouse Gold |
| `revolut_master_pipeline` | `dags/master_orchestrator.py` | Оркестрация daily account generation, transaction generation и Gold load |

## Слои Данных

### Bronze

Raw JSONB tables в PostgreSQL:

```text
bronze.revolut_accounts_raw
bronze.revolut_transactions_raw
```

SQL:

```text
sql/bronze/accounts_raw.sql
sql/bronze/transactions_raw.sql
```

### Silver

SQL views поверх Bronze JSONB:

```text
silver.v_accounts
silver.v_transactions
```

SQL:

```text
sql/silver/v_accounts.sql
sql/silver/v_transactions.sql
```

### Gold

ClickHouse table:

```text
gold.fact_transactions
```

SQL:

```text
sql/clickhouse/init_gold.sql
sql/gold/load_fact_transactions.sql
```

## Инструкция По Развертыванию

### 1. Клонировать Репозиторий

```bash
git clone <repository-url>
cd revolut_pet_project
```

### 2. Подготовить Переменные Окружения

Для синтетических DAG-ов переменные Revolut не обязательны.

Для DAG-а `revolut_extract_api` нужно добавить Airflow Variables или environment variables:

```text
REVOLUT_CLIENT_ID
REVOLUT_FINANCIAL_ID
REVOLUT_PRIVATE_KEY_PATH
REVOLUT_TRANSPORT_CERT_PATH
REVOLUT_KID
REVOLUT_REDIRECT_URL
REVOLUT_REFRESH_TOKEN
```

Сертификаты для Revolut API должны быть доступны внутри Airflow container. В локальном проекте они ожидаются в `certs/`.

### 3. Собрать Docker Images

```bash
docker compose build
```

### 4. Запустить Инфраструктуру

```bash
docker compose up -d
```

### 5. Проверить Контейнеры

```bash
docker compose ps
```

Ожидаемые сервисы:

```text
airflow_webserver
airflow_scheduler
airflow_init
postgres_main
minio
clickhouse
metabase
```

### 6. Открыть Airflow

```text
http://localhost:8080
```

Логин и пароль по умолчанию:

```text
airflow / airflow
```

### 7. Открыть MinIO

```text
http://localhost:9001
```

Логин и пароль:

```text
minioadmin / minioadmin
```

### 8. Открыть Metabase

```text
http://localhost:3001
```

При первом запуске Metabase попросит создать пользователя и подключить источник данных.

Рекомендуемое подключение к PostgreSQL:

```text
Host: postgres_main
Port: 5432
Database: airflow
User: airflow
Password: airflow
```

Через PostgreSQL удобно анализировать Bronze/Silver:

```text
bronze.revolut_accounts_raw
bronze.revolut_transactions_raw
silver.v_accounts
silver.v_transactions
```

ClickHouse можно подключить к Metabase через community ClickHouse driver. Папка для плагинов уже примонтирована:

```text
metabase/plugins -> /plugins
```

После добавления ClickHouse driver `.jar` в `metabase/plugins` нужно перезапустить Metabase:

```bash
docker compose restart metabase
```

Параметры ClickHouse:

```text
Host: clickhouse
HTTP Port: 8123
Database: gold
User: default
Password: default
```

## Рекомендуемый Порядок Запуска DAG-ов

Для локального demo flow:

1. Запустить `revolut_bootstrap_history`.
2. Запустить `revolut_load_gold`.
3. Запустить `revolut_master_pipeline` для daily flow.

Для проверки реальной интеграции с Revolut API:

1. Настроить Revolut credentials и certificate paths.
2. Запустить `revolut_extract_api`.
3. Проверить raw JSON в MinIO bucket `raw`.
4. Запустить `revolut_load_gold`.

## Полезные Команды

Пересобрать Airflow images после изменения зависимостей:

```bash
docker compose build --no-cache airflow-webserver airflow-scheduler airflow-init
docker compose up -d --force-recreate
```

Посмотреть логи scheduler:

```bash
docker compose logs -f airflow-scheduler
```

Зайти в PostgreSQL:

```bash
docker compose exec postgres_main psql -U airflow -d airflow
```

Применить DDL для API transaction events:

```bash
docker compose exec postgres_main psql -U airflow -d airflow -f /sql/bronze/transaction_events_raw.sql
```

Зайти в ClickHouse:

```bash
docker compose exec clickhouse clickhouse-client
```

Посмотреть логи Metabase:

```bash
docker compose logs -f metabase
```

Остановить проект:

```bash
docker compose down
```

Остановить проект и удалить volumes:

```bash
docker compose down -v
```

## Примеры Запросов

### PostgreSQL: Проверить Bronze Accounts

```sql
SELECT
    COUNT(*) AS raw_accounts_count
FROM bronze.revolut_accounts_raw;
```

### PostgreSQL: Проверить Bronze Transactions

```sql
SELECT
    COUNT(*) AS raw_transactions_count
FROM bronze.revolut_transactions_raw;
```

### PostgreSQL: Посмотреть Пример Raw JSON Account

```sql
SELECT
    raw_id,
    payload,
    loaded_at
FROM bronze.revolut_accounts_raw
ORDER BY loaded_at DESC
LIMIT 5;
```

### PostgreSQL: Проверить Silver Accounts

```sql
SELECT
    account_id,
    currency,
    account_type,
    acquisition_channel,
    registration_datetime
FROM silver.v_accounts
ORDER BY registration_datetime DESC
LIMIT 10;
```

### PostgreSQL: Проверить Silver Transactions

```sql
SELECT
    transaction_id,
    account_id,
    amount,
    currency,
    tx_timestamp
FROM silver.v_transactions
ORDER BY tx_timestamp DESC
LIMIT 10;
```

### PostgreSQL: Daily Transaction Volume

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

### PostgreSQL: Top Accounts By Transaction Amount

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

### ClickHouse: Проверить Gold Transactions

```sql
SELECT
    COUNT(*) AS gold_transactions_count
FROM gold.fact_transactions;
```

### ClickHouse: Daily Gold Aggregation

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

### ClickHouse: Currency Breakdown

```sql
SELECT
    currency,
    count() AS transaction_count,
    sum(amount) AS total_amount
FROM gold.fact_transactions
GROUP BY currency
ORDER BY total_amount DESC;
```

## MinIO Object Layout

Raw API responses from `revolut_extract_api` are saved to bucket:

```text
raw
```

Expected object layout:

```text
accounts/{ds}/accounts.json
transactions/{ds}/{account_id}.json
```

## Архитектурные Принципы

- DAG-и содержат только Airflow orchestration.
- Бизнес-логика живет в `src/revolut_app`.
- API-клиент изолирован в `src/revolut_app/api`.
- Генераторы изолированы в `src/revolut_app/generators`.
- Loaders отвечают только за подключение и запись в target-системы.
- Raw data хранится в Bronze как JSONB.
- Silver строится SQL views, без Pandas mapping.
- Gold слой загружается в ClickHouse.
- SQL хранится в `sql/`, а не внутри DAG-файлов.

## Автор

Проект разработан как pet project для демонстрации навыков Data Engineering:

- Apache Airflow orchestration
- ELT и Medallion Architecture
- PostgreSQL JSONB
- SQL transformations
- ClickHouse analytics
- MinIO/S3-compatible storage
- API integration with OAuth/certificates
- Docker-based local infrastructure

Автор: **vasile8egor**
