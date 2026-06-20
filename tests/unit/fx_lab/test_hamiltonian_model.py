import pytest

from revolut_app.fx_lab.hamiltonian import (
    HamiltonianEngine,
    HamiltonianParameters,
    SignedCoupling,
)
from revolut_app.fx_lab.models import Currency
from revolut_app.fx_lab.policy_comparison import PolicyComparisonEngine
from revolut_app.fx_lab.policies import QuotePolicyName


def test_zero_pressure_has_zero_hamiltonian():
    engine = HamiltonianEngine(HamiltonianParameters.threshold_v1())
    result = engine.evaluate(
        {
            'EUR': 0.0,
            'USD': 0.0,
            'GBP': 0.0,
        }
    )

    assert result.total == 0.0
    assert result.quadratic == 0.0
    assert result.quartic == 0.0


def test_local_hamiltonian_is_even():
    engine = HamiltonianEngine(HamiltonianParameters.threshold_v1())
    positive = engine.evaluate(
        {
            'EUR': 0.8,
            'USD': 0.0,
            'GBP': 0.0,
        }
    )
    negative = engine.evaluate(
        {
            'EUR': -0.8,
            'USD': 0.0,
            'GBP': 0.0,
        }
    )

    assert positive.total == pytest.approx(negative.total)


def test_threshold_calibration():
    engine = HamiltonianEngine(HamiltonianParameters.threshold_v1())
    elevated = engine.evaluate(
        {
            'EUR': 0.6,
            'USD': 0.0,
            'GBP': 0.0,
        }
    )
    stress = engine.evaluate(
        {
            'EUR': 0.9,
            'USD': 0.0,
            'GBP': 0.0,
        }
    )

    assert elevated.total == pytest.approx(1.0, rel=1e-6)
    assert stress.total == pytest.approx(3.0, rel=1e-6)


def test_breakdown_components_sum_to_total():
    engine = HamiltonianEngine(HamiltonianParameters.threshold_v1())

    result = engine.evaluate({'EUR': 0.7})

    assert result.quadratic > 0.0
    assert result.quartic > 0.0
    assert result.total == pytest.approx(
        result.quadratic
        + result.quartic
        + result.coupling
        + result.external
    )


def test_coupling_rejects_invalid_relation_sign():
    with pytest.raises(ValueError, match='either -1 or 1'):
        SignedCoupling(
            left_currency=Currency.EUR,
            right_currency=Currency.USD,
            strength=1.0,
            relation_sign=0,
        )


def test_observer_does_not_change_policy_result(fx_event_dataset):
    engine = PolicyComparisonEngine()
    hamiltonian_engine = HamiltonianEngine(
        HamiltonianParameters.threshold_v1()
    )
    baseline = engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
        hamiltonian_engine=None,
    )
    observer = engine.compare(
        policy_names=[
            QuotePolicyName.inventory_aware
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
        hamiltonian_engine=hamiltonian_engine,
    )

    baseline_run = baseline.results[0]
    observer_run = observer.results[0]

    assert baseline_run.accepted_events == observer_run.accepted_events
    assert baseline_run.rejected_events == observer_run.rejected_events
    assert baseline_run.net_pnl_usd == observer_run.net_pnl_usd
    assert (
        baseline_run.final_inventory_pressure
        == observer_run.final_inventory_pressure
    )
    assert all(
        snapshot.h_total is None
        for snapshot in baseline_run.snapshots
    )
    assert all(
        snapshot.h_total is not None
        for snapshot in observer_run.snapshots
    )
