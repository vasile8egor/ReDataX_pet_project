from datetime import datetime, timezone

import pytest

from revolut_app.fx_lab.experiments.snapshots import (
    capture_inventory_snapshots,
)
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.risk.hamiltonian import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.shared.constants import RATIO_PRECISION
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
    StressRegime,
)


def test_snapshot_contains_transition_diagnostics():
    hamiltonian_engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    transition = (
        hamiltonian_engine.evaluate_transition(
            pressures_before={
                "EUR": 0.20,
                "GBP": 0.10,
                "USD": -0.05,
            },
            pressures_after={
                "EUR": 0.25,
                "GBP": 0.08,
                "USD": -0.10,
            },
        )
    )

    snapshots = capture_inventory_snapshots(
        event_index=1,
        source_event_id=None,
        source_step_index=None,
        snapshot_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ledger=InventoryLedger(),
        pressures={
            "EUR": 0.25,
            "GBP": 0.08,
            "USD": -0.10,
        },
        regime=StressRegime.calm,
        event_accepted=True,
        acceptance_probability=1.0,
        cumulative_accepted_events=1,
        cumulative_rejected_events=0,
        cumulative_spread_revenue_usd=0.0,
        hamiltonian=transition.after,
        transition=transition,
    )

    assert snapshots

    for snapshot in snapshots:
        assert (
            snapshot.transition_h_before_event
            == pytest.approx(
                round(transition.h_before, RATIO_PRECISION)
            )
        )

        assert (
            snapshot.transition_h_after_if_accepted
            == pytest.approx(
                round(transition.h_after, RATIO_PRECISION)
            )
        )

        assert (
            snapshot.transition_delta_h_if_accepted
            == pytest.approx(
                round(transition.delta_total, RATIO_PRECISION)
            )
        )
