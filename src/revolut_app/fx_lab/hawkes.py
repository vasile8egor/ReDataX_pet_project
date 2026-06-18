from datetime import datetime, timedelta, timezone

import numpy as np

from revolut_app.fx_lab.constants import (
    BUSINESS_SEGMENT_PROBABILITY,
    DEFAULT_HAWKES_ALPHA,
    DEFAULT_HAWKES_BASE_INTENSITY,
    DEFAULT_HAWKES_BETA,
    DEFAULT_HAWKES_DT_SECONDS,
    DEFAULT_HAWKES_STEPS,
    HAWKES_BUY_PROBABILITY,
    HAWKES_LOGNORMAL_MEAN,
    HAWKES_LOGNORMAL_SIGMA,
    PREMIUM_SEGMENT_PROBABILITY,
    SECONDS_PER_MINUTE,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.models import (
    Currency,
    CustomerSegment,
    FXSide,
    QuoteRequest,
)


class HawkesLikeFXEventGenerator:
    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed)

    def simulate_quote_requests(
        self, *,
        steps: int = DEFAULT_HAWKES_STEPS,
        dt_seconds: int = DEFAULT_HAWKES_DT_SECONDS,
        base_intensity: float = DEFAULT_HAWKES_BASE_INTENSITY,
        alpha: float = DEFAULT_HAWKES_ALPHA,
        beta: float = DEFAULT_HAWKES_BETA,
        start_at: datetime | None = None,
    ) -> list[QuoteRequest]:
        current_time = start_at or datetime.now(timezone.utc)
        execution = ZERO_FLOAT
        requests = []

        currency_pairs = [
            (Currency.EUR, Currency.GBP),
            (Currency.GBP, Currency.EUR),
            (Currency.EUR, Currency.USD),
            (Currency.GBP, Currency.USD),
        ]

        for step in range(steps):
            intensity = base_intensity + execution

            if self.rng.random() < intensity:
                base_currency, quote_currency = currency_pairs[
                    self.rng.integers(0, len(currency_pairs))
                ]

                request = QuoteRequest(
                    customer_id=f'customer_num_{step}',
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    side=(
                        FXSide.buy
                        if self.rng.random() < HAWKES_BUY_PROBABILITY
                        else FXSide.sell
                    ),
                    amount=float(
                        self.rng.lognormal(
                            mean=HAWKES_LOGNORMAL_MEAN,
                            sigma=HAWKES_LOGNORMAL_SIGMA,
                        )
                    ),
                    segment=self._sample_segment(),
                    channel='synthetic_hawkes',
                )
                requests.append(request)
                execution += alpha

            execution *= float(np.exp(-beta * dt_seconds / SECONDS_PER_MINUTE))
            current_time += timedelta(seconds=dt_seconds)

        return requests

    def _sample_segment(self) -> CustomerSegment:
        value = self.rng.random()

        if value < PREMIUM_SEGMENT_PROBABILITY:
            return CustomerSegment.premium
        if value < BUSINESS_SEGMENT_PROBABILITY:
            return CustomerSegment.business
        return CustomerSegment.retail
