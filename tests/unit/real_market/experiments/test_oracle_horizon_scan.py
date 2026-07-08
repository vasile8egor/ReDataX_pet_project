from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from revolut_app.real_market.experiments import coupled_rg_final as coupled
from revolut_app.real_market.experiments.oracle_horizon_scan import (
    OracleDayData,
    OracleMetrics,
    OracleScenario,
    aggregate_oracle_metrics,
    build_oracle_day_data,
    distribution_metrics,
    oracle_metrics_for_budgets,
    select_recommendations,
    stability_metrics,
)


def test_break_even_markout():
    scenario = OracleScenario('base', 0.50, 0.25, 0.50)
    assert scenario.protection_fraction == pytest.approx(0.125)
    assert scenario.break_even_markout_bps == pytest.approx(4.0)


def test_oracle_partial_budget_is_exact_and_profitable():
    scenario = OracleScenario('base', 0.50, 0.25, 0.50)
    data = OracleDayData(
        markout_bps=np.array([12.0, 8.0, 1.0]),
        notional_usdt=np.array([60.0, 60.0, 60.0]),
        adverse_loss_usdt=np.array([
            60.0 * 12.0 / 10_000.0,
            60.0 * 8.0 / 10_000.0,
            60.0 * 1.0 / 10_000.0,
        ]),
    )

    metrics = oracle_metrics_for_budgets(
        data,
        scenario=scenario,
        budget_fractions=(0.50,),
    )[0.50]

    assert metrics.acted_notional_usdt == pytest.approx(90.0)
    assert metrics.acted_observations == 2
    assert (
        metrics.mean_action_fraction_on_acted_events
        == pytest.approx(0.75)
    )
    assert metrics.net_protected_value_usdt > 0.0
    assert metrics.profitable


def test_oracle_does_not_act_below_break_even():
    scenario = OracleScenario('base', 0.50, 0.25, 0.50)
    data = OracleDayData(
        markout_bps=np.array([1.0, 2.0, 4.0]),
        notional_usdt=np.array([100.0, 100.0, 100.0]),
        adverse_loss_usdt=np.array([0.01, 0.02, 0.04]),
    )

    metrics = oracle_metrics_for_budgets(
        data,
        scenario=scenario,
        budget_fractions=(1.0,),
    )[1.0]

    assert metrics.acted_observations == 0
    assert metrics.net_value_per_million_usdt == 0.0


def test_distribution_uses_strict_break_even_threshold():
    data = OracleDayData(
        markout_bps=np.array([-1.0, 0.0, 4.0, 5.0]),
        notional_usdt=np.array([10.0, 10.0, 10.0, 70.0]),
        adverse_loss_usdt=np.zeros(4),
    )
    result = distribution_metrics(
        data,
        break_even_markout_bps=4.0,
    )

    assert result.positive_markout_fraction == pytest.approx(0.5)
    assert (
        result.above_break_even_event_fraction
        == pytest.approx(0.25)
    )
    assert (
        result.above_break_even_notional_fraction
        == pytest.approx(0.70)
    )


def test_build_oracle_day_data_matches_markout_definition():
    shape = (coupled.SECONDS_PER_DAY, len(coupled.SYMBOLS))
    phi = np.zeros(shape, dtype=np.float32)
    vwap = np.full(shape, np.nan, dtype=np.float64)
    active = np.zeros(shape, dtype=bool)
    notional = np.zeros(shape, dtype=np.float64)

    target_index = coupled.SYMBOLS.index('BTCUSDT')
    current_second = max(coupled.SCALES_SECONDS)
    future_second = current_second + 10

    phi[current_second, target_index] = 1.0
    active[current_second, target_index] = True
    vwap[current_second, target_index] = 100.0
    vwap[future_second, target_index] = 100.10
    notional[current_second, target_index] = 1000.0

    day = coupled.MarketDay(
        trade_date=date(2025, 1, 27),
        phi=phi,
        log_volume=np.zeros(shape, dtype=np.float32),
        vwap=vwap,
        active=active,
        coarse_phi=np.zeros(
            (
                coupled.SECONDS_PER_DAY,
                len(coupled.SCALES_SECONDS),
                len(coupled.SYMBOLS),
            ),
            dtype=np.float32,
        ),
    )

    result = build_oracle_day_data(
        day,
        notional,
        target_symbol='BTCUSDT',
        horizon_seconds=10,
    )

    assert result.markout_bps.tolist() == pytest.approx([10.0])
    assert result.notional_usdt.tolist() == pytest.approx([1000.0])
    assert result.adverse_loss_usdt.tolist() == pytest.approx([1.0])


def test_stability_and_recommendation():
    template = dict(
        observations=100,
        acted_observations=1,
        acted_event_fraction=0.01,
        mean_action_fraction_on_acted_events=1.0,
        total_notional_usdt=1_000_000.0,
        acted_notional_usdt=10_000.0,
        acted_notional_fraction=0.01,
        total_adverse_loss_usdt=100.0,
        captured_adverse_loss_usdt=10.0,
        capture_rate=0.10,
        risk_concentration=10.0,
        gross_protected_value_usdt=1.25,
        action_cost_usdt=0.50,
        gross_value_per_million_usdt=1.25,
        break_even_action_cost_bps=1.25,
        benefit_cost_ratio=2.5,
        profitable=True,
    )
    daily = [
        OracleMetrics(
            **template,
            net_protected_value_usdt=value,
            net_value_per_million_usdt=value,
        )
        for value in (3.0, 4.0, 5.0, 4.0, 3.0, 2.0, 4.0)
    ]
    stability = stability_metrics(
        daily,
        risk_penalty=0.5,
        minimum_positive_day_fraction=5.0 / 7.0,
        bootstrap_samples=500,
        seed=42,
    )
    assert stability.strictly_feasible

    candidate = {
        'horizon_seconds': 30,
        'notional_budget_fraction': 0.01,
        'robust_score': stability.robust_score,
        'mean_daily_net_value_per_million_usdt': (
            stability.mean_daily_net_value_per_million_usdt
        ),
        'strictly_feasible': True,
    }
    recommendation = select_recommendations([candidate])
    assert (
        recommendation['status']
        == 'strictly_feasible_oracle_candidates_found'
    )


def test_aggregate_recomputes_from_sums():
    scenario = OracleScenario('base', 0.50, 0.25, 0.50)
    data = OracleDayData(
        markout_bps=np.array([10.0, 0.0]),
        notional_usdt=np.array([100.0, 100.0]),
        adverse_loss_usdt=np.array([0.10, 0.0]),
    )
    first = oracle_metrics_for_budgets(
        data,
        scenario=scenario,
        budget_fractions=(0.5,),
    )[0.5]
    aggregate = aggregate_oracle_metrics(
        [first, first],
        scenario=scenario,
    )

    assert aggregate.observations == 4
    assert aggregate.acted_notional_usdt == pytest.approx(200.0)
    assert aggregate.net_protected_value_usdt > 0.0
