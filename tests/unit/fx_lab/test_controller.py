from datetime import datetime, timezone

import pytest

from revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.shared.enums import StressRegime


def test_snapshot_contains_controller_decision():
    ledger = InventoryLedger()

    snapshots = capture_inventory_snapshots(
        event_index=1,
        source_event_id=None,
        source_step_index=None,
        snapshot_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ledger=ledger,
        pressures=ledger.pressures(),
        regime=StressRegime.calm,
        event_accepted=True,
        acceptance_probability=1.0,
        cumulative_accepted_events=1,
        cumulative_rejected_events=0,
        cumulative_spread_revenue_usd=10.0,
        hamiltonian=None,
        controller_activated=True,
        controller_h_before_event=1.25,
        controller_spread_adjustment_bps=1.1,
    )

    assert snapshots
    assert all(
        snapshot.controller_activated is True
        for snapshot in snapshots
    )
    assert all(
        snapshot.controller_h_before_event == pytest.approx(1.25)
        for snapshot in snapshots
    )
    assert all(
        snapshot.controller_spread_adjustment_bps == pytest.approx(1.1)
        for snapshot in snapshots
    )
