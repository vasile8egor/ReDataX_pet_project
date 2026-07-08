from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.market.mid_rate import StaticMidRateProvider
from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.shared.constants import (
    BPS_DENOMINATOR,
    SECONDS_PER_YEAR,
    USD_MARKS,
    ZERO_FLOAT,
)


def funding_cost_interval(
    ledger: InventoryLedger,
    elapsed_seconds: float,
):
    total = ZERO_FLOAT

    for currency, state in ledger.get_all_states().items():
        usd_mark = StaticMidRateProvider.USD_MARKS[
            currency.value
        ]
        inventory_notional_usd = (
            abs(state.position) * usd_mark
        )

        annual_cost_rate = (
            state.funding_cost_bps / BPS_DENOMINATOR
        )

        total += (
            inventory_notional_usd
            * annual_cost_rate
            * elapsed_seconds
            / SECONDS_PER_YEAR
        )
    return total


def spread_revenue_usd(
    request: QuoteRequest,
    spread_bps: float,
):
    base_usd_mark = USD_MARKS[request.base_currency.value]
    notional_usd = request.amount * base_usd_mark

    return (
        notional_usd
        * spread_bps
        / BPS_DENOMINATOR
    )
