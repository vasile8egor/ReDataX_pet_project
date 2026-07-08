CREATE OR REPLACE VIEW gold.v_model_evolution_predictive
(
    experiment_id,
    experiment_family,
    experiment_stage,
    metric_scope,
    metric_date,
    symbol,
    horizon_seconds,
    model_id,
    source_model,
    model_name,
    model_order,
    observations,
    toxic_rate,
    roc_auc,
    average_precision,
    brier_score,
    top_decile_lift
)
AS
SELECT
    experiment_id,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1', 'local_oos',
        experiment_id = 'coupled_rg_final_v1', 'cross_market',
        'other'
    ),
    experiment_stage,
    metric_scope,
    metric_date,
    symbol,
    horizon_seconds,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm0_single_scale', 'M0',
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm1_multiscale', 'M1',
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm2_rg_flow', 'M1R',
        experiment_id = 'coupled_rg_final_v1' AND model = 'm1_local', 'M1',
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_no_j', 'M2',
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_with_j', 'M3',
        model
    ),
    model,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm0_single_scale', 'M0 Single-scale local',
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm1_multiscale', 'M1 Local multiscale',
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm2_rg_flow', 'M1R Local RG-flow diagnostic',
        experiment_id = 'coupled_rg_final_v1' AND model = 'm1_local', 'M1 Local multiscale',
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_no_j', 'M2 Cross-market RG-noJ',
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_with_j', 'M3 Cross-market RG-with-J',
        model
    ),
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm0_single_scale', 0,
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm1_multiscale', 1,
        experiment_id = 'real_oos_multiscale_v1' AND model = 'm2_rg_flow', 2,
        experiment_id = 'coupled_rg_final_v1' AND model = 'm1_local', 1,
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_no_j', 2,
        experiment_id = 'coupled_rg_final_v1' AND model = 'rg_with_j', 3,
        99
    ),
    observations,
    toxic_rate,
    roc_auc,
    average_precision,
    brier_score,
    top_decile_lift
FROM gold.fact_model_validation_metrics FINAL
WHERE experiment_id IN ('real_oos_multiscale_v1', 'coupled_rg_final_v1');


CREATE OR REPLACE VIEW gold.v_model_evolution_bootstrap
(
    experiment_id,
    experiment_family,
    experiment_stage,
    symbol,
    horizon_seconds,
    comparison_id,
    source_comparison,
    comparison_name,
    comparison_order,
    metric,
    days,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    statistically_positive,
    statistically_negative
)
AS
SELECT
    experiment_id,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1', 'local_oos',
        experiment_id = 'coupled_rg_final_v1', 'cross_market',
        'other'
    ),
    experiment_stage,
    symbol,
    horizon_seconds,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm1_minus_m0', 'M1_vs_M0',
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm2_minus_m1', 'M1R_vs_M1',
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_no_j_minus_m1', 'M2_vs_M1',
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_with_j_minus_no_j', 'M3_vs_M2',
        comparison
    ),
    comparison,
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm1_minus_m0', 'M1 Local multiscale vs M0',
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm2_minus_m1', 'M1R local RG-flow vs M1',
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_no_j_minus_m1', 'M2 Cross-market RG-noJ vs M1',
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_with_j_minus_no_j', 'M3 RG-with-J vs M2',
        comparison
    ),
    multiIf(
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm1_minus_m0', 1,
        experiment_id = 'real_oos_multiscale_v1' AND comparison = 'm2_minus_m1', 2,
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_no_j_minus_m1', 3,
        experiment_id = 'coupled_rg_final_v1' AND comparison = 'rg_with_j_minus_no_j', 4,
        99
    ),
    metric,
    days,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    ci_lower > 0,
    ci_upper < 0
FROM gold.fact_model_comparison_bootstrap FINAL
WHERE experiment_id IN ('real_oos_multiscale_v1', 'coupled_rg_final_v1');


CREATE OR REPLACE VIEW gold.v_model_evolution_capture
(
    experiment_id,
    metric_scope,
    metric_date,
    symbol,
    horizon_seconds,
    capacity_fraction,
    model_id,
    source_model,
    model_name,
    observations,
    selected_observations,
    selected_trade_fraction,
    selected_notional_fraction,
    capture_rate,
    loss_lift,
    captured_loss_per_million_total_notional,
    selected_loss_per_million_selected_notional,
    oracle_capture_rate,
    oracle_efficiency
)
AS
SELECT
    experiment_id,
    metric_scope,
    metric_date,
    symbol,
    horizon_seconds,
    capacity_fraction,
    multiIf(model = 'm0_single_scale', 'M0', model = 'm1_multiscale', 'M1', model),
    model,
    multiIf(
        model = 'm0_single_scale', 'M0 Single-scale local',
        model = 'm1_multiscale', 'M1 Local multiscale',
        model
    ),
    observations,
    selected_observations,
    selected_trade_fraction,
    selected_notional_fraction,
    capture_rate,
    loss_lift,
    captured_loss_per_million_total_notional,
    selected_loss_per_million_selected_notional,
    oracle_capture_rate,
    oracle_efficiency
FROM gold.fact_adverse_selection_capture FINAL
WHERE experiment_id = 'adverse_selection_capture_v1';


CREATE OR REPLACE VIEW gold.v_model_evolution_capture_bootstrap
(
    experiment_id,
    symbol,
    horizon_seconds,
    capacity_fraction,
    comparison_id,
    comparison_name,
    metric,
    days,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    statistically_positive
)
AS
SELECT
    experiment_id,
    symbol,
    horizon_seconds,
    capacity_fraction,
    'M1_vs_M0',
    'M1 Local multiscale vs M0',
    metric,
    days,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    ci_lower > 0
FROM gold.fact_adverse_selection_capture_bootstrap FINAL
WHERE experiment_id = 'adverse_selection_capture_v1';
