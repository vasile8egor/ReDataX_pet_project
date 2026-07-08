from __future__ import annotations

from copy import deepcopy

from revolut_app.analytics.load_research_reporting import (
    flatten_research_reporting,
)


def metric(net: float) -> dict:
    return {
        "observations": 100,
        "acted_observations": 10,
        "acted_event_fraction": 0.10,
        "mean_action_fraction_on_acted_events": 1.0,
        "total_notional_usdt": 1_000_000.0,
        "acted_notional_usdt": 100_000.0,
        "acted_notional_fraction": 0.10,
        "total_adverse_loss_usdt": 100.0,
        "captured_adverse_loss_usdt": 20.0,
        "capture_rate": 0.20,
        "risk_concentration": 2.0,
        "gross_protected_value_usdt": 2.5,
        "action_cost_usdt": 0.5,
        "net_protected_value_usdt": net,
        "gross_value_per_million_usdt": 2.5,
        "net_value_per_million_usdt": net,
        "break_even_action_cost_bps": 2.5,
        "benefit_cost_ratio": 5.0,
        "profitable": net > 0,
    }


def candidate(horizon: int = 600) -> dict:
    return {
        "horizon_seconds": horizon,
        "model_spec": {"preset": "medium"},
        "policy_spec": {
            "notional_budget_fraction": 0.10,
            "min_expected_net_margin_bps": 0.10,
            "min_break_even_probability": 0.40,
            "prediction_multiplier": 1.0,
        },
        "mean_daily_net_value_per_million_usdt": 10.0,
        "median_daily_net_value_per_million_usdt": 9.0,
        "std_daily_net_value_per_million_usdt": 2.0,
        "worst_day_net_value_per_million_usdt": 4.0,
        "positive_day_fraction": 6 / 7,
        "robust_score": 9.0,
        "accepted": True,
    }


def evaluation() -> dict:
    policies = {
        "no_action": metric(0.0),
        "probability_budget": metric(8.0),
        "direct_economic": metric(7.0),
        "hurdle_economic": metric(12.0),
        "oracle_upper_bound": metric(48.0),
    }
    days = []
    for day in ("2025-02-10", "2025-02-11"):
        days.append(
            {
                "date": day,
                "policies": deepcopy(policies),
                "prediction_diagnostics": {
                    "probability_positive_mean": 0.50,
                    "probability_break_even_mean": 0.40,
                    "expected_positive_markout_p95_bps": 8.0,
                    "expected_positive_markout_max_bps": 20.0,
                    "direct_expected_markout_p95_bps": 7.0,
                    "hurdle_predicted_net_positive_fraction": 0.10,
                    "direct_predicted_net_positive_fraction": 0.05,
                },
                "comparisons": {},
            }
        )
    return {
        "daily": days,
        "aggregate": policies,
        "oracle_capture_fraction": 0.25,
        "bootstrap": {
            "hurdle_minus_no_action": {
                "days": 2,
                "mean": 12.0,
                "ci_025": 10.0,
                "ci_975": 14.0,
                "positive_day_fraction": 1.0,
            },
            "hurdle_minus_probability": {
                "days": 2,
                "mean": 4.0,
                "ci_025": 2.0,
                "ci_975": 6.0,
                "positive_day_fraction": 1.0,
            },
            "hurdle_minus_direct": {
                "days": 2,
                "mean": 5.0,
                "ci_025": 3.0,
                "ci_975": 7.0,
                "positive_day_fraction": 1.0,
            },
        },
    }


def test_flatten_research_reporting() -> None:
    selected = candidate()
    hurdle = {
        "configuration": {
            "scenario": {
                "name": "base",
                "mitigation_efficiency": 0.50,
                "internalization_rate": 0.25,
                "action_cost_bps": 0.50,
            },
            "break_even_markout_bps": 4.0,
            "decision_stride_seconds": 10,
            "train_dates": ["2025-01-06", "2025-01-26"],
            "development_dates": ["2025-01-27", "2025-02-02"],
            "validation_dates": ["2025-02-03", "2025-02-09"],
            "final_test_dates": ["2025-02-10", "2025-02-16"],
            "bootstrap_samples": 5000,
        },
        "targets": {
            "BTCUSDT": {
                "development": {
                    "600": {
                        "winner": selected,
                        "leaderboard_top20": [
                            selected,
                            {**candidate(), "robust_score": 8.0},
                        ],
                    }
                },
                "validation": {
                    "600": {
                        "candidate": selected,
                        "evaluation": evaluation(),
                    }
                },
                "selected_final_candidate": selected,
                "status": "final_candidate_evaluated",
                "final_test": evaluation(),
            }
        },
    }

    oracle_candidate = {
        "target_symbol": "BTCUSDT",
        "horizon_seconds": 600,
        "notional_budget_fraction": 0.10,
        "aggregate_net_value_per_million_usdt": 50.0,
        "mean_daily_net_value_per_million_usdt": 45.0,
        "robust_score": 40.0,
        "positive_day_fraction": 1.0,
        "bootstrap_ci_lower": 30.0,
        "bootstrap_ci_upper": 60.0,
        "strictly_feasible": True,
        "above_break_even_event_fraction": 0.4,
        "above_break_even_notional_fraction": 0.5,
        "acted_notional_fraction": 0.1,
        "capture_rate": 0.5,
        "break_even_action_cost_bps": 5.0,
        "benefit_cost_ratio": 10.0,
    }
    oracle = {
        "configuration": {"break_even_markout_bps": 4.0},
        "targets": {
            "BTCUSDT": {
                "recommendations": {
                    "best_by_robust_score": oracle_candidate,
                    "capital_efficient_candidate": oracle_candidate,
                },
                "candidate_ranking": [oracle_candidate],
            }
        },
    }

    rows = flatten_research_reporting(
        hurdle,
        oracle,
        experiment_id="research_v1_0",
        research_version="1.0",
        git_commit="abc123",
        hurdle_source_path="hurdle.json",
        oracle_source_path="oracle.json",
    )

    assert len(rows["runs"]) == 1
    assert len(rows["model_registry"]) == 8
    assert len(rows["policy_registry"]) == 5
    assert len(rows["model_selection"]) == 4

    # validation: 2 days * 5 policies + 5 aggregate
    # final:      2 days * 5 policies + 5 aggregate
    assert len(rows["policy_metrics"]) == 30
    assert len(rows["bootstrap"]) == 6
    assert len(rows["diagnostics"]) == 4
    assert len(rows["oracle"]) == 1

    aggregate_hurdle = [
        row
        for row in rows["policy_metrics"]
        if row[1] == "aggregate"
        and row[3] == "final"
        and row[9] == "P3"
    ]
    assert len(aggregate_hurdle) == 1
    assert aggregate_hurdle[0][33] == 0.25
