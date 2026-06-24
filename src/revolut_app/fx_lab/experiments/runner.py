from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from statistics import mean
from uuid import uuid4

from revolut_app.fx_lab.experiments.metrics import (
    funding_cost_interval,
    spread_revenue_usd,
)
from revolut_app.fx_lab.experiments.models import (
    FXEventDataset,
    PolicyInventorySnapshot,
    PolicyRunResult,
)
from revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots,
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.inventory.stress import StressRegimeDetect
from revolut_app.fx_lab.pricing.acceptance import AcceptanceModel
from revolut_app.fx_lab.pricing.policies import (
    QuotePolicyName,
    build_quote_policy,
)
from revolut_app.fx_lab.pricing.quote_engine import QuoteEngine
from revolut_app.fx_lab.risk.hamiltonian.controller import (
    HamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.shared.constants import (
    ONE_INT,
    RATIO_PRECISION,
    ZERO_FLOAT,
    ZERO_INT,
)
from revolut_app.fx_lab.shared.enums import StressRegime


class PolicyExperimentRunner:
    def run_policy(
        self,
        *,
        policy_name: QuotePolicyName,
        event_dataset: FXEventDataset,
        amount_multiplier: float,
        acceptance_seed: int | None,
        snapshot_every_n_events: int,
        hamiltonian_engine: HamiltonianEngine | None,
        hamiltonian_controller: HamiltonianController | None = None,
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

        acceptance_model = AcceptanceModel(
            seed=acceptance_seed,
        )

        snapshots: list[PolicyInventorySnapshot] = []

        accepted_events = 0
        rejected_events = 0

        quoted_spread_values: list[float] = []
        accepted_spread_values: list[float] = []

        spread_revenue_total_usd = ZERO_FLOAT
        product_revenue_usd = ZERO_FLOAT
        funding_cost_usd = ZERO_FLOAT

        max_abs_pressure = ZERO_FLOAT
        regime_counter: Counter[str] = Counter()

        previous_event_ts = event_dataset.started_at

        initial_pressures = ledger.pressures()
        initial_regime = stress_detect.detect(
            pressures=initial_pressures,
            states={
                currency.value: state
                for currency, state in ledger.get_all_states().items()
            },
        )

        if hamiltonian_engine is not None:
            initial_hamiltonian = hamiltonian_engine.evaluate(
                initial_pressures
            )
        elif hamiltonian_controller is not None:
            initial_hamiltonian = hamiltonian_controller.engine.evaluate(
                initial_pressures
            )
        else:
            initial_hamiltonian = None

        snapshots.extend(
            capture_inventory_snapshots(
                event_index=ZERO_INT,
                source_event_id=None,
                source_step_index=None,
                snapshot_ts=event_dataset.started_at,
                ledger=ledger,
                pressures=initial_pressures,
                regime=initial_regime,
                event_accepted=False,
                acceptance_probability=ZERO_FLOAT,
                cumulative_accepted_events=ZERO_INT,
                cumulative_rejected_events=ZERO_INT,
                cumulative_spread_revenue_usd=ZERO_FLOAT,
                hamiltonian=initial_hamiltonian,
                controller_activated=None,
                controller_h_before_event=None,
                controller_spread_adjustment_bps=None,
            )
        )

        for event in event_dataset.events:
            elapsed_seconds = max(
                ZERO_FLOAT,
                (event.event_ts - previous_event_ts).total_seconds(),
            )

            funding_cost_usd += funding_cost_interval(
                ledger=ledger,
                elapsed_seconds=elapsed_seconds,
            )

            previous_event_ts = event.event_ts

            request = replace(
                event.request,
                amount=event.request.amount * amount_multiplier,
            )

            pressures_before_event = ledger.pressures()

            controller_hamiltonian = None
            control_decision = None

            if hamiltonian_controller is not None:
                controller_hamiltonian, control_decision = (
                    hamiltonian_controller.evaluate(pressures_before_event)
                )

            hamiltonian_penalty_bps = (
                control_decision.applied_adjustment_bps
                if control_decision is not None
                else 0.0
            )

            quote = quote_engine.quote(
                request=request,
                hamiltonian_penalty_bps=(
                    control_decision.applied_adjustment_bps
                    if control_decision is not None
                    else 0.0
                ),
            )

            decision = acceptance_model.decide(quote)

            total_spread_bps = quote.components.total_spread_bps

            quoted_spread_values.append(total_spread_bps)

            if decision.accepted:
                accepted_events += 1
                accepted_spread_values.append(total_spread_bps)

                revenue_usd = spread_revenue_usd(
                    request=request,
                    spread_bps=total_spread_bps,
                )

                spread_revenue_total_usd += revenue_usd

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
                event.event_sequence % snapshot_every_n_events == 0
                or event.event_sequence == len(event_dataset.events)
            )

            if should_capture:
                if hamiltonian_engine is not None:
                    hamiltonian = hamiltonian_engine.evaluate(
                        pressures
                    )
                elif hamiltonian_controller is not None:
                    hamiltonian = hamiltonian_controller.engine.evaluate(
                        pressures
                    )
                else:
                    hamiltonian = None

                snapshots.extend(
                    capture_inventory_snapshots(
                        event_index=event.event_sequence,
                        source_event_id=event.event_id,
                        source_step_index=event.source_step_index,
                        snapshot_ts=event.event_ts,
                        ledger=ledger,
                        pressures=pressures,
                        regime=regime,
                        event_accepted=decision.accepted,
                        acceptance_probability=decision.probability,
                        cumulative_accepted_events=accepted_events,
                        cumulative_rejected_events=rejected_events,
                        cumulative_spread_revenue_usd=(
                            spread_revenue_total_usd
                        ),
                        hamiltonian=hamiltonian,
                        controller_activated=(
                            control_decision.activated
                            if control_decision is not None
                            else None
                        ),
                        controller_h_before_event=(
                            control_decision.h_total
                            if control_decision is not None
                            else None
                        ),
                        controller_spread_adjustment_bps=(
                            control_decision.applied_adjustment_bps
                            if control_decision is not None
                            else None
                        ),
                    )
                )

        final_elapsed_seconds = max(
            ZERO_FLOAT,
            (event_dataset.finished_at - previous_event_ts).total_seconds(),
        )

        funding_cost_usd += funding_cost_interval(
            ledger=ledger,
            elapsed_seconds=final_elapsed_seconds,
        )

        final_pressures = ledger.pressures()

        final_regime = stress_detect.detect(
            pressures=final_pressures,
            states={
                currency.value: state
                for currency, state in ledger.get_all_states().items()
            },
        )

        net_pnl_usd = (
            spread_revenue_total_usd
            + product_revenue_usd
            - funding_cost_usd
        )

        total_requests = len(event_dataset.events)

        stress_count = regime_counter[
            StressRegime.stress.value
        ]

        average_quoted_spread = (
            mean(quoted_spread_values)
            if quoted_spread_values
            else ZERO_FLOAT
        )

        average_accepted_spread = (
            mean(accepted_spread_values)
            if accepted_spread_values
            else ZERO_FLOAT
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
                average_quoted_spread,
                RATIO_PRECISION
            ),
            average_accepted_spread_bps=round(
                average_accepted_spread,
                RATIO_PRECISION
            ),
            customer_spread_cost_usd=round(
                spread_revenue_total_usd,
                RATIO_PRECISION,
            ),
            spread_revenue_usd=round(
                spread_revenue_total_usd,
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
