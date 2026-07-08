from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from revolut_app.real_market.experiments import coupled_rg_final as coupled
from revolut_app.real_market.experiments.hurdle_economic_policy import (
    CandidateSummary,
    EconomicScenario,
    HurdleDayDataset,
    ModelSpec,
    PolicySpec,
    PredictionBundle,
    build_hurdle_day_dataset,
    calculate_policy_metrics,
    direct_action_fraction,
    fractional_notional_allocation,
    hurdle_action_fraction,
    model_spec_from_preset,
    predicted_net_bps,
    select_best_candidate,
)


def _dataset(
    markout: np.ndarray,
    notional: np.ndarray,
):
    return HurdleDayDataset(
        trade_date=date(2025, 1, 1),
        seconds=np.arange(markout.size),
        features=np.zeros((markout.size, 2), dtype=np.float32),
        feature_names=('a', 'b'),
        markout_bps=markout,
        positive_labels=(markout > 0).astype(np.uint8),
        break_even_labels=(markout > 4).astype(np.uint8),
        notional_usdt=notional,
        adverse_loss_usdt=(
            notional * np.maximum(markout, 0.0) / 10_000.0
        ),
    )


def test_fractional_allocation_respects_notional_budget():
    score = np.array([3.0, 2.0, 1.0])
    notional = np.array([60.0, 60.0, 60.0])

    result = fractional_notional_allocation(
        score,
        notional,
        budget_fraction=0.50,
    )

    assert result.tolist() == pytest.approx([1.0, 0.5, 0.0])
    assert np.sum(result * notional) == pytest.approx(90.0)


def test_expected_net_bps_formula():
    scenario = EconomicScenario('base', 0.50, 0.25, 0.50)
    result = predicted_net_bps(
        np.array([2.0, 4.0, 8.0]),
        scenario=scenario,
        multiplier=1.0,
    )
    assert result.tolist() == pytest.approx([-0.25, 0.0, 0.5])


def test_hurdle_policy_uses_probability_gate():
    scenario = EconomicScenario('base', 0.50, 0.25, 0.50)
    policy = PolicySpec(
        notional_budget_fraction=1.0,
        min_expected_net_margin_bps=0.0,
        min_break_even_probability=0.60,
        prediction_multiplier=1.0,
    )
    predictions = PredictionBundle(
        probability_positive=np.array([0.8, 0.8]),
        probability_break_even=np.array([0.7, 0.5]),
        conditional_positive_markout_bps=np.array([10.0, 10.0]),
        expected_positive_markout_bps=np.array([8.0, 8.0]),
        direct_expected_positive_markout_bps=np.array([8.0, 8.0]),
    )
    action, net = hurdle_action_fraction(
        predictions,
        np.array([100.0, 100.0]),
        scenario=scenario,
        policy=policy,
    )

    assert net.tolist() == pytest.approx([0.5, 0.5])
    assert action.tolist() == pytest.approx([1.0, 0.0])


def test_policy_metrics_can_be_profitable():
    scenario = EconomicScenario('base', 0.50, 0.25, 0.50)
    dataset = _dataset(
        np.array([10.0, 0.0]),
        np.array([1000.0, 1000.0]),
    )
    metrics = calculate_policy_metrics(
        action_fraction=np.array([1.0, 0.0]),
        dataset=dataset,
        scenario=scenario,
    )

    assert metrics.gross_protected_value_usdt == pytest.approx(0.125)
    assert metrics.action_cost_usdt == pytest.approx(0.05)
    assert metrics.net_value_per_million_usdt == pytest.approx(37.5)
    assert metrics.profitable


def test_candidate_selection_rejects_non_positive_result():
    spec = model_spec_from_preset('compact')
    policy = PolicySpec(0.01, 0.0, 0.5, 1.0)
    bad = CandidateSummary(
        horizon_seconds=300,
        model_spec=spec,
        policy_spec=policy,
        mean_daily_net_value_per_million_usdt=0.0,
        median_daily_net_value_per_million_usdt=0.0,
        std_daily_net_value_per_million_usdt=0.0,
        worst_day_net_value_per_million_usdt=0.0,
        positive_day_fraction=0.0,
        robust_score=0.0,
        accepted=False,
    )
    assert select_best_candidate([bad]) is None


def test_build_dataset_respects_stride_and_markout():
    shape = (coupled.SECONDS_PER_DAY, len(coupled.SYMBOLS))
    phi = np.zeros(shape, dtype=np.float32)
    log_volume = np.zeros(shape, dtype=np.float32)
    vwap = np.full(shape, np.nan, dtype=np.float64)
    active = np.zeros(shape, dtype=bool)

    for component in range(len(coupled.SYMBOLS)):
        vwap[:, component] = 100.0 + component
        active[:, component] = True
        log_volume[:, component] = np.log1p(1000.0)
        phi[:, component] = 0.1

    current = 1000
    horizon = 120
    target_index = coupled.SYMBOLS.index('BTCUSDT')
    vwap[current + horizon, target_index] = 100.10

    coarse_phi = np.repeat(
        phi[:, None, :],
        len(coupled.SCALES_SECONDS),
        axis=1,
    )
    day = coupled.MarketDay(
        trade_date=date(2025, 1, 1),
        phi=phi,
        log_volume=log_volume,
        vwap=vwap,
        active=active,
        coarse_phi=coarse_phi,
    )
    scenario = EconomicScenario('base', 0.50, 0.25, 0.50)

    dataset = build_hurdle_day_dataset(
        day,
        target_symbol='BTCUSDT',
        horizon_seconds=horizon,
        decision_stride_seconds=10,
        scenario=scenario,
    )

    assert np.all(dataset.seconds % 10 == 0)
    position = np.flatnonzero(dataset.seconds == current)
    assert position.size == 1
    assert dataset.markout_bps[position[0]] == pytest.approx(10.0)
    assert dataset.features.shape[1] == len(dataset.feature_names)
    assert np.all(np.isfinite(dataset.features))


def test_direct_action_uses_direct_prediction():
    scenario = EconomicScenario('base', 0.50, 0.25, 0.50)
    policy = PolicySpec(1.0, 0.0, 0.0, 1.0)
    predictions = PredictionBundle(
        probability_positive=np.array([0.1, 0.9]),
        probability_break_even=np.array([0.9, 0.9]),
        conditional_positive_markout_bps=np.array([1.0, 1.0]),
        expected_positive_markout_bps=np.array([0.1, 0.9]),
        direct_expected_positive_markout_bps=np.array([8.0, 2.0]),
    )
    action, _ = direct_action_fraction(
        predictions,
        np.array([100.0, 100.0]),
        scenario=scenario,
        policy=policy,
    )
    assert action.tolist() == pytest.approx([1.0, 0.0])
