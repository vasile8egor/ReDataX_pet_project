from dataclasses import replace

from revolut_app.fx_lab.shared.constants import (
    BPS_DENOMINATOR,
    CLIENT_RATE_PRECISION,
    ONE_FLOAT,
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.inventory.stress import StressRegimeDetect
from revolut_app.fx_lab.market.mid_rate import StaticMidRateProvider
from revolut_app.fx_lab.shared.enums import FXSide
from revolut_app.fx_lab.pricing.models import (
    FXQuote,
    QuoteRequest,
)
from revolut_app.fx_lab.pricing.policies import (
    InventoryAwareQuotePolicy,
    QuotePolicy
)


class QuoteEngine:
    def __init__(
        self, *,
        ledger: InventoryLedger,
        stress_detect: StressRegimeDetect | None = None,
        mid_rate_provider: StaticMidRateProvider | None = None,
        policy: QuotePolicy | None = None,
    ):
        self.ledger = ledger
        self.stress_detect = stress_detect or StressRegimeDetect()
        self.mid_rate_provider = mid_rate_provider or StaticMidRateProvider()
        self.policy = policy or InventoryAwareQuotePolicy(
            stress_detect=self.stress_detect
        )

    def get_mid_rate(
        self,
        request: QuoteRequest,
    ) -> float:
        return self.mid_rate_provider.get_mid_rate(
            base_currency=request.base_currency,
            quote_currency=request.quote_currency,
        )

    def quote(
            self,
            request: QuoteRequest,
            hamiltonian_penalty_bps: float = 0.0,
            mid_rate: float | None = None,
    ) -> FXQuote:
        resolved_mid_rate = (
            mid_rate
            if mid_rate is not None
            else self.get_mid_rate(request)
        )

        if resolved_mid_rate <= 0.0:
            raise ValueError('mid_rate must be positive')

        pressures = self.ledger.pressures()
        states = {
            currency.value: state
            for currency, state in self.ledger.get_all_states().items()
        }

        regime = self.stress_detect.detect(
            pressures=pressures,
            states=states,
        )

        components = self.policy.spread_components(
            request=request,
            pressures=pressures,
            regime=regime,
        )

        components = replace(
            components,
            hamiltonian_penalty_bps=max(0.0, hamiltonian_penalty_bps),
        )

        spread_multiplier = components.total_spread_bps / BPS_DENOMINATOR

        if request.side == FXSide.buy:
            client_rate = resolved_mid_rate * (
                ONE_FLOAT + spread_multiplier
            )
        else:
            client_rate = resolved_mid_rate * (
                ONE_FLOAT - spread_multiplier
            )

        return FXQuote.new(
            request=request,
            mid_rate=resolved_mid_rate,
            client_rate=round(client_rate, CLIENT_RATE_PRECISION),
            components=components,
            inventory_pressure=pressures,
            regime=regime,
        )
