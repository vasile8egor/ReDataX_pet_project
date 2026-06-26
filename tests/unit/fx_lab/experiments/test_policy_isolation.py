from revolut_app.fx_lab.pricing.policies import QuotePolicyName
from revolut_app.fx_lab.experiments import PolicyComparisonEngine
from revolut_app.fx_lab.inventory.ledger import InventoryLedger

from .test_policy_reproducibility import _policy_signature


def test_policy_results_dont_depend_on_execution_order(fx_event_dataset):
    engine = PolicyComparisonEngine()

    forward = engine.compare(
        policy_names=[
            QuotePolicyName.naive,
            QuotePolicyName.inventory_aware,
            QuotePolicyName.platform,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
    )
    reverse = engine.compare(
        policy_names=[
            QuotePolicyName.platform,
            QuotePolicyName.inventory_aware,
            QuotePolicyName.naive,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
    )
    forward_by_policy = {
        item.policy: _policy_signature(item)
        for item in forward.results
    }
    reverse_by_policy = {
        item.policy: _policy_signature(item)
        for item in reverse.results
    }

    assert forward_by_policy == reverse_by_policy


def test_comparison_doesnt_mutate_event_dataset(fx_event_dataset):
    original_amounts = [
        event.request.amount
        for event in fx_event_dataset.events
    ]

    engine = PolicyComparisonEngine()
    engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=10_000.0,
        snapshot_every_n_events=10,
    )
    amount_after_run = [
        event.request.amount
        for event in fx_event_dataset.events
    ]

    assert original_amounts == amount_after_run


def test_different_amount_multiplier(fx_event_dataset):
    engine = PolicyComparisonEngine()
    small = engine.compare(
        policy_names=[QuotePolicyName.inventory_aware],
        event_dataset=fx_event_dataset,
        amount_multiplier=10.0,
        snapshot_every_n_events=10,
    )
    large = engine.compare(
        policy_names=[QuotePolicyName.inventory_aware],
        event_dataset=fx_event_dataset,
        amount_multiplier=1000.0,
        snapshot_every_n_events=10,
    )

    small_result = small.results[0]
    large_result = large.results[0]

    assert small.event_dataset_id == large.event_dataset_id
    assert (
        small_result.final_inventory_pressure
        != large_result.final_inventory_pressure
    )


def test_initial_snapshot_represents_pre_event_state(fx_event_dataset):
    result = PolicyComparisonEngine().compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
    )

    snapshots = result.results[0].snapshots

    initial_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.event_index == 0
    ]
    assert len(initial_snapshots) == 3

    initial_ledger = InventoryLedger()
    expected_positions = {
        currency: state.position
        for currency, state in initial_ledger.get_all_states().items()
    }
    expected_pressures = initial_ledger.pressures()

    for snapshot in initial_snapshots:
        assert snapshot.source_event_id is None
        assert snapshot.source_step_index is None
        assert snapshot.snapshot_ts == fx_event_dataset.started_at
        assert snapshot.position == expected_positions[snapshot.currency]
        assert snapshot.phi == expected_pressures[snapshot.currency.value]
        assert snapshot.cumulative_accepted_events == 0
        assert snapshot.cumulative_rejected_events == 0
        assert snapshot.cumulative_spread_revenue_usd == 0.0


def test_final_event_is_always_snapshotted(fx_event_dataset):
    result = PolicyComparisonEngine().compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=137,
    )
    last_event = fx_event_dataset.events[-1]

    final_snapshots = [
        snapshot for snapshot in result.results[0].snapshots
        if snapshot.event_index == last_event.event_sequence
    ]

    assert len(final_snapshots) == 3
    assert {
        snapshot.source_event_id
        for snapshot in final_snapshots
    } == {last_event.event_id}
