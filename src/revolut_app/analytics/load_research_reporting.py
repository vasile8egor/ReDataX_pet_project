from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from revolut_app.analytics.queries import (
    DELETE_EXPERIMENT_Q_TEMPLATE,
    DELETE_RESEARCH_MODEL_REGISTRY_Q_TEMPLATE,
    DELETE_RESEARCH_POLICY_REGISTRY_Q_TEMPLATE,
    INSERT_ROWS_Q_TEMPLATE,
)


RUN_COLUMNS = (
    'experiment_id',
    'research_version',
    'artifact_type',
    'git_commit',
    'scenario_name',
    'mitigation_efficiency',
    'internalization_rate',
    'action_cost_bps',
    'break_even_markout_bps',
    'decision_stride_seconds',
    'train_start',
    'train_end',
    'development_start',
    'development_end',
    'validation_start',
    'validation_end',
    'final_start',
    'final_end',
    'hurdle_source_path',
    'oracle_source_path',
    'hurdle_configuration_json',
    'oracle_configuration_json',
    'created_at',
)

MODEL_SELECTION_COLUMNS = (
    'experiment_id',
    'symbol',
    'stage',
    'horizon_seconds',
    'candidate_rank',
    'is_selected',
    'accepted',
    'model_id',
    'model_component',
    'model_preset',
    'policy_id',
    'notional_budget_fraction',
    'min_expected_net_margin_bps',
    'min_break_even_probability',
    'prediction_multiplier',
    'mean_daily_net_value_per_million_usdt',
    'median_daily_net_value_per_million_usdt',
    'std_daily_net_value_per_million_usdt',
    'worst_day_net_value_per_million_usdt',
    'positive_day_fraction',
    'robust_score',
    'model_spec_json',
    'policy_spec_json',
)

POLICY_METRIC_COLUMNS = (
    'experiment_id',
    'metric_scope',
    'metric_date',
    'split',
    'symbol',
    'horizon_seconds',
    'model_id',
    'model_component',
    'model_preset',
    'policy_id',
    'policy_name',
    'notional_budget_fraction',
    'min_expected_net_margin_bps',
    'min_break_even_probability',
    'prediction_multiplier',
    'observations',
    'acted_observations',
    'acted_event_fraction',
    'mean_action_fraction_on_acted_events',
    'total_notional_usdt',
    'acted_notional_usdt',
    'acted_notional_fraction',
    'total_adverse_loss_usdt',
    'captured_adverse_loss_usdt',
    'capture_rate',
    'risk_concentration',
    'gross_protected_value_usdt',
    'action_cost_usdt',
    'net_protected_value_usdt',
    'gross_value_per_million_usdt',
    'net_value_per_million_usdt',
    'break_even_action_cost_bps',
    'benefit_cost_ratio',
    'oracle_capture_fraction',
    'profitable',
)

BOOTSTRAP_COLUMNS = (
    'experiment_id',
    'split',
    'symbol',
    'horizon_seconds',
    'comparison_id',
    'candidate_policy_id',
    'baseline_policy_id',
    'metric_name',
    'days',
    'bootstrap_samples',
    'mean_delta',
    'ci_lower',
    'ci_upper',
    'positive_day_fraction',
)

DIAGNOSTIC_COLUMNS = (
    'experiment_id',
    'split',
    'metric_date',
    'symbol',
    'horizon_seconds',
    'model_id',
    'model_preset',
    'policy_id',
    'probability_positive_mean',
    'probability_break_even_mean',
    'expected_positive_markout_p95_bps',
    'expected_positive_markout_max_bps',
    'direct_expected_markout_p95_bps',
    'hurdle_predicted_net_positive_fraction',
    'direct_predicted_net_positive_fraction',
)

ORACLE_COLUMNS = (
    'experiment_id',
    'symbol',
    'horizon_seconds',
    'notional_budget_fraction',
    'aggregate_net_value_per_million_usdt',
    'mean_daily_net_value_per_million_usdt',
    'robust_score',
    'positive_day_fraction',
    'bootstrap_ci_lower',
    'bootstrap_ci_upper',
    'above_break_even_event_fraction',
    'above_break_even_notional_fraction',
    'acted_notional_fraction',
    'capture_rate',
    'break_even_action_cost_bps',
    'benefit_cost_ratio',
    'strictly_feasible',
    'is_best_by_robust_score',
    'is_capital_efficient',
)

MODEL_REGISTRY_COLUMNS = (
    'model_id',
    'model_name',
    'model_family',
    'target_type',
    'status',
    'predecessor_id',
    'description',
)

POLICY_REGISTRY_COLUMNS = (
    'policy_id',
    'policy_name',
    'policy_family',
    'deployable',
    'description',
)

MODEL_REGISTRY_ROWS = (
    ('NA', 'No predictive model', 'benchmark', 'none', 'Baseline', '', 'Used by the no-action policy.'),
    ('M0', 'Single-scale local baseline', 'classification', 'binary adverse-selection label', 'Baseline', '', 'Local single-scale predictive baseline.'),
    ('M1', 'Local multiscale', 'classification', 'binary adverse-selection label', 'Accepted', 'M0', 'Local temporal coarse-graining across multiple scales.'),
    ('M2', 'Cross-market RG-noJ', 'classification', 'binary adverse-selection label', 'Accepted', 'M1', 'Cross-market multiscale state without explicit pairwise J terms.'),
    ('M3', 'Cross-market RG-with-J', 'classification', 'binary adverse-selection label', 'Rejected', 'M2', 'Explicit pairwise interaction terms; incremental value was unstable.'),
    ('M4', 'Direct value regression', 'regression', 'positive markout in bps', 'Accepted', 'M2', 'Direct prediction of positive future markout.'),
    ('M5', 'Hurdle economic model', 'hurdle', 'probability and severity of positive markout', 'Final candidate', 'M4', 'Probability, conditional severity and break-even gate.'),
    ('ORACLE', 'Oracle upper bound', 'diagnostic', 'realized future markout', 'Diagnostic', '', 'Uses future data and is not deployable.'),
)

POLICY_REGISTRY_ROWS = (
    ('P0', 'No action', 'benchmark', 1, 'Zero-cost fallback and business baseline.'),
    ('P1', 'Probability budget', 'risk ranking', 1, 'Allocates notional by predicted break-even probability.'),
    ('P2', 'Direct economic', 'expected value', 1, 'Acts on direct positive-markout regression.'),
    ('P3', 'Hurdle economic', 'expected value', 1, 'Acts on probability times conditional severity with a break-even gate.'),
    ('P4', 'Oracle upper bound', 'diagnostic', 0, 'Uses realized future markout and is not deployable.'),
)

POLICY_META = {
    'no_action': ('NA', 'none', 'P0', 'No action'),
    'probability_budget': ('M5', 'break_even_classifier', 'P1', 'Probability budget'),
    'direct_economic': ('M4', 'direct_regression', 'P2', 'Direct economic'),
    'hurdle_economic': ('M5', 'hurdle', 'P3', 'Hurdle economic'),
    'oracle_upper_bound': ('ORACLE', 'oracle', 'P4', 'Oracle upper bound'),
}

COMPARISON_META = {
    'hurdle_minus_no_action': ('P3', 'P0'),
    'hurdle_minus_probability': ('P3', 'P1'),
    'hurdle_minus_direct': ('P3', 'P2'),
}


def read_json(path: str | Path):
    with Path(path).open('r', encoding='utf-8') as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f'''JSON root must be an object: {path}''')
    return payload


def canonical_json(value: Any):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def date_bounds(values: list[str]):
    if not values:
        raise ValueError('date list cannot be empty')
    parsed = [date.fromisoformat(value) for value in values]
    return min(parsed), max(parsed)


def resolve_git_commit(explicit: str | None):
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def same_candidate(left: dict[str, Any] | None, right: dict[str, Any] | None):
    if left is None or right is None:
        return False
    return (
        int(left['horizon_seconds']) == int(right['horizon_seconds'])
        and left['model_spec'] == right['model_spec']
        and left['policy_spec'] == right['policy_spec']
    )


def candidate_row(
    *,
    experiment_id: str,
    symbol: str,
    stage: str,
    candidate_rank: int,
    is_selected: bool,
    candidate: dict[str, Any],
):
    model_spec = candidate['model_spec']
    policy_spec = candidate['policy_spec']
    return (
        experiment_id,
        symbol,
        stage,
        int(candidate['horizon_seconds']),
        int(candidate_rank),
        int(is_selected),
        int(bool(candidate['accepted'])),
        'M5',
        'hurdle',
        str(model_spec['preset']),
        'P3',
        float(policy_spec['notional_budget_fraction']),
        float(policy_spec['min_expected_net_margin_bps']),
        float(policy_spec['min_break_even_probability']),
        float(policy_spec['prediction_multiplier']),
        float(candidate['mean_daily_net_value_per_million_usdt']),
        float(candidate['median_daily_net_value_per_million_usdt']),
        float(candidate['std_daily_net_value_per_million_usdt']),
        float(candidate['worst_day_net_value_per_million_usdt']),
        float(candidate['positive_day_fraction']),
        float(candidate['robust_score']),
        canonical_json(model_spec),
        canonical_json(policy_spec),
    )


def policy_metric_row(
    *,
    experiment_id: str,
    metric_scope: str,
    metric_date: date | None,
    split: str,
    symbol: str,
    horizon_seconds: int,
    model_preset: str,
    policy_spec: dict[str, Any],
    policy_name: str,
    metrics: dict[str, Any],
    oracle_capture_fraction: float,
):
    model_id, component, policy_id, display_name = POLICY_META[policy_name]
    return (
        experiment_id,
        metric_scope,
        metric_date or date(1970, 1, 1),
        split,
        symbol,
        int(horizon_seconds),
        model_id,
        component,
        model_preset,
        policy_id,
        display_name,
        float(policy_spec['notional_budget_fraction']),
        float(policy_spec['min_expected_net_margin_bps']),
        float(policy_spec['min_break_even_probability']),
        float(policy_spec['prediction_multiplier']),
        int(metrics['observations']),
        int(metrics['acted_observations']),
        float(metrics['acted_event_fraction']),
        float(metrics['mean_action_fraction_on_acted_events']),
        float(metrics['total_notional_usdt']),
        float(metrics['acted_notional_usdt']),
        float(metrics['acted_notional_fraction']),
        float(metrics['total_adverse_loss_usdt']),
        float(metrics['captured_adverse_loss_usdt']),
        float(metrics['capture_rate']),
        float(metrics['risk_concentration']),
        float(metrics['gross_protected_value_usdt']),
        float(metrics['action_cost_usdt']),
        float(metrics['net_protected_value_usdt']),
        float(metrics['gross_value_per_million_usdt']),
        float(metrics['net_value_per_million_usdt']),
        float(metrics['break_even_action_cost_bps']),
        float(metrics['benefit_cost_ratio']),
        float(oracle_capture_fraction),
        int(bool(metrics['profitable'])),
    )


def flatten_evaluation(
    *,
    experiment_id: str,
    split: str,
    symbol: str,
    horizon_seconds: int,
    model_spec: dict[str, Any],
    policy_spec: dict[str, Any],
    evaluation: dict[str, Any],
    bootstrap_samples: int,
):
    metric_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []
    diagnostic_rows: list[tuple[Any, ...]] = []
    model_preset = str(model_spec['preset'])

    for daily in evaluation['daily']:
        metric_date = date.fromisoformat(daily['date'])
        policies = daily['policies']
        oracle_net = float(policies['oracle_upper_bound']['net_value_per_million_usdt'])
        hurdle_net = float(policies['hurdle_economic']['net_value_per_million_usdt'])
        daily_capture = hurdle_net / oracle_net if oracle_net > 0 else 0.0

        for policy_name, metrics in policies.items():
            metric_rows.append(
                policy_metric_row(
                    experiment_id=experiment_id,
                    metric_scope='daily',
                    metric_date=metric_date,
                    split=split,
                    symbol=symbol,
                    horizon_seconds=horizon_seconds,
                    model_preset=model_preset,
                    policy_spec=policy_spec,
                    policy_name=policy_name,
                    metrics=metrics,
                    oracle_capture_fraction=(
                        daily_capture if policy_name == 'hurdle_economic' else 0.0
                    ),
                )
            )

        diagnostics = daily['prediction_diagnostics']
        diagnostic_rows.append(
            (
                experiment_id,
                split,
                metric_date,
                symbol,
                int(horizon_seconds),
                'M5',
                model_preset,
                'P3',
                float(diagnostics['probability_positive_mean']),
                float(diagnostics['probability_break_even_mean']),
                float(diagnostics['expected_positive_markout_p95_bps']),
                float(diagnostics['expected_positive_markout_max_bps']),
                float(diagnostics['direct_expected_markout_p95_bps']),
                float(diagnostics['hurdle_predicted_net_positive_fraction']),
                float(diagnostics['direct_predicted_net_positive_fraction']),
            )
        )

    aggregate_capture = float(evaluation.get('oracle_capture_fraction', 0.0))
    for policy_name, metrics in evaluation['aggregate'].items():
        metric_rows.append(
            policy_metric_row(
                experiment_id=experiment_id,
                metric_scope='aggregate',
                metric_date=None,
                split=split,
                symbol=symbol,
                horizon_seconds=horizon_seconds,
                model_preset=model_preset,
                policy_spec=policy_spec,
                policy_name=policy_name,
                metrics=metrics,
                oracle_capture_fraction=(
                    aggregate_capture if policy_name == 'hurdle_economic' else 0.0
                ),
            )
        )

    for comparison_id, values in evaluation['bootstrap'].items():
        candidate_policy_id, baseline_policy_id = COMPARISON_META[comparison_id]
        bootstrap_rows.append(
            (
                experiment_id,
                split,
                symbol,
                int(horizon_seconds),
                comparison_id,
                candidate_policy_id,
                baseline_policy_id,
                'net_value_per_million_usdt',
                int(values['days']),
                int(bootstrap_samples),
                float(values['mean']),
                float(values['ci_025']),
                float(values['ci_975']),
                float(values['positive_day_fraction']),
            )
        )

    return metric_rows, bootstrap_rows, diagnostic_rows


def flatten_hurdle(
    payload: dict[str, Any],
    *,
    experiment_id: str,
):
    configuration = payload['configuration']
    bootstrap_samples = int(configuration.get('bootstrap_samples', 5000))

    selection_rows: list[tuple[Any, ...]] = []
    metric_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []
    diagnostic_rows: list[tuple[Any, ...]] = []

    for symbol, target in payload['targets'].items():
        final_candidate = target.get('selected_final_candidate')

        for horizon_text, development in target['development'].items():
            winner = development.get('winner')
            for rank, candidate in enumerate(development['leaderboard_top20'], start=1):
                selection_rows.append(
                    candidate_row(
                        experiment_id=experiment_id,
                        symbol=symbol,
                        stage='development',
                        candidate_rank=rank,
                        is_selected=same_candidate(candidate, winner),
                        candidate=candidate,
                    )
                )

        validation_candidates: list[dict[str, Any]] = []
        for horizon_text, validation in target['validation'].items():
            candidate = validation['candidate']
            validation_candidates.append(candidate)

        validation_candidates.sort(
            key=lambda item: (
                bool(item['accepted']),
                float(item['robust_score']),
                float(item['mean_daily_net_value_per_million_usdt']),
            ),
            reverse=True,
        )

        for rank, candidate in enumerate(validation_candidates, start=1):
            selection_rows.append(
                candidate_row(
                    experiment_id=experiment_id,
                    symbol=symbol,
                    stage='validation',
                    candidate_rank=rank,
                    is_selected=same_candidate(candidate, final_candidate),
                    candidate=candidate,
                )
            )

        if final_candidate is not None:
            selection_rows.append(
                candidate_row(
                    experiment_id=experiment_id,
                    symbol=symbol,
                    stage='final',
                    candidate_rank=1,
                    is_selected=True,
                    candidate=final_candidate,
                )
            )

        for horizon_text, validation in target['validation'].items():
            candidate = validation['candidate']
            evaluation = validation['evaluation']
            rows = flatten_evaluation(
                experiment_id=experiment_id,
                split='validation',
                symbol=symbol,
                horizon_seconds=int(candidate['horizon_seconds']),
                model_spec=candidate['model_spec'],
                policy_spec=candidate['policy_spec'],
                evaluation=evaluation,
                bootstrap_samples=bootstrap_samples,
            )
            metric_rows.extend(rows[0])
            bootstrap_rows.extend(rows[1])
            diagnostic_rows.extend(rows[2])

        if final_candidate is not None and target.get('final_test') is not None:
            rows = flatten_evaluation(
                experiment_id=experiment_id,
                split='final',
                symbol=symbol,
                horizon_seconds=int(final_candidate['horizon_seconds']),
                model_spec=final_candidate['model_spec'],
                policy_spec=final_candidate['policy_spec'],
                evaluation=target['final_test'],
                bootstrap_samples=bootstrap_samples,
            )
            metric_rows.extend(rows[0])
            bootstrap_rows.extend(rows[1])
            diagnostic_rows.extend(rows[2])

    return {
        'model_selection': selection_rows,
        'policy_metrics': metric_rows,
        'bootstrap': bootstrap_rows,
        'diagnostics': diagnostic_rows,
    }


def recommendation_matches(candidate: dict[str, Any], selected: dict[str, Any] | None):
    if selected is None:
        return False
    return (
        int(candidate['horizon_seconds']) == int(selected['horizon_seconds'])
        and float(candidate['notional_budget_fraction'])
        == float(selected['notional_budget_fraction'])
    )


def flatten_oracle(
    payload: dict[str, Any],
    *,
    experiment_id: str,
):
    rows: list[tuple[Any, ...]] = []

    for symbol, target in payload['targets'].items():
        recommendation = target['recommendations']
        best = recommendation.get('best_by_robust_score')
        capital_efficient = recommendation.get('capital_efficient_candidate')

        for candidate in target['candidate_ranking']:
            rows.append(
                (
                    experiment_id,
                    symbol,
                    int(candidate['horizon_seconds']),
                    float(candidate['notional_budget_fraction']),
                    float(candidate['aggregate_net_value_per_million_usdt']),
                    float(candidate['mean_daily_net_value_per_million_usdt']),
                    float(candidate['robust_score']),
                    float(candidate['positive_day_fraction']),
                    float(candidate['bootstrap_ci_lower']),
                    float(candidate['bootstrap_ci_upper']),
                    float(candidate['above_break_even_event_fraction']),
                    float(candidate['above_break_even_notional_fraction']),
                    float(candidate['acted_notional_fraction']),
                    float(candidate['capture_rate']),
                    float(candidate['break_even_action_cost_bps']),
                    float(candidate['benefit_cost_ratio']),
                    int(bool(candidate['strictly_feasible'])),
                    int(recommendation_matches(candidate, best)),
                    int(recommendation_matches(candidate, capital_efficient)),
                )
            )
    return rows


def build_run_row(
    hurdle_payload: dict[str, Any],
    oracle_payload: dict[str, Any],
    *,
    experiment_id: str,
    research_version: str,
    git_commit: str,
    hurdle_source_path: str,
    oracle_source_path: str,
):
    configuration = hurdle_payload['configuration']
    scenario = configuration['scenario']
    train_start, train_end = date_bounds(configuration['train_dates'])
    development_start, development_end = date_bounds(configuration['development_dates'])
    validation_start, validation_end = date_bounds(configuration['validation_dates'])
    final_start, final_end = date_bounds(configuration['final_test_dates'])

    return (
        experiment_id,
        research_version,
        'hurdle_economic_policy+oracle_horizon_scan',
        git_commit,
        str(scenario['name']),
        float(scenario['mitigation_efficiency']),
        float(scenario['internalization_rate']),
        float(scenario['action_cost_bps']),
        float(configuration['break_even_markout_bps']),
        int(configuration['decision_stride_seconds']),
        train_start,
        train_end,
        development_start,
        development_end,
        validation_start,
        validation_end,
        final_start,
        final_end,
        hurdle_source_path,
        oracle_source_path,
        canonical_json(configuration),
        canonical_json(oracle_payload['configuration']),
        datetime.now(timezone.utc),
    )


def flatten_research_reporting(
    hurdle_payload: dict[str, Any],
    oracle_payload: dict[str, Any],
    *,
    experiment_id: str,
    research_version: str,
    git_commit: str,
    hurdle_source_path: str,
    oracle_source_path: str,
):
    hurdle = flatten_hurdle(hurdle_payload, experiment_id=experiment_id)
    return {
        'model_registry': list(MODEL_REGISTRY_ROWS),
        'policy_registry': list(POLICY_REGISTRY_ROWS),
        'runs': [
            build_run_row(
                hurdle_payload,
                oracle_payload,
                experiment_id=experiment_id,
                research_version=research_version,
                git_commit=git_commit,
                hurdle_source_path=hurdle_source_path,
                oracle_source_path=oracle_source_path,
            )
        ],
        'model_selection': hurdle['model_selection'],
        'policy_metrics': hurdle['policy_metrics'],
        'bootstrap': hurdle['bootstrap'],
        'diagnostics': hurdle['diagnostics'],
        'oracle': flatten_oracle(oracle_payload, experiment_id=experiment_id),
    }


def create_client():
    try:
        from clickhouse_driver import Client
    except ImportError as exc:
        raise RuntimeError(
            'clickhouse-driver is required to load research reporting data'
        ) from exc

    return Client(
        host=os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
        port=int(os.getenv('CLICKHOUSE_PORT', '9000')),
        user=os.getenv('CLICKHOUSE_USER', 'default'),
        password=os.getenv('CLICKHOUSE_PASSWORD', 'default'),
        database=os.getenv('CLICKHOUSE_DATABASE', 'gold'),
    )


def insert_rows(
    client: Any,
    table: str,
    columns: Iterable[str],
    rows: list[tuple[Any, ...]],
):
    if not rows:
        return
    client.execute(
        INSERT_ROWS_Q_TEMPLATE.format(
            table=table,
            columns=', '.join(columns),
        ),
        rows,
        types_check=True,
    )


def delete_experiment(client: Any, table: str, experiment_id: str):
    escaped = experiment_id.replace('\'', '\'\'')
    client.execute(
        DELETE_EXPERIMENT_Q_TEMPLATE.format(
            table=table,
            experiment_id=escaped,
        )
    )


def replace_registry(client: Any):
    model_ids = ', '.join('\'{}\''.format(row[0]) for row in MODEL_REGISTRY_ROWS)
    policy_ids = ', '.join('\'{}\''.format(row[0]) for row in POLICY_REGISTRY_ROWS)

    client.execute(
        DELETE_RESEARCH_MODEL_REGISTRY_Q_TEMPLATE.format(
            model_ids=model_ids
        )
    )
    client.execute(
        DELETE_RESEARCH_POLICY_REGISTRY_Q_TEMPLATE.format(
            policy_ids=policy_ids
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description='Load final research artifacts into ClickHouse reporting tables.'
    )
    parser.add_argument('--hurdle-input', required=True)
    parser.add_argument('--oracle-input', required=True)
    parser.add_argument('--experiment-id', default='research_v1_0')
    parser.add_argument('--research-version', default='1.0')
    parser.add_argument('--git-commit')
    parser.add_argument('--replace', action='store_true')
    arguments = parser.parse_args()

    hurdle_payload = read_json(arguments.hurdle_input)
    oracle_payload = read_json(arguments.oracle_input)
    git_commit = resolve_git_commit(arguments.git_commit)

    rows = flatten_research_reporting(
        hurdle_payload,
        oracle_payload,
        experiment_id=arguments.experiment_id,
        research_version=arguments.research_version,
        git_commit=git_commit,
        hurdle_source_path=str(Path(arguments.hurdle_input)),
        oracle_source_path=str(Path(arguments.oracle_input)),
    )

    client = create_client()

    experiment_tables = (
        'gold.dim_research_experiment_runs',
        'gold.fact_research_model_selection',
        'gold.fact_research_policy_metrics',
        'gold.fact_research_bootstrap',
        'gold.fact_research_prediction_diagnostics',
        'gold.fact_research_oracle_horizon',
    )

    if arguments.replace:
        for table in experiment_tables:
            delete_experiment(client, table, arguments.experiment_id)
        replace_registry(client)

    insert_rows(
        client,
        'gold.dim_research_model_registry',
        MODEL_REGISTRY_COLUMNS,
        rows['model_registry'],
    )
    insert_rows(
        client,
        'gold.dim_research_policy_registry',
        POLICY_REGISTRY_COLUMNS,
        rows['policy_registry'],
    )
    insert_rows(
        client,
        'gold.dim_research_experiment_runs',
        RUN_COLUMNS,
        rows['runs'],
    )
    insert_rows(
        client,
        'gold.fact_research_model_selection',
        MODEL_SELECTION_COLUMNS,
        rows['model_selection'],
    )
    insert_rows(
        client,
        'gold.fact_research_policy_metrics',
        POLICY_METRIC_COLUMNS,
        rows['policy_metrics'],
    )
    insert_rows(
        client,
        'gold.fact_research_bootstrap',
        BOOTSTRAP_COLUMNS,
        rows['bootstrap'],
    )
    insert_rows(
        client,
        'gold.fact_research_prediction_diagnostics',
        DIAGNOSTIC_COLUMNS,
        rows['diagnostics'],
    )
    insert_rows(
        client,
        'gold.fact_research_oracle_horizon',
        ORACLE_COLUMNS,
        rows['oracle'],
    )

    print(f'''experiment_id={arguments.experiment_id}''')
    for name, values in rows.items():
        print(f'''{name}: {len(values)} rows''')


if __name__ == '__main__':
    main()
