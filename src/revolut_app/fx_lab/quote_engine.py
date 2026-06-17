from revolut_app.fx_lab.models import (
    Currency,
    CustomerSegment,
    FXQuote,
    FXQuoteComponents,
    FXSide,
    QuoteRequest,
)
from revolut_app.fx_lab.state_engine import InventoryLedger
from revolut_app.fx_lab.stress import StressRegimeDetect


class StaticMidRateProvider:
    USD_MARKS = {
        Currency.USD: 1.00,
        Currency.EUR: 1.08,
        Currency.GBP: 1.27,
    }

    def get_mid_rate(
        self,
        base_currency: Currency,
        quote_currency: Currency,
    ) -> float:
        base_usd = self.USD_MARKS[base_currency]
        quote_usd = self.USD_MARKS[quote_currency]
        return round(base_usd / quote_usd, 6)


class QuoteEngine:
    def __init__(
        self, *,
        ledger: InventoryLedger,
        stress_detect: StressRegimeDetect | None = None,
        mid_rate_provider: StaticMidRateProvider | None = None,
    ):
        self.ledger = ledger
        self.stress_detect = stress_detect
        self.mid_rate_provider = mid_rate_provider or StaticMidRateProvider()

    def quote(self, request: QuoteRequest) -> FXQuote:
        mid_rate = self.mid_rate_provider.get_mid_rate(
            base_currency=request.base_currency,
            quote_currency=request.quote_currency,
        )

        pressures = self.ledger.pressures()
        states = {
            currency.value: state
            for currency, state in self.ledger.get_all_states().items()
        }

        regime = self.stress_detect.detect(
            pressures=pressures,
            states=states,
        )

        components = self._spread_components(
            request=request,
            pressures=pressures,
            regime=regime,
        )

        spread_multiplier = components.total_spread_bps / 10_000.0

        if request.side == FXSide.buy:
            client_rate = mid_rate * (1.0 + spread_multiplier)
        else:
            client_rate = mid_rate * (1.0 - spread_multiplier)

        return FXQuote.new(
            request=request,
            mid_rate=mid_rate,
            client_rate=round(client_rate, 6),
            components=components,
            inventory_pressure=pressures,
            regime=regime,
        )

    def _spread_components(
        self,
        *,
        request: QuoteRequest,
        pressures: dict[str, float],
        regime,
    ) -> FXQuoteComponents:
        base_spread_bps = self._base_spread_bps(request.segment)

        base_phi = pressures.get(request.base_currency.value, 0.0)
        quote_phi = pressures.get(request.quote_currency.value, 0.0)

        if request.side == FXSide.buy:
            bad_base_pressure = max(0.0, -base_phi)
            bad_quote_pressure = max(0.0, -quote_phi)
        else:
            bad_base_pressure = max(0.0, base_phi)
            bad_quote_pressure = max(0.0, quote_phi)
        inventory_penalty_bps = (
            18.0 * bad_base_pressure
            + 8.0 * bad_quote_pressure
        )
        max_pressure = max(abs(base_phi), abs(quote_phi))
        liquidity_penalty_bps = max(0.0, max_pressure - 0.55) * 10.0
        regime_penalty_bps = self.stress_detect.regime_penalty_bps(regime)

        return FXQuoteComponents(
            base_spread_bps=base_spread_bps,
            inventory_penalty_bps=round(inventory_penalty_bps, 4),
            liquidity_penalty_bps=round(liquidity_penalty_bps, 4),
            regime_penalty_bps=round(regime_penalty_bps, 4),
        )

    @staticmethod
    def _base_spread_bps(segment: CustomerSegment) -> float:
        if segment == CustomerSegment.premium:
            return 2.0
        if segment == CustomerSegment.business:
            return 4.0
        return 6.0
