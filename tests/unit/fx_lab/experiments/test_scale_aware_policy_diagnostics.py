from dataclasses import replace

import pytest

from revolut_app.fx_lab.experiments import (
    PolicyComparisonEngine,
)
from revolut_app.fx_lab.inventory.ledger import (
    InventoryLedger,
)
from revolut_app.fx_lab.inventory.stress import (
    StressRegimeDetect,
)
from revolut_app.fx_lab.pricing.policies import (
    QuotePolicyName,
    build_quote_policy,
)
from revolut_app.fx_lab.pricing.quote_engine import (
    QuoteEngine,
)
from revolut_app.fx_lab.risk.hamiltonian import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.risk.rg import (
    EffectiveHamiltonianEvaluator,
    RG_EFFECTIVE_LOCAL_B16,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
    ScaleAwareDiagnosticPreset,
)

from .test_policy_reproducibility import (
    _policy_signature,
)


def _compare(
    fx_event_dataset,
    *,
    diagnostics_enabled: bool,
):
    return PolicyComparisonEngine().compare(
        policy_names=[
            QuotePolicyName.inventory_aware,
            QuotePolicyName.naive,
        ],
        event_dataset=fx_event_dataset,
        amount_multiplier=500.0,
        snapshot_every_n_events=10,
        hamiltonian_engine=build_hamiltonian_engine(
            HamiltonianPreset.local_v1
        ),
        scale_aware_diagnostic_preset=(
            ScaleAwareDiagnosticPreset.RG_LOCAL_B16_V1
            if diagnostics_enabled
            else None
        ),
    )


def test_scale_aware_diagnostics_do_not_change_policy_results(
    fx_event_dataset,
):
    disabled = _compare(
        fx_event_dataset,
        diagnostics_enabled=False,
    )
    enabled = _compare(
        fx_event_dataset,
        diagnostics_enabled=True,
    )

    disabled_by_policy = {
        result.policy: _policy_signature(result)
        for result in disabled.results
    }
    enabled_by_policy = {
        result.policy: _policy_signature(result)
        for result in enabled.results
    }

    assert enabled_by_policy == disabled_by_policy

    for result in enabled.results:
        assert (
            len(result.scale_aware_transition_diagnostics)
            == result.generated_requests
        )


def test_scale_aware_diagnostics_ready_after_block_history(
    fx_event_dataset,
):
    result = _compare(
        fx_event_dataset,
        diagnostics_enabled=True,
    ).results[0]

    diagnostics = (
        result.scale_aware_transition_diagnostics
    )

    assert [
        item.history_ready
        for item in diagnostics[:16]
    ] == [False] * 16
    assert diagnostics[16].event_index == 17
    assert diagnostics[16].history_ready is True


def test_scale_aware_diagnostics_commit_actual_state(
    fx_event_dataset,
):
    result = _compare(
        fx_event_dataset,
        diagnostics_enabled=True,
    ).results[0]

    diagnostics = (
        result.scale_aware_transition_diagnostics
    )
    accepted_index = next(
        index
        for index, item in enumerate(
            diagnostics[:-1]
        )
        if item.event_index >= 17
        and item.request_accepted
        and diagnostics[index + 1].history_ready
    )
    rejected_index = next(
        index
        for index, item in enumerate(
            diagnostics[:-1]
        )
        if item.event_index >= 17
        and not item.request_accepted
        and diagnostics[index + 1].history_ready
    )

    expected_coarse_h_before = (
        _expected_ready_coarse_h_before(
            fx_event_dataset=fx_event_dataset,
            policy_name=result.policy,
            amount_multiplier=500.0,
        )
    )

    assert diagnostics[
        accepted_index + 1
    ].coarse_h_before == pytest.approx(
        expected_coarse_h_before[
            diagnostics[
                accepted_index + 1
            ].event_index
        ]
    )
    assert diagnostics[
        rejected_index + 1
    ].coarse_h_before == pytest.approx(
        expected_coarse_h_before[
            diagnostics[
                rejected_index + 1
            ].event_index
        ]
    )


def _expected_ready_coarse_h_before(
    *,
    fx_event_dataset,
    policy_name: QuotePolicyName,
    amount_multiplier: float,
):
    ledger = InventoryLedger()
    stress_detect = StressRegimeDetect()
    quote_engine = QuoteEngine(
        ledger=ledger,
        stress_detect=stress_detect,
        policy=build_quote_policy(
            name=policy_name,
            stress_detect=stress_detect,
        ),
    )
    hamiltonian = EffectiveHamiltonianEvaluator(
        coefficients=RG_EFFECTIVE_LOCAL_B16
    )
    actual_history: list[dict[str, float]] = []
    result = _compare(
        fx_event_dataset,
        diagnostics_enabled=True,
    ).results[0]
    decisions = {
        item.event_index: item.request_accepted
        for item in (
            result.scale_aware_transition_diagnostics
        )
    }
    expected: dict[int, float] = {}

    for event in fx_event_dataset.events:
        if len(actual_history) == 16:
            coarse_before = {
                currency: sum(
                    frame[currency]
                    for frame in actual_history
                )
                / 16
                for currency in ('EUR', 'GBP', 'USD')
            }
            expected[event.event_sequence] = (
                hamiltonian.evaluate(coarse_before)
            )

        request = replace(
            event.request,
            amount=(
                event.request.amount
                * amount_multiplier
            ),
        )
        mid_rate = quote_engine.get_mid_rate(
            request
        )
        projected = ledger.project_after_client_fx(
            request=request,
            mid_rate=mid_rate,
        )

        if decisions[event.event_sequence]:
            ledger.apply_client_fx(
                request=request,
                mid_rate=mid_rate,
            )
            actual = projected.pressures()
        else:
            actual = ledger.pressures()

        actual_history.append(actual)
        actual_history = actual_history[-16:]

    return expected
