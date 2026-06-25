DIM_EVENT_DATASET_Q = '''
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
'''

ALTER_DIM_EVENT_DATASET_Q = '''
ALTER TABLE gold.dim_event_datasets
ADD COLUMN IF NOT EXISTS generated_requests UInt64
AFTER amount_multiplier
'''

FACT_SIMULATION_RUNS_Q = '''
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
)
'''

FACT_INVENTORY_SNAPSHOTS_Q = '''
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
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(snapshot_ts)
ORDER BY (run_id, event_index, currency)
'''

ALTER_INVENTORY_SNAPSHOTS_Q = '''
ALTER TABLE gold.fact_inventory_snapshots

    ADD COLUMN IF NOT EXISTS
        source_event_id Nullable(UUID)
        AFTER event_index,

    ADD COLUMN IF NOT EXISTS
        source_step_index Nullable(UInt64)
        AFTER source_event_id,

    ADD COLUMN IF NOT EXISTS
        controller_activated Nullable(Bool)
        AFTER h_external,

    ADD COLUMN IF NOT EXISTS
        controller_h_before_event Nullable(Float64)
        AFTER controller_activated,

    ADD COLUMN IF NOT EXISTS
        controller_raw_adjustment_bps Nullable(Float64)
        AFTER controller_h_before_event,

    ADD COLUMN IF NOT EXISTS
        controller_spread_adjustment_bps Nullable(Float64)
        AFTER controller_raw_adjustment_bps,

    ADD COLUMN IF NOT EXISTS
        controller_cap_hit Nullable(UInt8)
        AFTER controller_spread_adjustment_bps,

    ADD COLUMN IF NOT EXISTS
        transition_h_before_event Nullable(Float64)
        AFTER controller_cap_hit,

    ADD COLUMN IF NOT EXISTS
        transition_h_after_if_accepted Nullable(Float64)
        AFTER transition_h_before_event,

    ADD COLUMN IF NOT EXISTS
        transition_delta_h_if_accepted Nullable(Float64)
        AFTER transition_h_after_if_accepted
'''

INSERT_INTO_DIM_EVENT_Q = '''
INSERT INTO gold.dim_event_datasets(
    event_dataset_id,
    comparison_id,
    generator,
    seed,
    steps,
    dt_seconds,
    base_intensity,
    alpha,
    beta,
    amount_multiplier,
    generated_requests,
    created_at
)
VALUES
'''

INSERT_INTO_FACT_SIM_Q = '''
INSERT INTO gold.fact_simulation_runs(
    run_id,
    comparison_id,
    event_dataset_id,
    model_version,
    physics_mode,
    pricing_policy,
    hedging_policy,
    seed,
    steps,
    dt_seconds,
    base_intensity,
    alpha,
    beta,
    amount_multiplier,
    generated_requests,
    accepted_events,
    rejected_events,
    acceptance_rate,
    average_quoted_spread_bps,
    average_accepted_spread_bps,
    customer_spread_cost_usd,
    spread_revenue_usd,
    allocated_product_revenue_usd,
    hedge_cost_usd,
    funding_cost_usd,
    net_pnl_usd,
    final_regime,
    max_abs_pressure,
    stress_time_fraction,
    final_inventory_pressure_json,
    parameters_json,
    started_at,
    finished_at
)
VALUES
'''

INSERT_INTO_FACT_INVENTORY_SNAPSHOTS_Q = '''
INSERT INTO gold.fact_inventory_snapshots(
    run_id,
    comparison_id,
    event_dataset_id,
    model_version,
    physics_mode,
    pricing_policy,
    event_index,
    source_event_id,
    source_step_index,
    snapshot_ts,
    currency,
    position,
    position_limit,
    limit_utilization,
    position_pressure,
    order_flow_buy_ewma,
    order_flow_sell_ewma,
    order_flow_imbalance,
    phi,
    hedge_capacity,
    max_hedge_capacity,
    hedge_capacity_used_ratio,
    funding_cost_bps,
    market_volatility,
    regime,
    event_accepted,
    acceptance_probability,
    cumulative_accepted_events,
    cumulative_rejected_events,
    cumulative_spread_revenue_usd,
    h_total,
    h_quadratic,
    h_quartic,
    h_coupling,
    h_external,
    controller_activated,
    controller_h_before_event,
    controller_raw_adjustment_bps,
    controller_spread_adjustment_bps,
    controller_cap_hit,
    transition_h_before_event,
    transition_h_after_if_accepted,
    transition_delta_h_if_accepted
)
VALUES
'''

SELECT_EXISTING_EVENT_DATASET_Q = '''
SELECT
    (
        SELECT count()
        FROM gold.dim_event_datasets
        WHERE event_dataset_id = %(event_dataset_id)s
    ) AS dataset_rows,
    (
        SELECT count()
        FROM gold.fact_fx_events
        WHERE event_dataset_id = %(event_dataset_id)s
    ) AS event_rows
'''

SELECT_EXISTING_COMPARISON_Q = '''
SELECT
    (
        SELECT count()
        FROM gold.fact_simulation_runs
        WHERE comparison_id = %(comparison_id)s
    ) AS run_rows,
    (
        SELECT count()
        FROM gold.fact_inventory_snapshots
        WHERE comparison_id = %(comparison_id)s
    ) AS snapshot_rows
'''

FACT_FX_EVENTS_Q = """
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
ORDER BY (
    event_dataset_id,
    event_sequence
)
"""

INSERT_INTO_FACT_FX_EVENTS_Q = """
INSERT INTO gold.fact_fx_events(
    event_dataset_id,
    event_id,
    event_sequence,
    source_step_index,
    event_ts,
    customer_id,
    base_currency,
    quote_currency,
    side,
    amount,
    customer_segment,
    channel
)
VALUES
"""

SELECT_ALL_FX_EVENTS_Q = '''
SELECT
    events.event_dataset_id,
    events.event_id,
    events.event_sequence,
    events.source_step_index,
    events.event_ts,
    events.customer_id,
    events.base_currency,
    events.quote_currency,
    events.side,
    events.amount,
    events.customer_segment,
    events.channel,
    datasets.generator,
    datasets.seed,
    datasets.steps,
    datasets.dt_seconds,
    datasets.base_intensity,
    datasets.alpha,
    datasets.beta
FROM gold.fact_fx_events AS events
INNER JOIN gold.dim_event_datasets AS datasets
    ON datasets.event_dataset_id = events.event_dataset_id
WHERE events.event_dataset_id = %(event_dataset_id)s
ORDER BY events.event_sequence
'''

FX_POLICY_RUN_SUMMARY_VIEW_Q = """
CREATE VIEW IF NOT EXISTS gold.v_fx_policy_run_summary AS
SELECT
    run_id,
    comparison_id,
    event_dataset_id,

    model_version,
    physics_mode,
    pricing_policy,
    hedging_policy,

    seed,

    generated_requests,
    accepted_events,
    rejected_events,
    acceptance_rate,

    average_quoted_spread_bps,
    average_accepted_spread_bps,
    customer_spread_cost_usd,

    spread_revenue_usd,
    allocated_product_revenue_usd,
    hedge_cost_usd,
    funding_cost_usd,
    net_pnl_usd,

    spread_revenue_usd
        + allocated_product_revenue_usd AS total_revenue_usd,

    final_regime,
    max_abs_pressure,
    stress_time_fraction,

    started_at,
    finished_at,
    loaded_at
FROM gold.fact_simulation_runs
"""

FX_INVENTORY_TRAJECTORY_VIEW_Q = """
CREATE VIEW IF NOT EXISTS gold.v_fx_inventory_trajectory AS
SELECT
    run_id,
    comparison_id,
    event_dataset_id,

    model_version,
    physics_mode,
    pricing_policy,

    event_index,
    snapshot_ts,
    currency,

    position,
    position_limit,
    limit_utilization,
    position_pressure,

    order_flow_imbalance,
    phi,
    abs(phi) AS abs_phi,

    hedge_capacity,
    hedge_capacity_used_ratio,

    regime,
    event_accepted,
    acceptance_probability,

    cumulative_accepted_events,
    cumulative_rejected_events,
    cumulative_spread_revenue_usd,

    h_total,
    h_quadratic,
    h_quartic,
    h_coupling,
    h_external
FROM gold.fact_inventory_snapshots
"""

FX_REGIME_DISTRIBUTION_VIEW_Q = """
CREATE VIEW IF NOT EXISTS gold.v_fx_regime_distribution AS
SELECT
    run_id,
    comparison_id,
    model_version,
    physics_mode,
    pricing_policy,
    regime,

    uniqExact(event_index) AS sampled_events,

    uniqExact(event_index)
        / sum(uniqExact(event_index))
          OVER (
              PARTITION BY
                  run_id,
                  pricing_policy
          ) AS regime_fraction
FROM gold.fact_inventory_snapshots
WHERE event_index > 0
GROUP BY
    run_id,
    comparison_id,
    model_version,
    physics_mode,
    pricing_policy,
    regime
"""

FX_HAMILTONIAN_STATE_VIEW_Q = """
CREATE VIEW IF NOT EXISTS gold.v_fx_hamiltonian_state AS
SELECT
    s.run_id,
    s.comparison_id,
    s.event_dataset_id,
    s.model_version,
    s.physics_mode,
    s.pricing_policy,
    s.event_index,
    s.snapshot_ts,

    any(s.regime) AS regime,

    max(abs(s.phi)) AS max_abs_phi,
    sqrt(sum(s.phi * s.phi)) AS phi_l2_norm,

    max(s.h_total) AS h_total,
    max(s.h_quadratic) AS h_quadratic,
    max(s.h_quartic) AS h_quartic,
    max(s.h_coupling) AS h_coupling,
    max(s.h_external) AS h_external

FROM gold.fact_inventory_snapshots AS s

WHERE s.h_total IS NOT NULL

GROUP BY
    s.run_id,
    s.comparison_id,
    s.event_dataset_id,
    s.model_version,
    s.physics_mode,
    s.pricing_policy,
    s.event_index,
    s.snapshot_ts
"""

RG_ANALYSIS_RUNS_Q = """
CREATE TABLE IF NOT EXISTS gold.fact_rg_analysis_runs
(
    analysis_id UUID,
    analysis_version LowCardinality(String),

    source_model_version LowCardinality(String),
    hamiltonian_preset LowCardinality(String),

    block_sizes Array(UInt32),
    stress_pressure_threshold Float64,

    source_run_count UInt32,
    source_frame_count UInt64,

    parameters_json String,

    started_at DateTime64(6, 'UTC'),
    finished_at DateTime64(6, 'UTC'),

    loaded_at DateTime64(6, 'UTC')
        DEFAULT now64(6)
)
ENGINE = MergeTree
ORDER BY
(
    analysis_version,
    source_model_version,
    started_at,
    analysis_id
)
"""

RG_SCALE_OBSERVABLES_Q = """
CREATE TABLE IF NOT EXISTS gold.fact_rg_scale_observables
(
    analysis_id UUID,
    analysis_version LowCardinality(String),

    source_run_id UUID,
    event_dataset_id UUID,
    source_model_version LowCardinality(String),
    pricing_policy LowCardinality(String),

    block_size UInt32,
    block_count UInt32,

    frames_used UInt64,
    frames_dropped UInt64,

    trace_coarse_covariance Float64,
    mean_coarse_norm_squared Float64,
    mean_internal_variance_total Float64,

    mean_max_abs_coarse_pressure Float64,
    coarse_stress_fraction Float64,

    mean_micro_h_total Nullable(Float64),
    mean_coarse_h_total Nullable(Float64),
    mean_unresolved_h_total Nullable(Float64),

    loaded_at DateTime64(6, 'UTC')
        DEFAULT now64(6)
)
ENGINE = MergeTree
ORDER BY
(
    analysis_id,
    pricing_policy,
    source_run_id,
    block_size
)
"""

RG_CURRENCY_OBSERVABLES_Q = """
CREATE TABLE IF NOT EXISTS gold.fact_rg_currency_observables
(
    analysis_id UUID,
    analysis_version LowCardinality(String),

    source_run_id UUID,
    event_dataset_id UUID,
    source_model_version LowCardinality(String),
    pricing_policy LowCardinality(String),

    block_size UInt32,
    currency LowCardinality(String),

    mean_coarse_pressure Float64,
    coarse_second_moment Float64,
    coarse_fourth_moment Float64,
    coarse_variance Float64,

    mean_micro_second_moment Float64,
    mean_internal_variance Float64,

    second_moment_decomposition_error Float64,

    loaded_at DateTime64(6, 'UTC')
        DEFAULT now64(6)
)
ENGINE = MergeTree
ORDER BY
(
    analysis_id,
    pricing_policy,
    source_run_id,
    block_size,
    currency
)
"""

RG_VARIANCE_SCALING_Q = """
CREATE TABLE IF NOT EXISTS gold.fact_rg_variance_scaling
(
    analysis_id UUID,
    analysis_version LowCardinality(String),

    source_run_id UUID,
    event_dataset_id UUID,
    source_model_version LowCardinality(String),
    pricing_policy LowCardinality(String),

    dimension LowCardinality(String),

    from_block_size UInt32,
    to_block_size UInt32,

    variance_from Float64,
    variance_to Float64,

    scaling_exponent Nullable(Float64),

    loaded_at DateTime64(6, 'UTC')
        DEFAULT now64(6)
)
ENGINE = MergeTree
ORDER BY
(
    analysis_id,
    pricing_policy,
    source_run_id,
    dimension,
    from_block_size
)
"""

SELECT_RG_SOURCE_RUNS_Q = """
SELECT
    argMax(
        run_id,
        tuple(loaded_at, run_id)
    ) AS source_run_id,

    event_dataset_id,
    pricing_policy,

    argMax(
        generated_requests,
        tuple(loaded_at, run_id)
    ) AS generated_requests

FROM gold.fact_simulation_runs

WHERE model_version =
    %(source_model_version)s

GROUP BY
    event_dataset_id,
    pricing_policy

ORDER BY
    pricing_policy,
    event_dataset_id
"""

SELECT_RG_PRESSURE_OBSERVATIONS_Q = """
SELECT
    event_index,
    currency,
    phi,
    h_total

FROM gold.fact_inventory_snapshots

WHERE run_id = %(run_id)s
  AND event_index > 0

ORDER BY
    event_index,
    currency
"""

SELECT_EXISTING_RG_ANALYSIS_Q = """
SELECT
    (
        SELECT count()
        FROM gold.fact_rg_analysis_runs
        WHERE analysis_id = %(analysis_id)s
    ) AS analysis_rows,

    (
        SELECT count()
        FROM gold.fact_rg_scale_observables
        WHERE analysis_id = %(analysis_id)s
    ) AS scale_rows,

    (
        SELECT count()
        FROM gold.fact_rg_currency_observables
        WHERE analysis_id = %(analysis_id)s
    ) AS currency_rows,

    (
        SELECT count()
        FROM gold.fact_rg_variance_scaling
        WHERE analysis_id = %(analysis_id)s
    ) AS scaling_rows
"""

INSERT_RG_ANALYSIS_RUN_Q = """
INSERT INTO gold.fact_rg_analysis_runs
(
    analysis_id,
    analysis_version,
    source_model_version,
    hamiltonian_preset,
    block_sizes,
    stress_pressure_threshold,
    source_run_count,
    source_frame_count,
    parameters_json,
    started_at,
    finished_at
)
VALUES
"""

INSERT_RG_SCALE_OBSERVABLES_Q = """
INSERT INTO gold.fact_rg_scale_observables
(
    analysis_id,
    analysis_version,
    source_run_id,
    event_dataset_id,
    source_model_version,
    pricing_policy,
    block_size,
    block_count,
    frames_used,
    frames_dropped,
    trace_coarse_covariance,
    mean_coarse_norm_squared,
    mean_internal_variance_total,
    mean_max_abs_coarse_pressure,
    coarse_stress_fraction,
    mean_micro_h_total,
    mean_coarse_h_total,
    mean_unresolved_h_total
)
VALUES
"""

INSERT_RG_CURRENCY_OBSERVABLES_Q = """
INSERT INTO gold.fact_rg_currency_observables
(
    analysis_id,
    analysis_version,
    source_run_id,
    event_dataset_id,
    source_model_version,
    pricing_policy,
    block_size,
    currency,
    mean_coarse_pressure,
    coarse_second_moment,
    coarse_fourth_moment,
    coarse_variance,
    mean_micro_second_moment,
    mean_internal_variance,
    second_moment_decomposition_error
)
VALUES
"""

INSERT_RG_VARIANCE_SCALING_Q = """
INSERT INTO gold.fact_rg_variance_scaling
(
    analysis_id,
    analysis_version,
    source_run_id,
    event_dataset_id,
    source_model_version,
    pricing_policy,
    dimension,
    from_block_size,
    to_block_size,
    variance_from,
    variance_to,
    scaling_exponent
)
VALUES
"""
