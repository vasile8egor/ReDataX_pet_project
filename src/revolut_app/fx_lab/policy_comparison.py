from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone, timedelta
from statistics import mean
from uuid import uuid4

from revolut_app.fx_lab.acceptance import AcceptanceModel
from revolut_app.fx_lab.constants import (
    BPS_DENOMINATOR,
    EPSILON,
    ONE_INT,
    RATIO_PRECISION,
    USD_MARKS,
    ZERO_FLOAT,
    ZERO_INT,
)
from revolut_app.fx_lab.hawkes import HawkesLikeFXEventGenerator
from revolut_app.fx_lab.models import (
    QuoteRequest,
    StressRegime,
    Currency,
)
from revolut_app.fx_lab.policies import (
    QuotePolicyName,
    build_quote_policy,
)
from revolut_app.fx_lab.quote_engine import (
    QuoteEngine,
    StaticMidRateProvider,
)
from revolut_app.fx_lab.state_engine import InventoryLedger
from revolut_app.fx_lab.stress import StressRegimeDetect


@dataclass(frozen=True)
class PolicyRunResult:
    run_id: str
    started_at: datetime
    finished_at: datetime

    policy: QuotePolicyName
    generated_requests: int
    accepted_events: int
    rejected_events: int
    acceptance_rate: float

    average_quoted_spread_bps: float
    average_accepted_spread_bps: float
    customer_spread_cost_usd: float

    spread_revenue_usd: float
    allocated_product_revenue_usd: float
    funding_cost_usd: float
    net_pnl_usd: float

    final_regime: StressRegime
    max_abs_pressure: float
    stress_time_fraction: float
    final_inventory_pressure: dict[str, float]
    snapshots: list[PolicyInventorySnapshot]


@dataclass(frozen=True)
class PolicyComparisonResult:
    comparison_id: str
    event_dataset_id: str

    started_at: datetime
    finished_at: datetime
    generated_requests: int
    seed: int | None
    results: list[PolicyRunResult]

    best_policy_by_net_pnl: QuotePolicyName
    lowest_risk_policy: QuotePolicyName
    lowest_customer_spread_policy: QuotePolicyName


class PolicyComparisonEngine:
    def compare(
        self, *,
        policy_names: list[QuotePolicyName],
        steps: int,
        dt_seconds: int,
        base_intensity: float,
        alpha: float,
        beta: float,
        seed: int | None,
        amount_multiplier: float,
        snapshot_every_n_events: int,
    ) -> PolicyComparisonResult:
        started_at = datetime.now(timezone.utc)

        requests = self._generate_requests(
            steps=steps,
            dt_seconds=dt_seconds,
            base_intensity=base_intensity,
            alpha=alpha,
            beta=beta,
            seed=seed,
            amount_multiplier=amount_multiplier,
        )

        comparison_id = str(uuid4())
        event_dataset_id = str(uuid4())

        results = [
            self._run_policy(
                policy_name=policy_name,
                requests=requests,
                seed=seed,
                dt_seconds=dt_seconds,
                snapshot_every_n_events=snapshot_every_n_events,
            )
            for policy_name in policy_names
        ]

        return PolicyComparisonResult(
            comparison_id=comparison_id,
            event_dataset_id=event_dataset_id,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            generated_requests=len(requests),
            seed=seed,
            results=results,
            best_policy_by_net_pnl=max(
                results,
                key=lambda item: item.net_pnl_usd,
            ).policy,
            lowest_customer_spread_policy=min(
                results,
                key=lambda item: item.average_accepted_spread_bps,
            ).policy,
            lowest_risk_policy=min(
                results,
                key=lambda item: (
                    item.stress_time_fraction,
                    item.max_abs_pressure,
                ),
            ).policy
        )

    def _run_policy(
        self, *,
        policy_name: QuotePolicyName,
        requests: list[QuoteRequest],
        seed: int | None,
        dt_seconds: int,
        snapshot_every_n_events: int,
    ) -> PolicyRunResult:
        ledger = InventoryLedger()
        stress_detect = StressRegimeDetect()

        policy = build_quote_policy(
            name=policy_name,
            stress_detect=stress_detect,
        )
        quote_engine = QuoteEngine(
            ledger=ledger,
            stress_detect=stress_detect,
            policy=policy,
        )

        run_started_at = datetime.now(timezone.utc)
        snapshots: list[PolicyInventorySnapshot] = []

        acceptance_model = AcceptanceModel(seed=seed)
        accepted_events = 0
        rejected_events = 0

        quoted_spread: list[float] = []
        accepted_spreads: list[float] = []

        spread_revenue_usd = ZERO_FLOAT
        product_revenue_usd = ZERO_FLOAT

        max_abs_pressure = ZERO_FLOAT
        regime_counter: Counter[str] = Counter()

        initial_pressures = ledger.pressures()
        initial_regime = stress_detect.detect(
            pressures=initial_pressures,
            states={
                currency.value: state
                for currency, state in ledger.get_all_states().items()
            },
        )
        snapshots.extend(
            self._capture_inventory_snapshots(
                event_index=ZERO_INT,
                snapshot_ts=run_started_at,
                ledger=ledger,
                pressures=initial_pressures,
                regime=initial_regime,
                event_accepted=False,
                acceptance_probability=ZERO_FLOAT,
                cumulative_accepted_events=ZERO_INT,
                cumulative_rejected_events=ZERO_INT,
                cumulative_spread_revenue_usd=ZERO_FLOAT,
            )
        )

        for event_index, request in enumerate(requests, start=ONE_INT):
            quote = quote_engine.quote(request)
            decision = acceptance_model.decide(quote)

            total_spread_bps = quote.components.total_spread_bps
            quoted_spread.append(total_spread_bps)

            if decision.accepted:
                accepted_events += 1
                accepted_spreads.append(total_spread_bps)

                revenue_usd = self._spread_revenue_usd(
                    request=request,
                    spread_bps=total_spread_bps,
                )

                spread_revenue_usd += revenue_usd
                product_revenue_usd += (
                    policy.allocated_product_revenue_usd(request)
                )

                ledger.apply_client_fx(
                    request=request,
                    mid_rate=quote.mid_rate,
                )
            else:
                rejected_events += 1

            pressures = ledger.pressures()
            states = {
                currency.value: state
                for currency, state in ledger.get_all_states().items()
            }

            regime = stress_detect.detect(
                pressures=pressures,
                states=states,
            )

            regime_counter[regime.value] += 1

            point_max_pressure = max(
                (abs(value) for value in pressures.values()),
                default=ZERO_FLOAT,
            )
            max_abs_pressure = max(
                max_abs_pressure,
                point_max_pressure,
            )

            should_capture = (
                event_index % snapshot_every_n_events == 0
                or event_index == len(requests)
            )

            if should_capture:
                snapshot_ts = (
                    run_started_at
                    + timedelta(seconds=event_index * dt_seconds)
                )

                snapshots.extend(
                    self._capture_inventory_snapshots(
                        event_index=event_index,
                        snapshot_ts=snapshot_ts,
                        ledger=ledger,
                        pressures=pressures,
                        regime=regime,
                        event_accepted=decision.accepted,
                        acceptance_probability=decision.probability,
                        cumulative_accepted_events=accepted_events,
                        cumulative_rejected_events=rejected_events,
                        cumulative_spread_revenue_usd=spread_revenue_usd,
                    ),
                )

        final_pressures = ledger.pressures()
        final_regime = stress_detect.detect(
            pressures=final_pressures,
            states={
                currency.value: state
                for currency, state in ledger.get_all_states().items()
            },
        )

        funding_cost_usd = self._funding_cost_usd(ledger)
        net_pnl_usd = (
            spread_revenue_usd
            + product_revenue_usd
            - funding_cost_usd
        )

        total_requests = len(requests)
        stress_count = regime_counter[StressRegime.stress.value]

        quoted_spreads = (
            mean(quoted_spread) if quoted_spread else ZERO_FLOAT
        )

        accepted_spreads = (
            mean(accepted_spreads) if accepted_spreads else ZERO_FLOAT
        )

        return PolicyRunResult(
            run_id=str(uuid4()),
            started_at=run_started_at,
            finished_at=datetime.now(timezone.utc),
            policy=policy_name,
            generated_requests=total_requests,
            accepted_events=accepted_events,
            rejected_events=rejected_events,
            acceptance_rate=round(
                accepted_events / max(total_requests, ONE_INT),
                RATIO_PRECISION
            ),
            average_quoted_spread_bps=round(
                quoted_spreads,
                RATIO_PRECISION
            ),
            average_accepted_spread_bps=round(
                accepted_spreads,
                RATIO_PRECISION
            ),
            customer_spread_cost_usd=round(
                spread_revenue_usd,
                RATIO_PRECISION,
            ),
            spread_revenue_usd=round(
                spread_revenue_usd,
                RATIO_PRECISION,
            ),
            allocated_product_revenue_usd=round(
                product_revenue_usd,
                RATIO_PRECISION,
            ),
            funding_cost_usd=round(
                funding_cost_usd,
                RATIO_PRECISION,
            ),
            net_pnl_usd=round(
                net_pnl_usd,
                RATIO_PRECISION,
            ),
            final_regime=final_regime,
            max_abs_pressure=round(
                max_abs_pressure,
                RATIO_PRECISION,
            ),
            stress_time_fraction=round(
                stress_count / max(total_requests, ONE_INT),
                RATIO_PRECISION,
            ),
            final_inventory_pressure=final_pressures,
            snapshots=snapshots,
        )

    @staticmethod
    def _capture_inventory_snapshots(
        event_index: int,
        snapshot_ts: datetime,
        ledger: InventoryLedger,
        pressures: dict[str, float],
        regime: StressRegime,
        event_accepted: bool,
        acceptance_probability: float,
        cumulative_accepted_events: int,
        cumulative_rejected_events: int,
        cumulative_spread_revenue_usd: float,
    ):
        result: list[PolicyInventorySnapshot] = []

        for currency, state in ledger.get_all_states().items():
            if state.position_limit > ZERO_FLOAT:
                position_pressure = (state.position / state.position_limit)
            else:
                position_pressure = ZERO_FLOAT

            order_flow_total = (
                state.order_flow_buy_ewma
                + state.order_flow_sell_ewma
            )

            if abs(order_flow_total) > EPSILON:
                order_flow_imbalance = (
                    state.order_flow_buy_ewma
                    - state.order_flow_sell_ewma
                ) / order_flow_total
            else:
                order_flow_imbalance = ZERO_FLOAT

            result.append(
                PolicyInventorySnapshot(
                    event_index=event_index,
                    snapshot_ts=snapshot_ts,
                    currency=currency,
                    position=round(state.position, RATIO_PRECISION),
                    position_limit=round(
                        state.position_limit,
                        RATIO_PRECISION,
                    ),
                    limit_utilization=round(
                        state.limit_utilization,
                        RATIO_PRECISION,
                    ),
                    position_pressure=round(
                        position_pressure,
                        RATIO_PRECISION,
                    ),
                    order_flow_buy_ewma=round(
                        state.order_flow_buy_ewma,
                        RATIO_PRECISION,
                    ),
                    order_flow_sell_ewma=round(
                        state.order_flow_sell_ewma,
                        RATIO_PRECISION,
                    ),
                    order_flow_imbalance=round(
                        order_flow_imbalance,
                        RATIO_PRECISION,
                    ),
                    phi=round(
                        pressures[currency.value],
                        RATIO_PRECISION,
                    ),
                    hedge_capacity=round(
                        state.hedge_capacity,
                        RATIO_PRECISION,
                    ),
                    max_hedge_capacity=round(
                        state.max_hedge_capacity,
                        RATIO_PRECISION,
                    ),
                    hedge_capacity_used_ratio=round(
                        state.hedge_capacity_used_ratio,
                        RATIO_PRECISION,
                    ),
                    funding_cost_bps=round(
                        state.funding_cost_bps,
                        RATIO_PRECISION,
                    ),
                    market_volatility=round(
                        state.market_volatility,
                        RATIO_PRECISION,
                    ),
                    regime=regime,
                    event_accepted=event_accepted,
                    acceptance_probability=round(
                        acceptance_probability,
                        RATIO_PRECISION,
                    ),
                    cumulative_accepted_events=(
                        cumulative_accepted_events
                    ),
                    cumulative_rejected_events=(
                        cumulative_rejected_events
                    ),
                    cumulative_spread_revenue_usd=round(
                        cumulative_spread_revenue_usd,
                        6,
                    ),
                )
            )
        return result

    @staticmethod
    def _funding_cost_usd(ledger: InventoryLedger) -> float:
        total = ZERO_FLOAT

        for currency, state in ledger.get_all_states().items():
            usd_mark = StaticMidRateProvider.USD_MARKS[
                currency.value
            ]
            notional_usd = abs(state.position) * usd_mark

            total += (
                notional_usd
                * state.funding_cost_bps
                / BPS_DENOMINATOR
            )
        return total

    @staticmethod
    def _spread_revenue_usd(
        request: QuoteRequest,
        spread_bps: float,
    ) -> float:
        base_usd_mark = USD_MARKS[request.base_currency.value]
        notional_usd = request.amount * base_usd_mark

        return (
            notional_usd
            * spread_bps
            / BPS_DENOMINATOR
        )

    @staticmethod
    def _generate_requests(
        *,
        steps: int,
        dt_seconds: int,
        base_intensity: float,
        alpha: float,
        beta: float,
        seed: int | None,
        amount_multiplier: float,
    ) -> list[QuoteRequest]:
        generator = HawkesLikeFXEventGenerator(seed=seed)

        raw_requests = generator.simulate_quote_requests(
            steps=steps,
            dt_seconds=dt_seconds,
            base_intensity=base_intensity,
            alpha=alpha,
            beta=beta,
            start_at=datetime.now(timezone.utc),
        )

        return [
            replace(
                request, amount=request.amount * amount_multiplier,
            )
            for request in raw_requests
        ]


@dataclass(frozen=True)
class PolicyInventorySnapshot:
    event_index: int
    snapshot_ts: datetime

    currency: Currency

    position: float
    position_limit: float
    limit_utilization: float
    position_pressure: float

    order_flow_buy_ewma: float
    order_flow_sell_ewma: float
    order_flow_imbalance: float

    phi: float

    hedge_capacity: float
    max_hedge_capacity: float
    hedge_capacity_used_ratio: float

    funding_cost_bps: float
    market_volatility: float

    regime: StressRegime

    event_accepted: bool
    acceptance_probability: float

    cumulative_accepted_events: int
    cumulative_rejected_events: int
    cumulative_spread_revenue_usd: float
