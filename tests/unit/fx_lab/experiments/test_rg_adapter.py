from datetime import datetime, timezone

from revolut_app.fx_lab.experiments.rg_adapter import (
    inventory_snapshots_to_rg_observations,
)
from revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots,
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.risk.rg import (
    TrajectoryExtractionParameters,
    extract_pressure_trajectories,
)
from revolut_app.fx_lab.shared.enums import StressRegime


def test_inventory_snapshots_convert_to_rg_observations():
    ledger = InventoryLedger()
    pressures = ledger.pressures()

    snapshots = capture_inventory_snapshots(
        event_index=1,
        source_event_id=None,
        source_step_index=None,
        snapshot_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ledger=ledger,
        pressures=pressures,
        regime=StressRegime.calm,
        event_accepted=True,
        acceptance_probability=1.0,
        cumulative_accepted_events=1,
        cumulative_rejected_events=0,
        cumulative_spread_revenue_usd=0.0,
        hamiltonian=None,
    )

    observations = inventory_snapshots_to_rg_observations(
        snapshots,
        trajectory_id='run-1',
    )

    assert {
        observation.currency: observation.pressure
        for observation in observations
    } == pressures

    assert {
        observation.trajectory_id
        for observation in observations
    } == {'run-1'}

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=TrajectoryExtractionParameters(
            expected_currencies=tuple(sorted(pressures)),
        ),
    )

    assert len(trajectories['run-1']) == 1
    assert trajectories['run-1'][0].pressures == pressures
