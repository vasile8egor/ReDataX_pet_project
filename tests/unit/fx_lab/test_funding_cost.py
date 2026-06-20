import pytest

from revolut_app.fx_lab.constants import SECONDS_PER_YEAR
from revolut_app.fx_lab.models import Currency
from revolut_app.fx_lab.policy_comparison import (
    PolicyComparisonEngine
)
from revolut_app.fx_lab.state_engine import InventoryLedger


def _zero_inventory(ledger: InventoryLedger) -> None:
    for state in ledger.get_all_states().values():
        state.position = 0.0


def test_funding_cost_for_one_year():
    ledger = InventoryLedger()
    _zero_inventory(ledger)
    state = ledger.get_state(Currency.EUR)
    state.position = 100_000.0
    state.funding_cost_bps = 10.0

    cost = (
        PolicyComparisonEngine._funding_cost_interval(
            ledger=ledger,
            elapsed_seconds=SECONDS_PER_YEAR,
        )
    )

    assert cost == pytest.approx(108.0, rel=1e-9,)


def test_zero_inventory_has_zero_funding_cost():
    ledger = InventoryLedger()
    _zero_inventory(ledger)

    cost = (
        PolicyComparisonEngine._funding_cost_interval(
            ledger=ledger,
            elapsed_seconds=SECONDS_PER_YEAR,
        )
    )

    assert cost == 0.0


def test_zero_elapsed_time_has_zero_funding_cost():
    ledger = InventoryLedger()
    ledger.get_state(Currency.EUR).position = 100_000.0

    cost = (
        PolicyComparisonEngine._funding_cost_interval(
            ledger=ledger,
            elapsed_seconds=0.0,
        )
    )

    assert cost == 0.0
