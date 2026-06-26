import pytest

from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.pricing.quote_engine import QuoteEngine
from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
)


request = QuoteRequest(
    customer_id='quote-engine-test',
    base_currency=Currency.EUR,
    quote_currency=Currency.USD,
    side=FXSide.buy,
    amount=10_000.0,
    segment=CustomerSegment.retail,
)


quote_engine = QuoteEngine(
    ledger=InventoryLedger(),
)


class FailingMidRateProvider:
    def get_mid_rate(
        self,
        base_currency,
        quote_currency,
    ):
        raise AssertionError(
            'Provider must not be called'
        )


class NonPositiveMidRateProvider:
    def get_mid_rate(
        self,
        base_currency,
        quote_currency,
    ):
        return 0.0


def test_quote_uses_explicit_mid_rate():
    quote = quote_engine.quote(
        request=request,
        mid_rate=1.2345,
    )

    assert quote.mid_rate == 1.2345


@pytest.mark.parametrize(
    'mid_rate',
    [0.0, -1.0],
)
def test_quote_rejects_non_positive_mid_rate(
    mid_rate,
):
    with pytest.raises(
        ValueError,
        match='mid_rate must be positive',
    ):
        quote_engine.quote(
            request=request,
            mid_rate=mid_rate,
        )


def test_explicit_mid_rate_skips_provider():
    engine = QuoteEngine(
        ledger=InventoryLedger(),
        mid_rate_provider=FailingMidRateProvider(),
    )

    quote = engine.quote(
        request=request,
        mid_rate=1.20,
    )

    assert quote.mid_rate == 1.20


def test_quote_rejects_non_positive_provider_mid_rate():
    engine = QuoteEngine(
        ledger=InventoryLedger(),
        mid_rate_provider=NonPositiveMidRateProvider(),
    )

    with pytest.raises(
        ValueError,
        match='mid_rate must be positive',
    ):
        engine.quote(request=request)
