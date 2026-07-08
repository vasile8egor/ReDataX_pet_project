CREATE OR REPLACE VIEW gold.v_policy_economics_aggregate
(
    experiment_id, research_version, split, symbol, horizon_seconds,
    model_id, model_component, model_preset, policy_id, policy_name,
    scenario_name, internalization_rate, mitigation_efficiency,
    action_cost_bps, break_even_markout_bps,
    total_notional_usdt, acted_notional_usdt, acted_notional_fraction,
    total_adverse_loss_usdt, captured_adverse_loss_usdt,
    capture_rate, risk_concentration,
    gross_protected_value_usdt, action_cost_usdt,
    net_protected_value_usdt,
    gross_value_per_million_usdt, action_cost_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps, action_cost_headroom_bps,
    benefit_cost_ratio, oracle_capture_fraction, profitable
)
AS
SELECT
    p.experiment_id,
    r.research_version,
    p.split,
    p.symbol,
    p.horizon_seconds,
    p.model_id,
    p.model_component,
    p.model_preset,
    p.policy_id,
    p.policy_name,
    r.scenario_name,
    r.internalization_rate,
    r.mitigation_efficiency,
    r.action_cost_bps,
    r.break_even_markout_bps,
    p.total_notional_usdt,
    p.acted_notional_usdt,
    p.acted_notional_fraction,
    p.total_adverse_loss_usdt,
    p.captured_adverse_loss_usdt,
    p.capture_rate,
    p.risk_concentration,
    p.gross_protected_value_usdt,
    p.action_cost_usdt,
    p.net_protected_value_usdt,
    p.gross_value_per_million_usdt,
    if(
        p.total_notional_usdt > 0,
        p.action_cost_usdt / p.total_notional_usdt * 1000000,
        0
    ),
    p.net_value_per_million_usdt,
    p.break_even_action_cost_bps,
    p.break_even_action_cost_bps - r.action_cost_bps,
    p.benefit_cost_ratio,
    p.oracle_capture_fraction,
    p.profitable
FROM gold.fact_research_policy_metrics AS p
ANY LEFT JOIN gold.dim_research_experiment_runs AS r
    ON p.experiment_id = r.experiment_id
WHERE p.metric_scope = 'aggregate';


CREATE OR REPLACE VIEW gold.v_policy_economics_daily
(
    experiment_id, split, metric_date, symbol, horizon_seconds,
    model_id, model_preset, policy_id, policy_name,
    total_notional_usdt, acted_notional_usdt, acted_notional_fraction,
    captured_adverse_loss_usdt, capture_rate, risk_concentration,
    gross_value_per_million_usdt, action_cost_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps, benefit_cost_ratio, profitable
)
AS
SELECT
    experiment_id,
    split,
    metric_date,
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    policy_name,
    total_notional_usdt,
    acted_notional_usdt,
    acted_notional_fraction,
    captured_adverse_loss_usdt,
    capture_rate,
    risk_concentration,
    gross_value_per_million_usdt,
    if(
        total_notional_usdt > 0,
        action_cost_usdt / total_notional_usdt * 1000000,
        0
    ),
    net_value_per_million_usdt,
    break_even_action_cost_bps,
    benefit_cost_ratio,
    profitable
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'daily';


CREATE OR REPLACE VIEW gold.v_policy_economics_selected
(
    experiment_id, research_version, symbol, horizon_seconds,
    model_id, model_preset, policy_id, policy_name,
    scenario_name, internalization_rate, mitigation_efficiency,
    action_cost_bps, break_even_markout_bps,
    acted_notional_fraction, capture_rate, risk_concentration,
    gross_value_per_million_usdt, action_cost_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps, action_cost_headroom_bps,
    benefit_cost_ratio, oracle_capture_fraction
)
AS
SELECT
    experiment_id,
    research_version,
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    policy_name,
    scenario_name,
    internalization_rate,
    mitigation_efficiency,
    action_cost_bps,
    break_even_markout_bps,
    acted_notional_fraction,
    capture_rate,
    risk_concentration,
    gross_value_per_million_usdt,
    action_cost_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps,
    action_cost_headroom_bps,
    benefit_cost_ratio,
    oracle_capture_fraction
FROM gold.v_policy_economics_aggregate
WHERE split = 'final'
  AND policy_id = 'P3';
