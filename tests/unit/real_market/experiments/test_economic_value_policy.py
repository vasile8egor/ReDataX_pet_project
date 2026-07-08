from __future__ import annotations

import numpy as np
import pytest

from revolut_app.real_market.experiments.economic_value_policy import (
    CandidateSummary,
    EconomicScenario,
    PolicySpec,
    ValueModelSpec,
    calculate_policy_metrics,
    economic_action_fractions,
    fractional_notional_allocation,
    select_candidate,
    summarize_candidate,
)


def test_fractional_notional_allocation_respects_exact_budget() -> None:
    score = np.array([4.0, 3.0, 2.0])
    notional = np.array([60.0, 60.0, 60.0])

    allocation = fractional_notional_allocation(
        score,
        notional,
        budget_fraction=0.50,
    )

    assert allocation.tolist() == pytest.approx([1.0, 0.5, 0.0])
    assert np.sum(allocation * notional) == pytest.approx(90.0)


def test_economic_policy_does_not_act_below_cost() -> None:
    scenario = EconomicScenario("base", 0.50, 0.25, 0.50)
    prediction = np.array([1.0, 3.0, 5.0])
    notional = np.array([100.0, 100.0, 100.0])
    policy = PolicySpec(1.0, 0.0)

    allocation, predicted_net = economic_action_fractions(
        prediction,
        notional,
        scenario=scenario,
        policy=policy,
    )

    # Protection fraction is 12.5%; 5 bps predicts 0.625 bps gross,
    # while 1 and 3 bps remain below the 0.50 bps action cost.
    assert predicted_net.tolist() == pytest.approx([-0.375, -0.125, 0.125])
    assert allocation.tolist() == pytest.approx([0.0, 0.0, 1.0])


def test_realized_policy_metrics_can_be_profitable() -> None:
    scenario = EconomicScenario("base", 0.50, 0.25, 0.50)
    action = np.array([1.0, 0.0])
    notional = np.array([1000.0, 1000.0])
    losses = np.array([1.0, 0.0])

    metrics = calculate_policy_metrics(
        action_fraction=action,
        losses_usdt=losses,
        notional_usdt=notional,
        scenario=scenario,
    )

    assert metrics.gross_protected_value_usdt == pytest.approx(0.125)
    assert metrics.action_cost_usdt == pytest.approx(0.05)
    assert metrics.net_protected_value_usdt == pytest.approx(0.075)
    assert metrics.net_value_per_million_usdt == pytest.approx(37.5)
    assert metrics.profitable


def test_no_action_has_zero_value_not_negative_value() -> None:
    scenario = EconomicScenario("base", 0.50, 0.25, 0.50)
    metrics = calculate_policy_metrics(
        action_fraction=np.zeros(3),
        losses_usdt=np.array([1.0, 2.0, 3.0]),
        notional_usdt=np.array([100.0, 100.0, 100.0]),
        scenario=scenario,
    )

    assert metrics.net_protected_value_usdt == 0.0
    assert metrics.net_value_per_million_usdt == 0.0
    assert not metrics.profitable


def test_candidate_summary_requires_robust_positive_days() -> None:
    scenario = EconomicScenario("base", 0.50, 0.25, 0.50)
    daily = []
    for net in (10.0, 9.0, 8.0, 7.0, 6.0, -1.0, -2.0):
        # Construct metrics with the desired normalized value.
        total_notional = 1_000_000.0
        net_value = net
        daily.append(
            calculate_policy_metrics(
                action_fraction=np.array([1.0]),
                losses_usdt=np.array([(net_value + 50.0) / 0.125]),
                notional_usdt=np.array([total_notional]),
                scenario=scenario,
            )
        )

    summary = summarize_candidate(
        model_spec=ValueModelSpec(1e-3, 10.0, 0.5),
        policy_spec=PolicySpec(0.01, 0.1),
        daily_metrics=daily,
        risk_penalty=0.5,
        minimum_positive_day_fraction=5.0 / 7.0,
    )
    assert summary.positive_day_fraction == pytest.approx(5.0 / 7.0)
    assert summary.development_profitable


def test_select_candidate_returns_none_without_profitable_policy() -> None:
    bad = CandidateSummary(
        model_spec=ValueModelSpec(1e-3, 10.0, 0.5),
        policy_spec=PolicySpec(0.01, 0.1),
        mean_daily_net_value_per_million=-1.0,
        median_daily_net_value_per_million=-1.0,
        std_daily_net_value_per_million=0.1,
        worst_day_net_value_per_million=-1.2,
        positive_day_fraction=0.0,
        robust_score=-1.05,
        development_profitable=False,
    )
    assert select_candidate([bad]) is None
