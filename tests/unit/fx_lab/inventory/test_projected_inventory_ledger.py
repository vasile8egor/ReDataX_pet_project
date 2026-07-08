import pytest

from revolut_app.fx_lab.inventory.ledger import (
    InventoryLedger,
)
from revolut_app.fx_lab.pricing.models import (
    QuoteRequest,
)
from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
    HamiltonianPreset,
)


def test_projected_inventory_can_be_evaluated_as_transition():
    ledger = InventoryLedger()

    request = QuoteRequest(
        customer_id='transition-test',
        base_currency=Currency.EUR,
        quote_currency=Currency.USD,
        side=FXSide.buy,
        amount=10_000.0,
        segment=CustomerSegment.retail,
    )

    pressures_before = ledger.pressures()

    projected_ledger = ledger.project_after_client_fx(
        request=request,
        mid_rate=1.10,
    )

    pressures_after = projected_ledger.pressures()

    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    transition = engine.evaluate_transition(
        pressures_before=pressures_before,
        pressures_after=pressures_after,
    )

    assert transition.h_before >= 0.0
    assert transition.h_after >= 0.0

    assert transition.delta_total == pytest.approx(
        transition.h_after
        - transition.h_before
    )

    assert ledger.pressures() == pressures_before


def test_transition_supports_coupled_hamiltonian():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.coupled_v1
    )

    transition = engine.evaluate_transition(
        pressures_before={
            'EUR': 0.20,
            'GBP': 0.10,
            'USD': -0.10,
        },
        pressures_after={
            'EUR': 0.30,
            'GBP': 0.05,
            'USD': -0.20,
        },
    )

    expected_coupling_delta = (
        transition.after.coupling
        - transition.before.coupling
    )

    assert transition.delta_total == pytest.approx(
        transition.h_after
        - transition.h_before
    )

    assert expected_coupling_delta == pytest.approx(
        transition.after.coupling
        - transition.before.coupling
    )
