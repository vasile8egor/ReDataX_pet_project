from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from revolut_app.fx_lab.experiments.metrics import (
    funding_cost_interval,
    spread_revenue_usd,
)
from revolut_app.fx_lab.experiments.models import (
    FXEventDataset,
    PolicyComparisonResult,
)
from revolut_app.fx_lab.experiments.runner import PolicyExperimentRunner
from revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots,
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.pricing.policies import QuotePolicyName
from revolut_app.fx_lab.risk.hamiltonian.controller import (
    HamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.risk.hamiltonian.models import HamiltonianBreakdown
from revolut_app.fx_lab.shared.enums import StressRegime


class PolicyComparisonEngine:
    def __init__(self, runner: PolicyExperimentRunner | None = None):
        self.runner = runner or PolicyExperimentRunner()

    def compare(
        self,
        *,
        policy_names: list[QuotePolicyName],
        event_dataset: FXEventDataset,
        amount_multiplier: float,
        snapshot_every_n_events: int,
        hamiltonian_engine: HamiltonianEngine | None = None,
        hamiltonian_controller: HamiltonianController | None = None,
    ) -> PolicyComparisonResult:
        if (
            hamiltonian_engine is not None
            and hamiltonian_controller is not None
        ):
            raise ValueError(
                'Observer and controller cant be enabled together'
            )
        started_at = datetime.now(timezone.utc)
        comparison_id = str(uuid4())

        acceptance_seed = event_dataset.seed

        results = [
            self.runner.run_policy(
                policy_name=policy_name,
                event_dataset=event_dataset,
                amount_multiplier=amount_multiplier,
                acceptance_seed=acceptance_seed,
                snapshot_every_n_events=snapshot_every_n_events,
                hamiltonian_engine=hamiltonian_engine,
                hamiltonian_controller=hamiltonian_controller,
            )
            for policy_name in policy_names
        ]

        return PolicyComparisonResult(
            comparison_id=comparison_id,
            event_dataset_id=str(event_dataset.event_dataset_id),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            generated_requests=len(event_dataset.events),
            seed=event_dataset.seed,
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
            ).policy,
        )

    @staticmethod
    def _funding_cost_interval(
        ledger: InventoryLedger,
        elapsed_seconds: float,
    ):
        return funding_cost_interval(
            ledger=ledger,
            elapsed_seconds=elapsed_seconds,
        )

    @staticmethod
    def _spread_revenue_usd(
        request: QuoteRequest,
        spread_bps: float,
    ) -> float:
        return spread_revenue_usd(
            request=request,
            spread_bps=spread_bps,
        )

    @staticmethod
    def _capture_inventory_snapshots(
        event_index: int,
        source_event_id: UUID | None,
        source_step_index: int | None,
        snapshot_ts: datetime,
        ledger: InventoryLedger,
        pressures: dict[str, float],
        regime: StressRegime,
        event_accepted: bool,
        acceptance_probability: float,
        cumulative_accepted_events: int,
        cumulative_rejected_events: int,
        cumulative_spread_revenue_usd: float,
        hamiltonian: HamiltonianBreakdown | None,
    ):
        return capture_inventory_snapshots(
            event_index=event_index,
            source_event_id=source_event_id,
            source_step_index=source_step_index,
            snapshot_ts=snapshot_ts,
            ledger=ledger,
            pressures=pressures,
            regime=regime,
            event_accepted=event_accepted,
            acceptance_probability=acceptance_probability,
            cumulative_accepted_events=cumulative_accepted_events,
            cumulative_rejected_events=cumulative_rejected_events,
            cumulative_spread_revenue_usd=cumulative_spread_revenue_usd,
            hamiltonian=hamiltonian,
        )
