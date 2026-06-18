from revolut_app.fx_lab.constants import (
    BASE_INVENTORY_PENALTY_WEIGHT_BPS,
    BPS_DENOMINATOR,
    BUSINESS_BASE_SPREAD_BPS,
    CLIENT_RATE_PRECISION,
    COMPONENT_BPS_PRECISION,
    LIQUIDITY_PENALTY_WEIGHT_BPS,
    LIQUIDITY_PRESSURE_THRESHOLD,
    MID_RATE_PRECISION,
    ONE_FLOAT,
    PREMIUM_BASE_SPREAD_BPS,
    QUOTE_INVENTORY_PENALTY_WEIGHT_BPS,
    RETAIL_BASE_SPREAD_BPS,
    USD_MARKS as DEFAULT_USD_MARKS,
    ZERO_FLOAT,
)
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
    USD_MARKS = DEFAULT_USD_MARKS

    def get_mid_rate(
        self,
        base_currency: Currency,
        quote_currency: Currency,
    ) -> float:
        base_usd = self.USD_MARKS[base_currency.value]
        quote_usd = self.USD_MARKS[quote_currency.value]
        return round(base_usd / quote_usd, MID_RATE_PRECISION)


class QuoteEngine:
    def __init__(
        self, *,
        ledger: InventoryLedger,
        stress_detect: StressRegimeDetect | None = None,
        mid_rate_provider: StaticMidRateProvider | None = None,
    ):
        self.ledger = ledger
        self.stress_detect = stress_detect or StressRegimeDetect()
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

        spread_multiplier = components.total_spread_bps / BPS_DENOMINATOR

        if request.side == FXSide.buy:
            client_rate = mid_rate * (ONE_FLOAT + spread_multiplier)
        else:
            client_rate = mid_rate * (ONE_FLOAT - spread_multiplier)

        return FXQuote.new(
            request=request,
            mid_rate=mid_rate,
            client_rate=round(client_rate, CLIENT_RATE_PRECISION),
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

        base_phi = pressures.get(request.base_currency.value, ZERO_FLOAT)
        quote_phi = pressures.get(request.quote_currency.value, ZERO_FLOAT)

        if request.side == FXSide.buy:
            bad_base_pressure = max(ZERO_FLOAT, -base_phi)
            bad_quote_pressure = max(ZERO_FLOAT, quote_phi)
        else:
            bad_base_pressure = max(ZERO_FLOAT, base_phi)
            bad_quote_pressure = max(ZERO_FLOAT, -quote_phi)

        inventory_penalty_bps = (
            BASE_INVENTORY_PENALTY_WEIGHT_BPS * bad_base_pressure
            + QUOTE_INVENTORY_PENALTY_WEIGHT_BPS * bad_quote_pressure
        )
        max_pressure = max(abs(base_phi), abs(quote_phi))
        liquidity_penalty_bps = (
            max(ZERO_FLOAT, max_pressure - LIQUIDITY_PRESSURE_THRESHOLD)
            * LIQUIDITY_PENALTY_WEIGHT_BPS
        )
        regime_penalty_bps = self.stress_detect.regime_penalty_bps(regime)

        return FXQuoteComponents(
            base_spread_bps=base_spread_bps,
            inventory_penalty_bps=round(
                inventory_penalty_bps,
                COMPONENT_BPS_PRECISION,
            ),
            liquidity_penalty_bps=round(
                liquidity_penalty_bps,
                COMPONENT_BPS_PRECISION,
            ),
            regime_penalty_bps=round(
                regime_penalty_bps,
                COMPONENT_BPS_PRECISION,
            ),
        )

    @staticmethod
    def _base_spread_bps(segment: CustomerSegment) -> float:
        if segment == CustomerSegment.premium:
            return PREMIUM_BASE_SPREAD_BPS
        if segment == CustomerSegment.business:
            return BUSINESS_BASE_SPREAD_BPS
        return RETAIL_BASE_SPREAD_BPS
