from datetime import datetime, timedelta, timezone

import numpy as np

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
        steps: int = 1_000,
        dt_seconds: int = 10,
        base_intensity: float = 0.015,
        alpha: float = 0.08,
        beta: float = 0.12,
        start_at: datetime | None = None,
    ) -> list[QuoteRequest]:
        current_time = start_at or datetime.now(timezone.utc)
        execution = 0.0
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
                        FXSide.buy if self.rng.random() < 0.55 else FXSide.sell
                    ),
                    amount=float(self.rng.lognormal(mean=0.7, sigma=0.75)),
                    segment=self._sample_segment(),
                    channel='synthetic_hawkes',
                )
                requests.append(request)
                execution += alpha

            execution *= float(np.exp(-beta * dt_seconds / 60.0))
            current_time += timedelta(seconds=dt_seconds)

        return requests

    def _sample_segment(self) -> CustomerSegment:
        value = self.rng.random()

        if value < 0.12:
            return CustomerSegment.premium
        if value < 0.2:
            return CustomerSegment.business
        return CustomerSegment.retail
