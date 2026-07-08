<div align="center">

# ReDataX

### Платформа для моделирования банковских и рыночных потоков, управления FX-риском и многомасштабного анализа adverse selection

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.10.5-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-required-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Синтетическая FX-платформа · Inventory-aware pricing · Hawkes-like event flow · ClickHouse analytics · RG-inspired multiscale modelling · Binance aggTrades**

</div>

> [!IMPORTANT]
> ReDataX является исследовательским и учебным проектом. Он не воспроизводит внутренние алгоритмы Revolut, Binance или иной финансовой организации, не является торговой системой и не предоставляет инвестиционных рекомендаций.

---

## Содержание

- [О проекте](#о-проекте)
- [Основные возможности](#основные-возможности)
- [Архитектура](#архитектура)
- [Технологический стек](#технологический-стек)
- [Исследовательская модель](#исследовательская-модель)
- [Основные результаты](#основные-результаты)
- [Структура репозитория](#структура-репозитория)
- [Развёртывание](#развёртывание)
- [Проверка установленной системы](#проверка-установленной-системы)
- [Примеры API-запросов](#примеры-api-запросов)
- [Работа с Apache Airflow](#работа-с-apache-airflow)
- [Загрузка реальных данных Binance](#загрузка-реальных-данных-binance)
- [Запуск экспериментов](#запуск-экспериментов)
- [Тестирование](#тестирование)
- [Остановка и сброс окружения](#остановка-и-сброс-окружения)
- [Устранение неполадок](#устранение-неполадок)
- [Ограничения проекта](#ограничения-проекта)
- [Документация](#документация)
- [Автор](#автор)
- [Лицензия](#лицензия)

---

# О проекте

**ReDataX** - модульная data-платформа, объединяющая два взаимосвязанных исследовательских контура.

### 1. Синтетический банковский и FX-контур

Система генерирует поток клиентских запросов на обмен валюты, поддерживает внутреннее состояние валютного инвентаря и сравнивает несколько политик формирования клиентского спреда:

- `naive` - базовая политика без учёта текущей позиции;
- `inventory_aware` - политика, реагирующая на направление и величину инвентарного давления;
- `platform` - компромиссная политика между контролем риска и качеством клиентской цены.

Для генерации кластеризованной активности применяется дискретная Hawkes-like модель. Состояние системы может анализироваться через Hamiltonian observer, режимы `calm`, `elevated`, `stress` и набор инвентарных метрик.

### 2. Эмпирический контур рыночной микроструктуры

Платформа загружает публичные архивы Binance `aggTrades`, восстанавливает сторону агрессора, строит причинные признаки направленного потока и проверяет модели краткосрочного adverse selection.

Исследовательская последовательность включает:

1. single-scale baseline;
2. локальную multiscale-модель;
3. RG-inspired признаки перехода между масштабами;
4. синхронное cross-market состояние BTCUSDT, ETHUSDT и ETHBTC;
5. явные попарные взаимодействия между рыночными полями;
6. out-of-time validation и bootstrap по торговым дням.

Полное математическое обоснование вынесено в [теоретический отчёт](docs/theory/ReDataX_theory_revised.pdf).

---

# Основные возможности

## Data Engineering

- контейнеризированное окружение из нескольких сервисов;
- оркестрация ETL и генераторов через Apache Airflow;
- разделение операционного и аналитического хранения;
- загрузка исторических Binance `aggTrades`;
- пакетная обработка больших событийных таблиц;
- Bronze / Silver / Gold логика данных;
- воспроизводимые экспериментальные CLI и shell-скрипты;
- сохранение raw-артефактов, snapshots и аналитических результатов.

## Backend и API

- FastAPI-сервис для приёма транзакционных событий;
- идемпотентная обработка событий;
- rule-based risk scoring;
- расчёт FX-котировок;
- preview и execution режимы котировки;
- получение состояния инвентарного риска;
- стресс-шоки;
- запуск синтетической дневной симуляции;
- Swagger/OpenAPI документация.

## Моделирование

- генерация клиентских FX-запросов;
- Hawkes-like кластеризация потока;
- inventory-aware pricing;
- Hamiltonian observer;
- temporal coarse-graining;
- multiscale order-flow features;
- cross-market feature construction;
- логистическая классификация adverse selection;
- day-cluster bootstrap;
- анализ observed dollar markout exposure.

## Аналитика

- ClickHouse-витрины;
- Metabase dashboards;
- расчёт PnL, acceptance, stress-time и inventory pressure;
- сравнение политик на одинаковом событийном наборе;
- out-of-time абляции моделей;
- экспорт результатов в JSON и CSV.

---

# Архитектура

![Логическая архитектура ReDataX](docs/figures/redatax_architecture.png)

Платформа построена по принципу polyglot persistence: каждый тип хранения решает собственную задачу.

## Основные потоки данных

1. Синтетические генераторы создают аккаунты, транзакции и FX-запросы.
2. Публичные Binance-архивы загружаются в файловый слой, валидируются и записываются в ClickHouse.
3. FastAPI принимает транзакционные события и FX-запросы.
4. PostgreSQL хранит операционные записи, конфигурации и события.
5. MinIO используется как файловый слой.
6. ClickHouse хранит таблицы собыитй, snapshots, признаки и результаты аналитики.
7. Metabase читает аналитические витрины и используется для EDA и dashboards.

---

# Технологический стек

| Компонент | Назначение |
|---|---|
| **Python** | бизнес-логика, генераторы, ETL, API, эксперименты |
| **FastAPI** | REST API |
| **Apache Airflow 2.10.5** | оркестрация |
| **PostgreSQL 15** | операционное хранение |
| **ClickHouse** | аналитическое хранение |
| **MinIO** | объектное хранение |
| **Metabase** | BI и исследовательская аналитика |
| **NumPy** | численные вычисления |
| **scikit-learn** | модели и метрики |
| **Pydantic** | схемы API |
| **psycopg** | PostgreSQL client |

---

# Исследовательская модель

## Нормированное поле направленного потока

Для рынка \(i\) и временного окна \(B\) поле определяется как

\[
\phi_i^{(B)}(t)=
\frac{V_{i,B}^{+}(t)-V_{i,B}^{-}(t)}
     {V_{i,B}^{+}(t)+V_{i,B}^{-}(t)+\varepsilon}.
\]

Здесь \(V^+\) и \(V^-\) - объёмы агрессивных покупок и продаж. Значение поля лежит в диапазоне \([-1,1]\).

В проекте используются масштабы:

\[
B\in\{1,2,4,8,16,32,64\}\text{ секунд}.
\]

## Иерархия моделей

| Модель | Смысл |
|---|---|
| `M0` | признаки одного фиксированного масштаба |
| `M1` | признаки целевого рынка на нескольких масштабах |
| `M2` | `M1` и корреляции между соседними масштабами |
| `M_cross` / `RG-noJ` | синхронные признаки BTCUSDT, ETHUSDT и ETHBTC без явных pairwise products |
| `M_J` / `RG-J` | cross-market модель с членами \(\phi_i^{(B)}\phi_j^{(B)}\) |

## Аналогии, используемые в проекте

Терминология статистической физики используется как способ организовать модель:

- сделка рассматривается как микроскопическое событие;
- дисбаланс - как поле;
- временное усреднение - как coarse-graining;
- pairwise products - как феноменологические взаимодействия;
- Hamiltonian observer - как скор напряжённости состояния.

---

# Основные результаты

## 1. Multiscale против single-scale

Локальная multiscale-модель `M1` устойчиво превзошла single-scale baseline `M0` на out-of-time данных BTCUSDT и ETHUSDT для горизонтов 1 и 5 секунд.

Основной вывод:

> Направленный поток на нескольких временных масштабах содержит информацию, отсутствующую в одном фиксированном окне.

## 2. Простые RG-inspired преобразования

Добавление конечных разностей и скейлинга признаков поверх `M1` не дало общего устойчивого прироста.

Основной вывод:

> Простые преобразования масштабов в значительной степени избыточны относительно исходного multiscale feature space.

## 3. Cross-market состояние

На untouched final holdout синхронное состояние BTCUSDT, ETHUSDT и ETHBTC улучшило Average Precision относительно локальной модели:

| Target | \(\Delta AP\) | 95% CI | Положительные дни |
|---|---:|---:|---:|
| BTCUSDT | +0.01879 | [+0.01676; +0.02129] | 7/7 |
| ETHUSDT | +0.01120 | [+0.00892; +0.01385] | 7/7 |

## 4. Явные \(J\)-взаимодействия

Pairwise interaction terms дали:

- небольшой AP-only прирост для BTCUSDT;
- отсутствие общего выигрыша по всем метрикам.

Поэтому финальной практической спецификацией выбрана более простая модель:

\[
\boxed{M_{\mathrm{cross}}\equiv RG\text{-}noJ}
\]

## 5. Dollar markout capture

`M1` захватывала больше observed adverse-selection exposure, чем `M0`, при одинаковой доле выбранных сделок. Однако бинарный toxicity score не был оптимизирован под величину долларового убытка, поэтому этот анализ не интерпретируется как доказательство реального PnL.

---

# Структура репозитория

```text
ReDataX_pet_project/
├── dags/                 # Airflow DAG
├── scripts/              # ingestion и experiment runners
├── sql/
│   ├── bronze/           # raw PostgreSQL tables
│   ├── silver/           # typed views / transformations
│   ├── gold/             # analytical SQL
│   └── clickhouse/       # ClickHouse initialization
├── src/revolut_app/
│   ├── api/              # legacy / supporting API modules
│   ├── api_service/      # FastAPI application
│   ├── core/             # common constants and configuration
│   ├── etl/              # ETL pipelines
│   ├── experiments/      # synthetic experiment logic
│   ├── fx_lab/           # FX simulation, pricing, risk, inventory
│   ├── generators/       # synthetic data generators
│   ├── loaders/          # database loaders
│   └── real_market/      # Binance ingestion and real-market models
├── tests/                # unit and integration tests
├── analytics/            # analytical assets
├── artifacts/            # experiment artifacts
├── metabase/             # Metabase plugins and assets
├── docs/                 # theory, figures, results
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

# Развёртывание

## 1. Требования

### Обязательные

- Git;
- Docker Engine;
- Docker Compose v2;

Проверка:

```bash
git --version
docker --version
docker compose version
```

### Рекомендуемые ресурсы

Полный стек включает Airflow, PostgreSQL, ClickHouse, MinIO, Metabase и FastAPI.

Рекомендуется:

- 4 CPU;
- 8 GB RAM минимум;
- 12-16 GB RAM для тяжёлых real-market экспериментов;
- не менее 20 GB свободного диска;
- Linux, macOS или Windows с WSL2.

## 2. Используемые порты

| Сервис | Host port | Назначение |
|---|---:|---|
| FastAPI | `8000` | API и Swagger |
| Airflow | `8080` | Airflow UI |
| PostgreSQL | `5432` | PostgreSQL |
| ClickHouse HTTP | `8123` | HTTP API |
| ClickHouse native | `9000` | native protocol |
| MinIO Console | `9001` | web console |
| MinIO S3 API | `9002` | S3-compatible API |
| Metabase | `3001` | BI web interface |


## 3. Клонирование

```bash
git clone https://github.com/vasile8egor/ReDataX_pet_project.git
cd ReDataX_pet_project
```

## 4. Подготовка локальных каталогов

```bash
mkdir -p data logs metabase/plugins
```

На Linux задайте UID текущего пользователя для Airflow-контейнеров:

```bash
printf 'AIRFLOW_UID=%s\n' "$(id -u)" > .env
```

Проверка:

```bash
cat .env
```

На Windows вне WSL можно оставить значение по умолчанию:

```text
AIRFLOW_UID=50000
```

## 5. Сборка образа

```bash
docker compose build
```

## 6. Инициализация Airflow

```bash
docker compose up airflow-init
```

Airflow создаёт локального администратора:

```text
username: airflow
password: airflow
```

## 7. Запуск полного стека

API находится в отдельном Compose profile, поэтому используйте `--profile api`.

```bash
docker compose --profile api up -d
```

Для первой сборки одной командой:

```bash
docker compose --profile api up -d --build
```

Без `--profile api` сервис FastAPI не будет запущен.

## 8. Проверка контейнеров

```bash
docker compose --profile api ps
```

Ожидаемые сервисы:

```text
api
postgres_main
airflow_webserver
airflow_scheduler
minio
clickhouse
metabase
```

## 9. Инициализация PostgreSQL-схем проекта

Airflow создаёт собственные metadata tables, но бизнес-схемы `bronze`, `silver` и `gold` должны быть применены отдельно.

Минимум для transaction ingestion API:

```bash
docker compose exec -T postgres_main \
  psql -U airflow -d airflow \
  < sql/bronze/transaction_events_raw.sql
```

Основные Bronze-таблицы:

```bash
docker compose exec -T postgres_main \
  psql -U airflow -d airflow \
  < sql/bronze/accounts_raw.sql

docker compose exec -T postgres_main \
  psql -U airflow -d airflow \
  < sql/bronze/transactions_raw.sql
```

SQL-файлы Silver и Gold применяйте в порядке зависимостей, указанном в соответствующих DAG и SQL-модулях. Не выполняйте все файлы произвольным glob-порядком в production-подобном окружении.

## 10. Проверка ClickHouse

`sql/clickhouse/init_gold.sql` подключён к стандартному init-каталогу контейнера и выполняется при создании нового ClickHouse volume.

Проверка:

```bash
curl -fsS http://localhost:8123/ping
```

Ожидаемый ответ:

```text
Ok.
```

Проверить базы:

```bash
docker compose exec clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --query "SHOW DATABASES"
```

> [!NOTE]
> Init-скрипт ClickHouse выполняется только при первоначальной инициализации пустого volume. После изменения SQL потребуется применить миграцию вручную либо пересоздать volume.

## 11. Проверка API

```bash
curl -fsS http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Swagger UI:

```text
http://localhost:8000/docs
```

OpenAPI schema:

```text
http://localhost:8000/openapi.json
```

## 12. Адреса сервисов

| Сервис | URL | login/password |
|---|---|---|
| FastAPI Swagger | http://localhost:8000/docs | не требуются |
| Airflow | http://localhost:8080 | `airflow` / `airflow` |
| Metabase | http://localhost:3001 | создаются при первом входе |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| ClickHouse HTTP | http://localhost:8123 | `default` / `default` |
| PostgreSQL | `localhost:5432` | `airflow` / `airflow` |


---

# Проверка установленной системы

Выполните последовательно:

```bash
docker compose --profile api ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8123/ping
docker compose exec postgres_main pg_isready -U airflow
```

Проверка импорта приложения:

```bash
docker compose exec api \
  python -c "from revolut_app.api_service.main import app; print(app.title, app.version)"
```

Проверка доступных маршрутов:

```bash
curl -fsS http://localhost:8000/openapi.json \
  | python -m json.tool \
  | less
```

Логи:

```bash
docker compose logs --tail=100 api
docker compose logs --tail=100 airflow-webserver
docker compose logs --tail=100 airflow-scheduler
docker compose logs --tail=100 clickhouse
```

---

# Примеры API-запросов

Базовый адрес:

```bash
export REDATAX_API=http://localhost:8000
```

## 1. Health check

```bash
curl -sS "$REDATAX_API/health"
```

Ответ:

```json
{
  "status": "ok"
}
```

## 2. Приём транзакционного события

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
  }'
```

Пример ответа:

```json
{
  "status": "accepted",
  "transaction_id": "txn-demo-0001",
  "risk_score": 0.0,
  "risk_level": "low",
  "is_duplicate": false
}
```

Точные `risk_score` и `risk_level` зависят от rule-based risk service.

### Проверка идемпотентности

Повторите тот же запрос с тем же `idempotency_key`.

Ожидается:

```json
{
  "status": "duplicate",
  "transaction_id": "txn-demo-0001",
  "risk_score": 0.0,
  "risk_level": "low",
  "is_duplicate": true
}
```

## 3. Получение транзакционного события

```bash
curl -sS \
  "$REDATAX_API/events/transactions/txn-demo-0001" \
  | python -m json.tool
```

## 4. Предварительный расчёт FX-котировки

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
  }' \
  | python -m json.tool
```

Поддерживаемые валюты:

```text
EUR
GBP
USD
```

Поддерживаемые стороны:

```text
buy
sell
```

Поддерживаемые сегменты:

```text
retail
premium
business
```

Ключевые поля ответа:

```json
{
  "quote_id": "...",
  "mid_rate": 1.0,
  "client_rate": 1.0,
  "components": {
    "base_spread_bps": 0.0,
    "inventory_penalty_bps": 0.0,
    "liquidity_penalty_bps": 0.0,
    "regime_penalty_bps": 0.0,
    "total_spread_bps": 0.0
  },
  "inventory_pressure": {
    "EUR": 0.0,
    "GBP": 0.0,
    "USD": 0.0
  },
  "regime": "calm",
  "executed": false
}
```

Числа выше приведены только как форма ответа, а не как гарантированный результат.

## 5. Исполнение FX-запроса

Параметр `"execute": true` применяет операцию к in-memory inventory ledger процесса API:

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
  }' \
  | python -m json.tool
```

> [!NOTE]
> Текущее состояние FX ledger находится в памяти API-процесса. Перезапуск контейнера сбрасывает это состояние, если оно предварительно не сохранено отдельным experiment/persistence path.

## 6. Снимок риска

```bash
curl -sS \
  "$REDATAX_API/fx/risk-snapshot" \
  | python -m json.tool
```

Ответ содержит:

- текущий regime;
- давление по валютам;
- позиции;
- лимиты;
- utilization;
- hedge capacity;
- funding cost;
- market volatility;
- поле `phi`.

## 7. Стресс-шок

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/stress-shock" \
  -H "Content-Type: application/json" \
  -d '{
    "volatility_multiplier": 2.0,
    "hedge_capacity_multiplier": 0.7
  }' \
  | python -m json.tool
```

## 8. Синтетическая дневная симуляция

Все поля имеют значения по умолчанию:

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/simulate-day" \
  -H "Content-Type: application/json" \
  -d '{}' \
  | python -m json.tool
```

Пример с фиксированным seed:

```bash
curl -sS -X POST \
  "$REDATAX_API/fx/simulate-day" \
  -H "Content-Type: application/json" \
  -d '{
    "seed": 42,
    "reset_state": true,
    "amount_multiplier": 1.0,
    "max_snapshots": 200
  }' \
  | python -m json.tool
```

Актуальные границы параметров всегда проверяйте в Swagger:

```text
http://localhost:8000/docs
```

---

# Работа с Apache Airflow

## Доступ

```text
URL:      http://localhost:8080
Username: airflow
Password: airflow
```

## Основные DAG

| DAG | Назначение |
|---|---|
| `revolut_bootstrap_history` | историческая bootstrap-загрузка |
| `revolut_generate_new_accounts` | генерация аккаунтов |
| `revolut_generate_transactions` | генерация транзакций |
| `revolut_load_gold` | загрузка аналитического Gold-слоя |
| `revolut_master_pipeline` | последовательный master workflow |

Проверка из CLI:

```bash
docker compose exec airflow-webserver airflow dags list
```

Запуск bootstrap:

```bash
docker compose exec airflow-webserver \
  airflow dags trigger revolut_bootstrap_history
```

Запуск master pipeline:

```bash
docker compose exec airflow-webserver \
  airflow dags trigger revolut_master_pipeline
```

Проверка последних запусков:

```bash
docker compose exec airflow-webserver \
  airflow dags list-runs \
  --dag-id revolut_master_pipeline \
  --limit 10
```

Просмотр task logs удобнее выполнять через Airflow UI.

---

# Загрузка реальных данных Binance

## Диапазон дат

Скрипт принимает:

```text
scripts/ingest_binance_range.sh START_DATE END_DATE [SYMBOL ...]
```

Пример для одного дня и трёх инструментов:

```bash
chmod +x scripts/ingest_binance_range.sh

./scripts/ingest_binance_range.sh \
  2025-01-06 \
  2025-01-06 \
  BTCUSDT ETHUSDT ETHBTC
```

Пример диапазона:

```bash
./scripts/ingest_binance_range.sh \
  2025-01-06 \
  2025-01-10 \
  BTCUSDT ETHUSDT
```

Скрипт:

1. скачивает и проверяет архивы через `smoke_cli`;
2. запускает ClickHouse ingestion через `ingest_cli`;
3. загружает данные batch-размером `50000`;
4. повторяет неудачную дневную загрузку.

Настройка retries:

```bash
export BINANCE_INGEST_DAY_ATTEMPTS=6
export BINANCE_INGEST_DAY_RETRY_SLEEP_SECONDS=60
```

Локальный каталог внутри контейнера:

```text
/opt/airflow/data/real_market/binance
```

На host он соответствует:

```text
./data/real_market/binance
```

## Проверка загруженных данных

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
> Архивы Binance могут занимать значительный объём. Не добавляйте каталог `data/` в Git.

---

# Запуск экспериментов

Готовые сценарии находятся в `scripts/`.

## Baseline experiments

```bash
bash scripts/run_baseline_experiments.sh
```

## Observer comparison

```bash
bash scripts/run_current_observer_comparison.sh
```

## Hamiltonian observer

```bash
bash scripts/run_hamiltonian_observer_normal_load.sh
```

## RG diagnostic

```bash
bash scripts/run_hamiltonian_rg_diagnostic_b16.sh
```

Перед запуском любого скрипта:

```bash
sed -n '1,240p' scripts/<script_name>.sh
```

Это важно, поскольку экспериментальные скрипты могут:

- предполагать заранее загруженные данные;
- записывать результаты в конкретный каталог;
- использовать определённую версию модели;
- быть привязаны к исторической ветке эксперимента.

Raw result artifacts рекомендуется хранить в:

```text
docs/results/raw/
```

Графики должны строиться программно из зафиксированных JSON/CSV, а не переноситься вручную.

---

# Тестирование

`pyproject.toml` по умолчанию исключает integration tests.

## Unit tests в одноразовом контейнере

API-образ содержит зависимости, но каталог `tests/` не смонтирован постоянно. Запустите:

```bash
docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q /opt/airflow/tests
```

## Конкретный файл

```bash
docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q \
  /opt/airflow/tests/unit/path/to/test_file.py
```

## Integration tests

Сначала запустите сервисы:

```bash
docker compose --profile api up -d
```

Затем:

```bash
docker compose --profile api run --rm \
  -v "$PWD/tests:/opt/airflow/tests:ro" \
  api \
  pytest -q \
  -o addopts="" \
  -m integration \
  /opt/airflow/tests
```

## Проверка синтаксиса

```bash
docker compose --profile api run --rm \
  api \
  python -m compileall /opt/airflow/src
```

---

# Настройка Metabase

Откройте:

```text
http://localhost:3001
```

При первом запуске создайте локального администратора.

## ClickHouse connection

Используйте значения внутри Docker network:

```text
Host:     clickhouse
Port:     8123
Database: gold
Username: default
Password: default
SSL:      disabled
```

## PostgreSQL connection

```text
Host:     postgres_main
Port:     5432
Database: airflow
Username: airflow
Password: airflow
```

Для аналитических dashboards предпочтителен ClickHouse. PostgreSQL следует использовать для проверки операционного и raw-состояния, а не для тяжёлых OLAP-запросов.

---

# Остановка и сброс окружения

## Остановка без удаления данных

```bash
docker compose --profile api down
```

Named volumes сохраняются.

## Повторный запуск

```bash
docker compose --profile api up -d
```

## Полный сброс

```bash
docker compose --profile api down -v
```

> [!CAUTION]
> `down -v` удаляет PostgreSQL, ClickHouse, MinIO и Metabase volumes. Данные будут потеряны.

## Удаление локальных real-market файлов

```bash
rm -rf data/real_market
```

## Обновление после `git pull`

```bash
git pull
docker compose --profile api down
docker compose build
docker compose --profile api up -d
```

При изменении schema SQL примените миграции отдельно. Перезапуск контейнера не изменяет уже существующий named volume автоматически.

---

# Устранение неполадок

## `api` отсутствует в `docker compose ps`

Причина: API находится в Compose profile.

Решение:

```bash
docker compose --profile api up -d api
```

## Ошибка `mount path must be absolute`

Проверьте `.git` volume:

```yaml
- ./.git:/opt/airflow/.git:ro
```

## Permission denied в `logs/` или `data/`

Linux:

```bash
printf 'AIRFLOW_UID=%s\n' "$(id -u)" > .env
mkdir -p logs data
sudo chown -R "$(id -u):0" logs data
```

Не используйте `chmod -R 777` как постоянное решение.

## Airflow UI недоступен

```bash
docker compose ps -a airflow-init
docker compose logs --tail=200 airflow-init
docker compose logs --tail=200 airflow-webserver
```

`airflow-init` должен завершиться успешно.

## Transaction endpoint возвращает PostgreSQL error

Проверьте таблицу:

```bash
docker compose exec postgres_main \
  psql -U airflow -d airflow \
  -c '\d bronze.transaction_events_raw'
```

Если таблица отсутствует:

```bash
docker compose exec -T postgres_main \
  psql -U airflow -d airflow \
  < sql/bronze/transaction_events_raw.sql
```

## ClickHouse init не применился

Init-скрипты выполняются только для пустого volume.

Проверка:

```bash
docker compose logs --tail=200 clickhouse
```

Локальная полная переинициализация ClickHouse удалит данные:

```bash
docker compose --profile api down
docker volume ls | grep clickhouse
```

Удаляйте volume только осознанно.

## Metabase не видит ClickHouse

Проверьте:

1. наличие ClickHouse driver в `metabase/plugins`;
2. host `clickhouse`, а не `localhost`;
3. HTTP port `8123`;
4. здоровье ClickHouse:

```bash
docker compose exec metabase \
  sh -c 'wget -qO- http://clickhouse:8123/ping || true'
```

## Порт уже занят

Определите процесс:

```bash
ss -lntp | grep ':8000'
```

Измените только host side:

```yaml
ports:
  - "18000:8000"
```

Внутренний container port менять не требуется.

## Недостаточно памяти

Остановите необязательные сервисы:

```bash
docker compose stop metabase minio
```

Для запуска API и базового моделирования обычно нужны:

```bash
docker compose --profile api up -d \
  postgres_main clickhouse api
```

Airflow и Metabase можно запускать отдельно.

## Просмотр всех логов

```bash
docker compose --profile api logs -f --tail=100
```

---

# Ограничения проекта

1. Синтетические данные не моделируются на основе реального банка, а лишь по предположениям автора.
2. Модель принятия сделки (acceptance model) является упрощенной, а не обученной моделью поведения клиентов.
3. Binance `aggTrades` не содержит полный order book, cancellations и queue position.
4. Внутренний инвентарь реального маркет-мейкера ненаблюдаем.
5. Future trade price или VWAP используется как proxy для markout, а не как точный mid-price replay.
6. Observed dollar markout exposure не равен realized PnL.
7. RG-inspired coarse-graining не является строгой Wilsonian RG.
8. Supervised coefficients не являются физическими coupling constants.
9. Результаты ограничены исследованными инструментами, периодами и горизонтами.
10. Final holdout нельзя повторно использовать для настройки модели.
11. API и Compose-конфигурация предназначены для локального окружения, а не для public production deployment.
12. Некоторые исторические controller scripts могут относиться к экспериментальным веткам и требуют отдельной проверки на текущем `main`.

---

# Документация

## Теоретическая часть

- [PDF](docs/theory/ReDataX_theory_revised.pdf)
- [LaTeX source](docs/theory/ReDataX_theory_revised.tex)

Теоретический отчёт содержит:

- экономическую постановку;
- модель инвентаря;
- Hawkes-like генератор;
- определение order-flow field;
- coarse-graining;
- Hamiltonian observer;
- иерархию моделей;
- temporal validation;
- метрики;
- границы физической аналогии.

---

# Автор

**Егор Васильев**

- GitHub: [@vasile8egor](https://github.com/vasile8egor)
- Репозиторий: [ReDataX_pet_project](https://github.com/vasile8egor/ReDataX_pet_project)

Проект разработан как самостоятельная исследовательская и инженерная работа, объединяющая data engineering, backend-разработку, моделирование рыночной микроструктуры и методы статистической физики.

При использовании проекта или его отдельных материалов укажите автора и ссылку на репозиторий.

---
