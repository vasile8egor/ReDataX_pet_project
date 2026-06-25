CREATE DATABASE IF NOT EXISTS gold;


CREATE TABLE IF NOT EXISTS gold.fact_transactions (
    transaction_id String,
    account_id String,
    tx_timestamp DateTime64(3, 'UTC'),
    amount Decimal(18, 4),
    currency String,
    merchant_name Nullable(String),
    bronze_loaded_at DateTime64(3, 'UTC'),
    gold_loaded_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(gold_loaded_at)
ORDER BY (tx_timestamp, transaction_id);


CREATE TABLE IF NOT EXISTS gold.dim_event_datasets(
    event_dataset_id UUID,
    comparison_id UUID,

    generator LowCardinality(String),
    seed Nullable(Int64),

    steps UInt32,
    dt_seconds UInt32,
    base_intensity Float64,
    alpha Float64,
    beta Float64,
    amount_multiplier Float64,
    generated_requests UInt64,

    created_at DateTime64(6, 'UTC'),
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree 
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, event_dataset_id);


CREATE TABLE IF NOT EXISTS gold.fact_simulation_runs(
    run_id UUID,
    comparison_id UUID,
    event_dataset_id UUID,

    model_version LowCardinality(String),
    physics_mode LowCardinality(String),
    pricing_policy LowCardinality(String),
    hedging_policy LowCardinality(String),

    seed Nullable(Int64),

    steps UInt32,
    dt_seconds UInt32,
    base_intensity Float64,
    alpha Float64,
    beta Float64,
    amount_multiplier Float64,

    generated_requests UInt64,
    accepted_events UInt64,
    rejected_events UInt64,
    acceptance_rate Float64,

    average_quoted_spread_bps Float64,
    average_accepted_spread_bps Float64,
    customer_spread_cost_usd Float64,

    spread_revenue_usd Float64,
    allocated_product_revenue_usd Float64,
    hedge_cost_usd Float64,
    funding_cost_usd Float64,
    net_pnl_usd Float64,

    final_regime LowCardinality(String),
    max_abs_pressure Float64,
    stress_time_fraction Float64,

    final_inventory_pressure_json String,
    parameters_json String,

    started_at DateTime64(6, 'UTC'),
    finished_at DateTime64(6, 'UTC'),
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (
    model_version,
    physics_mode,
    pricing_policy,
    started_at,
    run_id
);


CREATE TABLE IF NOT EXISTS gold.fact_inventory_snapshots(
    run_id UUID,
    comparison_id UUID,
    event_dataset_id UUID,

    model_version LowCardinality(String),
    physics_mode LowCardinality(String),
    pricing_policy LowCardinality(String),

    event_index UInt64,
    source_event_id Nullable(UUID),
    source_step_index Nullable(UInt64),
    snapshot_ts DateTime64(6, 'UTC'),

    currency LowCardinality(String),

    position Float64,
    position_limit Float64,
    limit_utilization Float64,
    position_pressure Float64,

    order_flow_buy_ewma Float64,
    order_flow_sell_ewma Float64,
    order_flow_imbalance Float64,

    phi Float64,

    hedge_capacity Float64,
    max_hedge_capacity Float64,
    hedge_capacity_used_ratio Float64,

    funding_cost_bps Float64,
    market_volatility Float64,

    regime LowCardinality(String),

    event_accepted UInt8,
    acceptance_probability Float64,

    cumulative_accepted_events UInt64,
    cumulative_rejected_events UInt64,
    cumulative_spread_revenue_usd Float64,

    h_total Nullable(Float64),
    h_quadratic Nullable(Float64),
    h_quartic Nullable(Float64),
    h_coupling Nullable(Float64),
    h_external Nullable(Float64),

    controller_activated Nullable(UInt8),
    controller_h_before_event Nullable(Float64),
    controller_raw_adjustment_bps Nullable(Float64),
    controller_spread_adjustment_bps Nullable(Float64),
    controller_cap_hit Nullable(UInt8),

    transition_h_before_event Nullable(Float64),
    transition_h_after_if_accepted Nullable(Float64),
    transition_delta_h_if_accepted Nullable(Float64),

    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(snapshot_ts)
ORDER BY (
    run_id,
    event_index,
    currency
);


CREATE TABLE IF NOT EXISTS gold.fact_rg_transition_diagnostics
(
    run_id UUID,
    event_dataset_id UUID,

    model_version LowCardinality(String),
    pricing_policy LowCardinality(String),

    event_index UInt64,
    block_size UInt32,

    history_ready UInt8,
    request_accepted UInt8,

    local_h_before Float64,
    local_projected_h_after Float64,
    local_delta_h Float64,

    coarse_h_before Float64,

    coarse_temporal_drift_delta_h Float64,
    normalized_coarse_temporal_drift_delta_h Float64,

    coarse_request_delta_h Float64,
    normalized_coarse_request_delta_h Float64,

    coarse_total_accepted_delta_h Float64,
    normalized_coarse_total_accepted_delta_h Float64,

    local_sign LowCardinality(String),
    coarse_sign LowCardinality(String),
    sign_agreement UInt8,

    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
ORDER BY
(
    model_version,
    pricing_policy,
    run_id,
    event_index
);


CREATE TABLE IF NOT EXISTS gold.fact_fx_events(
    event_dataset_id UUID,
    event_id UUID,
    event_sequence UInt64,
    source_step_index UInt64,
    event_ts DateTime64(6, 'UTC'),
    customer_id String,
    base_currency LowCardinality(String),
    quote_currency LowCardinality(String),
    side LowCardinality(String),
    amount Float64,
    customer_segment LowCardinality(String),
    channel LowCardinality(String),
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_ts)
ORDER BY (event_dataset_id, event_sequence);
