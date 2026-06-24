import pytest

from src.revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots
)


def test_snapshot_contains_controller_decision():
    snapshots = capture_inventory_snapshots(
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
