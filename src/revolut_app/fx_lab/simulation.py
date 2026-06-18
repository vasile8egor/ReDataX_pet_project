from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from revolut_app.fx_lab.constants import (
    BPS_DENOMINATOR,
    DEFAULT_AMOUNT_MULTIPLIER,
    DEFAULT_HAWKES_ALPHA,
    DEFAULT_HAWKES_BETA,
    DEFAULT_HAWKES_DT_SECONDS,
    DEFAULT_MAX_SNAPSHOTS,
    DEFAULT_SIMULATION_BASE_INTENSITY,
    DEFAULT_SIMULATION_SEED,
    DEFAULT_SIMULATION_STEPS,
    ONE_INT,
    RATIO_PRECISION,
    ZERO_FLOAT,
    ZERO_INT,
)
from revolut_app.fx_lab.hawkes import HawkesLikeFXEventGenerator
from revolut_app.fx_lab.models import FXQuote, QuoteRequest, StressRegime
from revolut_app.fx_lab.quote_engine import QuoteEngine, StaticMidRateProvider
from revolut_app.fx_lab.state_engine import InventoryLedger
from revolut_app.fx_lab.stress import StressRegimeDetect


@dataclass
class InventorySnapshotPoint:
    event_index: int
    timestamp: datetime
    regime: StressRegime
    inventory_pressure: dict[str, float]
    max_abs_pressure: float
    synthetic_spread_revenue_usd: float


@dataclass
class DaySimulationResult:
    run_id: str
    started_at: datetime
    finished_at: datetime
    generated_requests: int
    executed_events: int
    final_regime: StressRegime
    max_abs_pressure: float
    stress_time_fraction: float
    elevated_or_stress_time_fraction: float
    synthetic_spread_revenue_usd: float
    final_inventory_pressure: dict[str, float]
    regime_counts: dict[str, int]
    snapshots: list[InventorySnapshotPoint]


class DaySimulationEngine:
    def __init__(
        self, *,
        ledger: InventoryLedger,
        quote_engine: QuoteEngine,
        stress_detect: StressRegimeDetect,
    ):
        self.ledger = ledger
        self.quote_engine = quote_engine
        self.stress_detect = stress_detect

    def simulate_day(
        self, *,
        steps: int = DEFAULT_SIMULATION_STEPS,
        dt_seconds: int = DEFAULT_HAWKES_DT_SECONDS,
        base_intensity: float = DEFAULT_SIMULATION_BASE_INTENSITY,
        alpha: float = DEFAULT_HAWKES_ALPHA,
        beta: float = DEFAULT_HAWKES_BETA,
        seed: int | None = DEFAULT_SIMULATION_SEED,
        amount_multiplier: float = DEFAULT_AMOUNT_MULTIPLIER,
        max_snapshots: int = DEFAULT_MAX_SNAPSHOTS,
    ) -> DaySimulationResult:
        started_at = datetime.now(timezone.utc)
        generator = HawkesLikeFXEventGenerator(seed=seed)

        raw_requests = generator.simulate_quote_requests(
            steps=steps,
            dt_seconds=dt_seconds,
            base_intensity=base_intensity,
            alpha=alpha,
            beta=beta,
            start_at=started_at,
        )
        requests = [
            self._scale_request_amount(
                request=request,
                amount_multiplier=amount_multiplier,
            )
            for request in raw_requests
        ]

        snapshots: list[InventorySnapshotPoint] = []
        regime_counter: Counter[str] = Counter()
        total_spread_revenue_usd = ZERO_FLOAT
        max_abs_pressure = ZERO_FLOAT

        for event_idx, request in enumerate(requests):
            quote = self.quote_engine.quote(request)
            spread_revenue_usd = self._synthetic_spread_revenue_usd(quote)
            total_spread_revenue_usd += spread_revenue_usd

            self.ledger.apply_client_fx(
                request=request,
                mid_rate=quote.mid_rate,
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

            regime_counter[regime.value] += 1

            point_max_abs_pressure = max(
                (abs(value) for value in pressures.values()),
                default=ZERO_FLOAT,
            )

            max_abs_pressure = max(max_abs_pressure, point_max_abs_pressure)

            snapshots.append(
                InventorySnapshotPoint(
                    event_index=event_idx,
                    timestamp=datetime.now(timezone.utc),
                    regime=regime,
                    inventory_pressure=pressures,
                    max_abs_pressure=round(
                        max_abs_pressure,
                        RATIO_PRECISION,
                    ),
                    synthetic_spread_revenue_usd=round(
                        total_spread_revenue_usd,
                        RATIO_PRECISION,
                    ),
                )
            )

        executed_events = len(requests)

        if executed_events == 0:
            final_pressures = self.ledger.pressures()
            final_regime = self.stress_detect.detect(
                pressures=final_pressures,
                states={
                    currency.value: state
                    for currency, state in self.ledger.get_all_states().items()
                },
            )

            return DaySimulationResult(
                run_id=str(uuid4()),
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                generated_requests=ZERO_INT,
                executed_events=ZERO_INT,
                final_regime=final_regime,
                max_abs_pressure=ZERO_FLOAT,
                stress_time_fraction=ZERO_FLOAT,
                elevated_or_stress_time_fraction=ZERO_FLOAT,
                synthetic_spread_revenue_usd=ZERO_FLOAT,
                final_inventory_pressure=final_pressures,
                regime_counts={},
                snapshots=[],
            )

        stress_count = regime_counter[StressRegime.stress.value]
        elevated_count = regime_counter[StressRegime.elevated.value]

        final_snapshot = snapshots[-1]
        sampled_snapshots = self._sampled_snapshots(
            snapshots=snapshots,
            max_snapshots=max_snapshots,
        )

        return DaySimulationResult(
            run_id=str(uuid4()),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            generated_requests=len(raw_requests),
            executed_events=executed_events,
            final_regime=final_snapshot.regime,
            max_abs_pressure=round(max_abs_pressure, RATIO_PRECISION),
            stress_time_fraction=round(
                stress_count / executed_events,
                RATIO_PRECISION,
            ),
            elevated_or_stress_time_fraction=round(
                (stress_count + elevated_count) / executed_events,
                RATIO_PRECISION,
            ),
            synthetic_spread_revenue_usd=round(
                total_spread_revenue_usd,
                RATIO_PRECISION,
            ),
            final_inventory_pressure=final_snapshot.inventory_pressure,
            regime_counts=dict(regime_counter),
            snapshots=sampled_snapshots,
        )

    @staticmethod
    def _sampled_snapshots(
        *,
        snapshots: list[InventorySnapshotPoint],
        max_snapshots: int,
    ) -> list[InventorySnapshotPoint]:
        if max_snapshots <= ZERO_INT:
            return []
        if len(snapshots) <= max_snapshots:
            return snapshots

        step = max(ONE_INT, len(snapshots) // max_snapshots)
        sampled = snapshots[::step]
        if sampled[-1] != snapshots[-1]:
            sampled.append(snapshots[-1])

        return sampled[:max_snapshots]

    @staticmethod
    def _synthetic_spread_revenue_usd(quote: FXQuote) -> float:
        base_usd_mark = StaticMidRateProvider.USD_MARKS[
            quote.request.base_currency.value
        ]
        notional_usd = quote.request.amount * base_usd_mark
        spread_fraction = quote.components.total_spread_bps / BPS_DENOMINATOR

        return notional_usd * spread_fraction

    @staticmethod
    def _scale_request_amount(
        request: QuoteRequest,
        amount_multiplier: float,
    ) -> QuoteRequest:
        return replace(
            request,
            amount=request.amount * amount_multiplier,
        )
