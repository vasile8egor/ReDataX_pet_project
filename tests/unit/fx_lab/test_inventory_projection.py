from revolut_app.fx_lab.inventory.ledger import (
    InventoryLedger,
)
from revolut_app.fx_lab.pricing.models import (
    QuoteRequest,
)
from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
)


def build_request() -> QuoteRequest:
    return QuoteRequest(
        customer_id='projection-test',
        base_currency=Currency.EUR,
        quote_currency=Currency.USD,
        side=FXSide.buy,
        amount=10_000.0,
        segment=CustomerSegment.retail,
    )


def test_projection_does_not_mutate_original_ledger():
    ledger = InventoryLedger()
    request = build_request()

    positions_before = {
        currency: state.position
        for currency, state
        in ledger.get_all_states().items()
    }

    buy_ewma_before = {
        currency: state.order_flow_buy_ewma
        for currency, state
        in ledger.get_all_states().items()
    }

    sell_ewma_before = {
        currency: state.order_flow_sell_ewma
        for currency, state
        in ledger.get_all_states().items()
    }

    pressures_before = ledger.pressures()

    projected = ledger.project_after_client_fx(
        request=request,
        mid_rate=1.10,
    )

    assert projected is not ledger

    assert ledger.pressures() == pressures_before

    assert {
        currency: state.position
        for currency, state
        in ledger.get_all_states().items()
    } == positions_before

    assert {
        currency: state.order_flow_buy_ewma
        for currency, state
        in ledger.get_all_states().items()
    } == buy_ewma_before

    assert {
        currency: state.order_flow_sell_ewma
        for currency, state
        in ledger.get_all_states().items()
    } == sell_ewma_before


def test_projection_matches_real_ledger_mutation():
    source_ledger = InventoryLedger()
    request = build_request()
    mid_rate = 1.10

    projected = source_ledger.project_after_client_fx(
        request=request,
        mid_rate=mid_rate,
    )

    actually_mutated = source_ledger.copy()

    actually_mutated.apply_client_fx(
        request=request,
        mid_rate=mid_rate,
    )

    assert (
        projected.pressures()
        == actually_mutated.pressures()
    )

    for currency in Currency:
        projected_state = projected.get_state(currency)
        actual_state = actually_mutated.get_state(
            currency
        )

        assert (
            projected_state.position
            == actual_state.position
        )

        assert (
            projected_state.order_flow_buy_ewma
            == actual_state.order_flow_buy_ewma
        )

        assert (
            projected_state.order_flow_sell_ewma
            == actual_state.order_flow_sell_ewma
        )


def test_ledger_copy_has_independent_states():
    ledger = InventoryLedger()
    copied = ledger.copy()

    for currency in Currency:
        assert (
            copied.get_state(currency)
            is not ledger.get_state(currency)
        )

    copied.get_state(Currency.EUR).position = 500.0

    assert (
        ledger.get_state(Currency.EUR).position
        != 500.0
    )


def test_buy_and_sell_projections_have_opposite_direction():
    ledger = InventoryLedger()

    buy_request = QuoteRequest(
        customer_id="buy",
        base_currency=Currency.EUR,
        quote_currency=Currency.USD,
        side=FXSide.buy,
        amount=10_000.0,
        segment=CustomerSegment.retail,
    )

    sell_request = QuoteRequest(
        customer_id="sell",
        base_currency=Currency.EUR,
        quote_currency=Currency.USD,
        side=FXSide.sell,
        amount=10_000.0,
        segment=CustomerSegment.retail,
    )

    buy_projection = ledger.project_after_client_fx(
        request=buy_request,
        mid_rate=1.10,
    )

    sell_projection = ledger.project_after_client_fx(
        request=sell_request,
        mid_rate=1.10,
    )

    assert (
        buy_projection.get_state(
            Currency.EUR
        ).position
        <
        ledger.get_state(Currency.EUR).position
    )

    assert (
        sell_projection.get_state(
            Currency.EUR
        ).position
        >
        ledger.get_state(Currency.EUR).position
    )
