from datetime import datetime
from uuid import UUID

from revolut_app.fx_lab.experiments.models import PolicyInventorySnapshot
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.risk.hamiltonian.models import HamiltonianBreakdown
from revolut_app.fx_lab.shared.constants import (
    EPSILON,
    RATIO_PRECISION,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.shared.enums import StressRegime


def capture_inventory_snapshots(
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
                source_event_id=source_event_id,
                source_step_index=source_step_index,
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
                    RATIO_PRECISION,
                ),
                h_total=(
                    round(
                        hamiltonian.total,
                        RATIO_PRECISION,
                    )
                    if hamiltonian is not None
                    else None
                ),
                h_quadratic=(
                    round(
                        hamiltonian.quadratic,
                        RATIO_PRECISION,
                    )
                    if hamiltonian is not None
                    else None
                ),
                h_quartic=(
                    round(
                        hamiltonian.quartic,
                        RATIO_PRECISION,
                    )
                    if hamiltonian is not None
                    else None
                ),
                h_coupling=(
                    round(
                        hamiltonian.coupling,
                        RATIO_PRECISION,
                    )
                    if hamiltonian is not None
                    else None
                ),
                h_external=(
                    round(
                        hamiltonian.external,
                        RATIO_PRECISION,
                    )
                    if hamiltonian is not None
                    else None
                ),
            )
        )
    return result
