from dataclasses import dataclass

import numpy as np

from revolut_app.fx_lab.constants import (
    ACCEPTANCE_SPREAD_NORMALIZER_BPS,
    BUSINESS_SEGMENT_SENSITIVITY,
    DEFAULT_AMOUNT_ACCEPTANCE_MULTIPLIER,
    DEFAULT_REGIME_ACCEPTANCE_MULTIPLIER,
    ELEVATED_ACCEPTANCE_MULTIPLIER,
    LARGE_AMOUNT_ACCEPTANCE_MULTIPLIER,
    LARGE_AMOUNT_THRESHOLD,
    MAX_ACCEPTANCE_PROBABILITY,
    MEDIUM_AMOUNT_ACCEPTANCE_MULTIPLIER,
    MEDIUM_AMOUNT_THRESHOLD,
    MIN_ACCEPTANCE_PROBABILITY,
    PREMIUM_SEGMENT_SENSITIVITY,
    RATIO_PRECISION,
    RETAIL_SEGMENT_SENSITIVITY,
    STRESS_ACCEPTANCE_MULTIPLIER,
)
from revolut_app.fx_lab.models import CustomerSegment, FXQuote, StressRegime


@dataclass
class AcceptanceDecision:
    accepted: bool
    probability: float
    reason: str


class AcceptanceModel:
    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed=seed)

    def decide(self, quote: FXQuote) -> AcceptanceDecision:
        probability = self.acceptance_probability(quote)
        accepted = bool(self.rng.random() < probability)

        if accepted:
            reason = 'quote accepted by customer'
        else:
            reason = 'quote rejected because spread pressure is too high'
        return AcceptanceDecision(
            accepted=accepted,
            probability=round(probability, RATIO_PRECISION),
            reason=reason,
        )

    def acceptance_probability(self, quote: FXQuote) -> float:
        spread_bps = quote.components.total_spread_bps
        segment_sensitivity = self._segment_sensitivity(quote.request.segment)
        regime_multiplier = self._regime_multiplier(quote.regime)
        amount_multiplier = self._amount_multiplier(quote.request.amount)
        raw_probability = (
            1
            - segment_sensitivity
            * spread_bps
            / ACCEPTANCE_SPREAD_NORMALIZER_BPS
        )
        raw_probability *= regime_multiplier * amount_multiplier

        return max(
            MIN_ACCEPTANCE_PROBABILITY,
            min(MAX_ACCEPTANCE_PROBABILITY, raw_probability),
        )

    @staticmethod
    def _amount_multiplier(amount: float) -> float:
        if amount >= LARGE_AMOUNT_THRESHOLD:
            return LARGE_AMOUNT_ACCEPTANCE_MULTIPLIER
        if amount >= MEDIUM_AMOUNT_THRESHOLD:
            return MEDIUM_AMOUNT_ACCEPTANCE_MULTIPLIER
        return DEFAULT_AMOUNT_ACCEPTANCE_MULTIPLIER

    @staticmethod
    def _regime_multiplier(regime: StressRegime) -> float:
        if regime == StressRegime.elevated:
            return ELEVATED_ACCEPTANCE_MULTIPLIER
        if regime == StressRegime.stress:
            return STRESS_ACCEPTANCE_MULTIPLIER
        return DEFAULT_REGIME_ACCEPTANCE_MULTIPLIER

    @staticmethod
    def _segment_sensitivity(segment: CustomerSegment) -> float:
        if segment == CustomerSegment.premium:
            return PREMIUM_SEGMENT_SENSITIVITY
        if segment == CustomerSegment.business:
            return BUSINESS_SEGMENT_SENSITIVITY
        return RETAIL_SEGMENT_SENSITIVITY
