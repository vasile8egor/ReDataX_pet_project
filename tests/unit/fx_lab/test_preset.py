import pytest

from revolut_app.fx_lab.shared.enums import HamiltonianPreset, Currency
from revolut_app.fx_lab.experiments import (
    PolicyComparisonEngine,
)
from revolut_app.fx_lab.pricing.policies import QuotePolicyName
from revolut_app.fx_lab.risk.hamiltonian import (
    HamiltonianController,
    build_hamiltonian_controller,
    build_hamiltonian_parameters,
    build_hamiltonian_engine
)


def test_local_preset_hasnt_couplings():
    parameters = build_hamiltonian_parameters(HamiltonianPreset.local_v1)

    assert parameters.couplings == ()
    assert parameters.preset_name == 'threshold-local-v1'


def test_coupled_preset_has_expected_signs():
    parameters = build_hamiltonian_parameters(HamiltonianPreset.coupled_v1)
    signs = {
        (
            coupling.left_currency,
            coupling.right_currency
        ): coupling.relation_sign
        for coupling in parameters.couplings
    }

    assert signs == {
        (
            Currency.EUR,
            Currency.GBP,
        ): 1,
        (
            Currency.EUR,
            Currency.USD,
        ): -1,
        (
            Currency.GBP,
            Currency.USD,
        ): -1,
    }


def test_coupled_preset_has_expected_strength():
    parameters = build_hamiltonian_parameters(HamiltonianPreset.coupled_v1)

    assert len(parameters.couplings) == 3
    assert all(
        coupling.strength == pytest.approx(0.2)
        for coupling in parameters.couplings
    )


def test_eur_gbp_positive_relation():
    engine = build_hamiltonian_engine(HamiltonianPreset.coupled_v1)
    aligned = engine.evaluate({'EUR': 0.7, 'GBP': 0.7, 'USD': 0.0, })
    opposite = engine.evaluate({'EUR': 0.7, 'GBP': -0.7, 'USD': 0.0, })
    assert opposite.coupling > aligned.coupling


def test_eur_usd_negative_relation():
    engine = build_hamiltonian_engine(HamiltonianPreset.coupled_v1)
    aligned = engine.evaluate({'EUR': 0.7, 'GBP': 0.0, 'USD': -0.7, })
    same_sign = engine.evaluate({'EUR': 0.7, 'GBP': 0.0, 'USD': 0.7, })
    assert same_sign.coupling > aligned.coupling


def test_build_hamiltonian_controller():
    controller = build_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    assert isinstance(
        controller,
        HamiltonianController,
    )

    assert (
        controller.parameters.activation_energy
        == pytest.approx(0.70)
    )


def test_coupled_observer_does_not_change_business_results(
    fx_event_dataset,
):
    comparison_engine = PolicyComparisonEngine()

    local_result = comparison_engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=150.0,
        snapshot_every_n_events=10,
        hamiltonian_engine=(
            build_hamiltonian_engine(
                HamiltonianPreset.local_v1
            )
        ),
    )

    coupled_result = comparison_engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=150.0,
        snapshot_every_n_events=10,
        hamiltonian_engine=(
            build_hamiltonian_engine(
                HamiltonianPreset.coupled_v1
            )
        ),
    )

    local_run = local_result.results[0]
    coupled_run = coupled_result.results[0]

    assert (
        local_run.accepted_events
        == coupled_run.accepted_events
    )
    assert (
        local_run.rejected_events
        == coupled_run.rejected_events
    )
    assert (
        local_run.net_pnl_usd
        == coupled_run.net_pnl_usd
    )
    assert (
        local_run.final_inventory_pressure
        == coupled_run.final_inventory_pressure
    )

    assert any(
        snapshot.h_coupling == 0.0
        for snapshot in local_run.snapshots
    )

    assert any(
        snapshot.h_coupling is not None
        and snapshot.h_coupling > 0.0
        for snapshot in coupled_run.snapshots
    )

    assert all(
        snapshot.controller_activated is None
        for run in coupled_result.results
        for snapshot in run.snapshots
    )


def test_controller_snapshots_capture_activation(
    fx_event_dataset,
):
    comparison_engine = PolicyComparisonEngine()

    result = comparison_engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
        hamiltonian_controller=(
            build_hamiltonian_controller(
                HamiltonianPreset.local_v1
            )
        ),
    )

    controller_snapshots = [
        snapshot
        for run in result.results
        for snapshot in run.snapshots
        if snapshot.controller_activated is not None
    ]

    assert controller_snapshots

    assert any(
        snapshot.controller_activated
        for snapshot in controller_snapshots
    )

    assert any(
        snapshot.controller_spread_adjustment_bps > 0
        for snapshot in controller_snapshots
        if snapshot.controller_spread_adjustment_bps
        is not None
    )
