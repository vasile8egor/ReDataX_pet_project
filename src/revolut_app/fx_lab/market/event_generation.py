from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5

import numpy as np

from revolut_app.fx_lab.shared.constants import (
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
    ONE_FLOAT,
    ONE_INT,
    SECONDS_PER_MINUTE,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.experiments.models import FXEvent, FXEventDataset
from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.shared.enums import Currency, CustomerSegment, FXSide


class HawkesLikeFXEventGenerator:
    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed)

    def simulate_event_dataset(
        self, *,
        steps: int = DEFAULT_HAWKES_STEPS,
        dt_seconds: int = DEFAULT_HAWKES_DT_SECONDS,
        base_intensity: float = DEFAULT_HAWKES_BASE_INTENSITY,
        alpha: float = DEFAULT_HAWKES_ALPHA,
        beta: float = DEFAULT_HAWKES_BETA,
        start_at: datetime | None = None,
        event_dataset_id: UUID | None = None,
        seed: int | None = None,
    ):
        dataset_id = event_dataset_id or uuid4()
        started_at = start_at or datetime.now(timezone.utc)
        current_time = started_at
        excitation = ZERO_FLOAT
        rng = np.random.default_rng(seed) if seed is not None else self.rng

        events: list[FXEvent] = []

        currency_pairs = [
            (Currency.EUR, Currency.GBP),
            (Currency.GBP, Currency.EUR),
            (Currency.EUR, Currency.USD),
            (Currency.GBP, Currency.USD),
        ]

        for step_idx in range(steps):
            event_probability = max(
                ZERO_FLOAT,
                min(ONE_FLOAT, base_intensity + excitation),
            )

            if rng.random() < event_probability:
                base_currency, quote_currency = currency_pairs[
                    rng.integers(0, len(currency_pairs))
                ]

                event_sequence = len(events) + ONE_INT

                side = (
                    FXSide.buy if rng.random() < HAWKES_BUY_PROBABILITY
                    else FXSide.sell
                )
                amount = float(
                    rng.lognormal(
                        mean=HAWKES_LOGNORMAL_MEAN,
                        sigma=HAWKES_LOGNORMAL_SIGMA,
                    )
                )

                request = QuoteRequest(
                    customer_id=f'customer_num_{step_idx}',
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    side=side,
                    amount=amount,
                    segment=self._sample_segment(rng),
                    channel='synthetic_hawkes',
                )
                events.append(
                    FXEvent(
                        event_id=uuid5(
                            dataset_id,
                            str(step_idx),
                        ),
                        event_sequence=event_sequence,
                        source_step_index=step_idx,
                        event_ts=current_time,
                        request=request,
                    )
                )
                excitation += alpha
            excitation *= float(
                np.exp(-beta * dt_seconds / SECONDS_PER_MINUTE)
            )
            current_time += timedelta(seconds=dt_seconds)
        return FXEventDataset(
            event_dataset_id=dataset_id,
            generator='hawkes_v2',
            seed=seed,
            started_at=started_at,
            finished_at=(
                started_at + timedelta(seconds=steps * dt_seconds)
            ),
            source_steps=steps,
            dt_seconds=dt_seconds,
            base_intensity=base_intensity,
            alpha=alpha,
            beta=beta,
            events=tuple(events),
        )

    def simulate_quote_requests(
        self, *,
        steps: int = DEFAULT_HAWKES_STEPS,
        dt_seconds: int = DEFAULT_HAWKES_DT_SECONDS,
        base_intensity: float = DEFAULT_HAWKES_BASE_INTENSITY,
        alpha: float = DEFAULT_HAWKES_ALPHA,
        beta: float = DEFAULT_HAWKES_BETA,
        start_at: datetime | None = None,
    ):
        dataset = self.simulate_event_dataset(
            steps=steps,
            dt_seconds=dt_seconds,
            base_intensity=base_intensity,
            alpha=alpha,
            beta=beta,
            start_at=start_at,
        )

        return [
            event.request
            for event in dataset.events
        ]

    @staticmethod
    def _sample_segment(rng: np.random.Generator):
        value = rng.random()

        premium_threshold = PREMIUM_SEGMENT_PROBABILITY
        business_threshold = (
            PREMIUM_SEGMENT_PROBABILITY
            + BUSINESS_SEGMENT_PROBABILITY
        )

        if value < premium_threshold:
            return CustomerSegment.premium
        if value < business_threshold:
            return CustomerSegment.business
        return CustomerSegment.retail
