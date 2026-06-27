from __future__ import annotations

import numpy as np

from revolut_app.real_market.experiments.adverse_selection_oos import (
    DayData,
    SCALES,
    causal_imbalances,
    feature_matrices,
    future_vwap_markout,
)


def make_data() -> DayData:
    return DayData(
        timestamp_us=np.array(
            [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000],
            dtype=np.int64,
        ),
        price=np.array([100.0, 101.0, 102.0, 103.0, 104.0]),
        base_quantity=np.ones(5),
        aggressor_sign=np.array([1, -1, 1, 1, -1], dtype=np.int8),
        notional_usdt=np.array([100.0, 101.0, 102.0, 103.0, 104.0]),
    )


def test_causal_feature_does_not_use_current_event() -> None:
    data = make_data()
    changed = DayData(
        timestamp_us=data.timestamp_us,
        price=data.price,
        base_quantity=data.base_quantity,
        aggressor_sign=np.array([1, -1, -1, 1, -1], dtype=np.int8),
        notional_usdt=np.array([100.0, 101.0, 999999.0, 103.0, 104.0]),
    )

    original_phi = causal_imbalances(data)
    changed_phi = causal_imbalances(changed)

    # Event index 2 may only use events 0 and 1 for B=2.
    scale_index = SCALES.index(2)
    assert original_phi[2, scale_index] == changed_phi[2, scale_index]


def test_future_vwap_markout_uses_requested_future_window() -> None:
    data = make_data()
    markout = future_vwap_markout(
        data,
        horizon_seconds=1,
        window_seconds=1,
    )

    # For event 0, target window [1s, 2s] contains prices 101 and 102.
    assert markout[0] == 150.0


def test_feature_hierarchy_has_increasing_dimension() -> None:
    data = make_data()
    phi = np.tile(
        np.linspace(-0.5, 0.5, len(SCALES)),
        (data.price.size, 1),
    )
    features = feature_matrices(data, phi)

    assert features["m0_single_scale"].shape[1] < features["m1_multiscale"].shape[1]
    assert features["m1_multiscale"].shape[1] < features["m2_rg_flow"].shape[1]
