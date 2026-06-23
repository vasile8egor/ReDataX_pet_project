from abc import ABC, abstractmethod
from enum import Enum

from revolut_app.fx_lab.shared.constants import (
    BASE_INVENTORY_PENALTY_WEIGHT_BPS,
    BUSINESS_BASE_SPREAD_BPS,
    COMPONENT_BPS_PRECISION,
    LIQUIDITY_PENALTY_WEIGHT_BPS,
    LIQUIDITY_PRESSURE_THRESHOLD,
    NAIVE_FIXED_SPREAD_BPS,
    PLATFORM_BUSINESS_BASE_SPREAD_BPS,
    PLATFORM_BUSINESS_REVENUE_PER_ACCEPTED_EVENT_USD,
    PLATFORM_INVENTORY_PENALTY_MULTIPLIER,
    PLATFORM_LIQUIDITY_PENALTY_MULTIPLIER,
    PLATFORM_PREMIUM_BASE_SPREAD_BPS,
    PLATFORM_PREMIUM_REVENUE_PER_ACCEPTED_EVENT_USD,
    PLATFORM_REGIME_PENALTY_MULTIPLIER,
    PLATFORM_RETAIL_BASE_SPREAD_BPS,
    PLATFORM_RETAIL_REVENUE_PER_ACCEPTED_EVENT_USD,
    PREMIUM_BASE_SPREAD_BPS,
    QUOTE_INVENTORY_PENALTY_WEIGHT_BPS,
    RETAIL_BASE_SPREAD_BPS,
    ONE_FLOAT,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.pricing.models import FXQuoteComponents, QuoteRequest
from revolut_app.fx_lab.shared.enums import CustomerSegment, FXSide, StressRegime
from revolut_app.fx_lab.inventory.stress import StressRegimeDetect


class QuotePolicyName(str, Enum):
    naive = 'naive'
    inventory_aware = 'inventory_aware'
    platform = 'platform'


class QuotePolicy(ABC):
    name: QuotePolicyName

    @abstractmethod
    def spread_components(
        self, *,
        request: QuoteRequest,
        pressures: dict[str, float],
        regime: StressRegime,
    ):
        raise NotImplementedError

    def allocated_product_revenue_usd(self, request: QuoteRequest):
        return ZERO_FLOAT


class NaiveQuotePolicy(QuotePolicy):
    name = QuotePolicyName.naive

    def spread_components(
        self, *,
        request: QuoteRequest,
        pressures: dict[str, float],
        regime: StressRegime,
    ):
        return FXQuoteComponents(
            base_spread_bps=NAIVE_FIXED_SPREAD_BPS,
            inventory_penalty_bps=ZERO_FLOAT,
            liquidity_penalty_bps=ZERO_FLOAT,
            regime_penalty_bps=ZERO_FLOAT,
        )


class RiskAwareQuotePolicy(QuotePolicy):
    inventory_penalty_multiplier = ONE_FLOAT
    liquidity_penalty_multiplier = ONE_FLOAT
    regime_penalty_multiplier = ONE_FLOAT

    def __init__(self, stress_detect: StressRegimeDetect):
        self.stress_detect = stress_detect

    def spread_components(
        self, *,
        request: QuoteRequest,
        pressures: dict[str, float],
        regime: StressRegime,
    ):
        base_phi = pressures.get(
            request.base_currency.value,
            ZERO_FLOAT,
        )
        quote_phi = pressures.get(
            request.quote_currency.value,
            ZERO_FLOAT,
        )

        if request.side == FXSide.buy:
            bad_base_pressure = max(ZERO_FLOAT, -base_phi)
            bad_quote_pressure = max(ZERO_FLOAT, quote_phi)
        else:
            bad_base_pressure = max(ZERO_FLOAT, base_phi)
            bad_quote_pressure = max(ZERO_FLOAT, -quote_phi)

        inventory_penalty_bps = (
            BASE_INVENTORY_PENALTY_WEIGHT_BPS * bad_base_pressure
            + QUOTE_INVENTORY_PENALTY_WEIGHT_BPS * bad_quote_pressure
        ) * self.inventory_penalty_multiplier

        max_pressure = max(abs(base_phi), abs(quote_phi))

        liquidity_penalty_bps = (
            max(
                ZERO_FLOAT,
                max_pressure - LIQUIDITY_PRESSURE_THRESHOLD,
            )
            * LIQUIDITY_PENALTY_WEIGHT_BPS
            * self.liquidity_penalty_multiplier
        )

        regime_penalty_bps = (
            self.stress_detect.regime_penalty_bps(regime)
            * self.regime_penalty_multiplier
        )

        return FXQuoteComponents(
            base_spread_bps=self.base_spread_bps(request.segment),
            inventory_penalty_bps=round(
                inventory_penalty_bps,
                COMPONENT_BPS_PRECISION
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

    @abstractmethod
    def base_spread_bps(self, segment: CustomerSegment):
        raise NotImplementedError


class InventoryAwareQuotePolicy(RiskAwareQuotePolicy):
    name = QuotePolicyName.inventory_aware

    def base_spread_bps(self, segment: CustomerSegment):
        if segment == CustomerSegment.premium:
            return PREMIUM_BASE_SPREAD_BPS
        if segment == CustomerSegment.business:
            return BUSINESS_BASE_SPREAD_BPS

        return RETAIL_BASE_SPREAD_BPS


class PlatformQuotePolicy(RiskAwareQuotePolicy):
    name = QuotePolicyName.platform

    inventory_penalty_multiplier = (
        PLATFORM_INVENTORY_PENALTY_MULTIPLIER
    )
    liquidity_penalty_multiplier = (
        PLATFORM_LIQUIDITY_PENALTY_MULTIPLIER
    )
    regime_penalty_multiplier = (
        PLATFORM_REGIME_PENALTY_MULTIPLIER
    )

    def base_spread_bps(self, segment: CustomerSegment):
        if segment == CustomerSegment.premium:
            return PLATFORM_PREMIUM_BASE_SPREAD_BPS
        if segment == CustomerSegment.business:
            return PLATFORM_BUSINESS_BASE_SPREAD_BPS
        return PLATFORM_RETAIL_BASE_SPREAD_BPS

    def allocated_product_revenue_usd(self, request: QuoteRequest):
        if request.segment == CustomerSegment.premium:
            return (
                PLATFORM_PREMIUM_REVENUE_PER_ACCEPTED_EVENT_USD
            )
        if request.segment == CustomerSegment.business:
            return (
                PLATFORM_BUSINESS_REVENUE_PER_ACCEPTED_EVENT_USD
            )
        return PLATFORM_RETAIL_REVENUE_PER_ACCEPTED_EVENT_USD


def build_quote_policy(
    name: QuotePolicyName,
    stress_detect: StressRegimeDetect
) -> QuotePolicy:
    if name == QuotePolicyName.naive:
        return NaiveQuotePolicy()
    if name == QuotePolicyName.platform:
        return PlatformQuotePolicy(stress_detect)
    return InventoryAwareQuotePolicy(stress_detect)
