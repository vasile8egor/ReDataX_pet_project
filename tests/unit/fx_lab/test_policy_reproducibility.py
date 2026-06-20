from revolut_app.fx_lab.policies import QuotePolicyName
from revolut_app.fx_lab.policy_comparison import (
    PolicyComparisonEngine
)


def _round(value: float):
    return round(value, 8)


def _policy_signature(result):
    return {
        'policy': result.policy.value,
        'generated_requests': result.generated_requests,
        'accepted_events': result.accepted_events,
        'rejected_events': result.rejected_events,
        'acceptance_rate': result.acceptance_rate,
        'average_quoted_spread_bps': _round(
            result.average_quoted_spread_bps
        ),
        'average_accepted_spread_bps': _round(
            result.average_accepted_spread_bps
        ),
        'spread_revenue_usd': _round(
            result.spread_revenue_usd
        ),
        'allocated_product_revenue_usd': _round(
            result.allocated_product_revenue_usd
        ),
        'funding_cost_usd': _round(
            result.funding_cost_usd
        ),
        'net_pnl_usd': _round(result.net_pnl_usd),
        'final_regime': result.final_regime.value,
        'max_abs_pressure': _round(
            result.max_abs_pressure
        ),
        'stress_time_fraction': _round(
            result.stress_time_fraction
        ),
        'final_inventory_pressure': {
            currency: _round(value)
            for currency, value in sorted(
                result.final_inventory_pressure.items()
            )
        },
        'snapshots': [
            (
                snapshot.event_index,
                snapshot.source_event_id,
                snapshot.source_step_index,
                snapshot.snapshot_ts,
                snapshot.currency.value,
                _round(snapshot.position),
                _round(snapshot.phi),
                snapshot.regime.value,
                snapshot.event_accepted,
                _round(snapshot.acceptance_probability),
            )
            for snapshot in result.snapshots
        ],
    }


def test_same_dataset_produces_same_policy_results(fx_event_dataset):
    engine = PolicyComparisonEngine()

    first = engine.compare(
        policy_names=[
            QuotePolicyName.naive,
            QuotePolicyName.inventory_aware,
            QuotePolicyName.platform,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
    )
    second = engine.compare(
        policy_names=[
            QuotePolicyName.naive,
            QuotePolicyName.inventory_aware,
            QuotePolicyName.platform,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
    )

    assert first.event_dataset_id == second.event_dataset_id
    assert first.generated_requests == second.generated_requests
    assert first.comparison_id != second.comparison_id

    first_results = {
        item.policy: _policy_signature(item)
        for item in second.results
    }

    second_results = {
        item.policy: _policy_signature(item)
        for item in first.results
    }

    assert first_results == second_results
