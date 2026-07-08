from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from revolut_app.real_market.experiments import coupled_rg_final as coupled
from revolut_app.real_market.experiments.queries import SECONDLY_NOTIONAL_SQL


DEFAULT_HORIZONS_SECONDS = (
    5,
    10,
    15,
    30,
    60,
    120,
    300,
    600,
    1800,
    3600,
    7200,
)
DEFAULT_NOTIONAL_BUDGETS = (0.005, 0.01, 0.02, 0.05, 0.10)


@dataclass(frozen=True)
class OracleScenario:
    name: str
    mitigation_efficiency: float
    internalization_rate: float
    action_cost_bps: float

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError('scenario name cannot be empty')
        if not 0.0 <= self.mitigation_efficiency <= 1.0:
            raise ValueError('mitigation_efficiency must be in [0, 1]')
        if not 0.0 <= self.internalization_rate <= 1.0:
            raise ValueError('internalization_rate must be in [0, 1]')
        if self.action_cost_bps < 0.0:
            raise ValueError('action_cost_bps cannot be negative')

    @property
    def protection_fraction(self):
        return self.mitigation_efficiency * self.internalization_rate

    @property
    def break_even_markout_bps(self):
        if self.protection_fraction <= 0.0:
            return float('inf')
        return self.action_cost_bps / self.protection_fraction


@dataclass(frozen=True)
class OracleDayData:
    markout_bps: np.ndarray
    notional_usdt: np.ndarray
    adverse_loss_usdt: np.ndarray


@dataclass(frozen=True)
class MarkoutDistribution:
    observations: int
    positive_markout_fraction: float
    above_break_even_event_fraction: float
    above_break_even_notional_fraction: float
    positive_markout_p50_bps: float
    positive_markout_p90_bps: float
    positive_markout_p95_bps: float
    positive_markout_p99_bps: float
    maximum_positive_markout_bps: float


@dataclass(frozen=True)
class OracleMetrics:
    observations: int
    acted_observations: int
    acted_event_fraction: float
    mean_action_fraction_on_acted_events: float

    total_notional_usdt: float
    acted_notional_usdt: float
    acted_notional_fraction: float

    total_adverse_loss_usdt: float
    captured_adverse_loss_usdt: float
    capture_rate: float
    risk_concentration: float

    gross_protected_value_usdt: float
    action_cost_usdt: float
    net_protected_value_usdt: float

    gross_value_per_million_usdt: float
    net_value_per_million_usdt: float
    break_even_action_cost_bps: float
    benefit_cost_ratio: float

    profitable: bool


@dataclass(frozen=True)
class StabilityMetrics:
    days: int
    mean_daily_net_value_per_million_usdt: float
    median_daily_net_value_per_million_usdt: float
    std_daily_net_value_per_million_usdt: float
    worst_day_net_value_per_million_usdt: float
    positive_day_fraction: float
    robust_score: float
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    strictly_feasible: bool


def parse_scenario(value: str):
    parts = value.split(':')
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            'scenario must be '
            'NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS'
        )
    name, mitigation, internalization, cost = parts
    try:
        return OracleScenario(
            name=name,
            mitigation_efficiency=float(mitigation),
            internalization_rate=float(internalization),
            action_cost_bps=float(cost),
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_positive_int(value: str):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('value must be positive')
    return parsed


def parse_fraction(value: str):
    parsed = float(value)
    if not 0.0 < parsed <= 1.0:
        raise argparse.ArgumentTypeError('fraction must be in (0, 1]')
    return parsed


def parse_non_negative_float(value: str):
    parsed = float(value)
    if parsed < 0.0:
        raise argparse.ArgumentTypeError('value cannot be negative')
    return parsed


def load_second_notional(
    clickhouse: Any,
    trade_date: date,
):
    rows = clickhouse.execute(
        SECONDLY_NOTIONAL_SQL,
        {
            'trade_date': trade_date,
            'day_start_us': coupled.utc_midnight_us(trade_date),
            'symbols': coupled.TARGET_SYMBOLS,
        },
    )

    matrix = np.zeros(
        (coupled.SECONDS_PER_DAY, len(coupled.SYMBOLS)),
        dtype=np.float64,
    )
    symbol_index = {
        symbol: index
        for index, symbol in enumerate(coupled.SYMBOLS)
    }
    counts = {symbol: 0 for symbol in coupled.TARGET_SYMBOLS}

    for second_index, symbol, quote_notional in rows:
        second = int(second_index)
        symbol_text = str(symbol)
        if symbol_text not in symbol_index:
            raise ValueError(f'''unexpected symbol: {symbol_text}''')
        if not 0 <= second < coupled.SECONDS_PER_DAY:
            raise ValueError(f'''invalid second index: {second}''')

        value = float(quote_notional)
        if value < 0.0:
            raise ValueError('negative quote notional')

        matrix[second, symbol_index[symbol_text]] = value
        if symbol_text in counts:
            counts[symbol_text] += 1

    missing = [
        symbol for symbol, count in counts.items()
        if count == 0
    ]
    if missing:
        raise ValueError(
            f'''missing target-symbol notional on {trade_date}: {missing}'''
        )

    return matrix


def build_oracle_day_data(
    day: coupled.MarketDay,
    second_notional: np.ndarray,
    *,
    target_symbol: str,
    horizon_seconds: int,
):
    if target_symbol not in coupled.TARGET_SYMBOLS:
        raise ValueError(f'''unsupported target symbol: {target_symbol}''')
    if horizon_seconds <= 0:
        raise ValueError('horizon_seconds must be positive')
    expected_shape = (
        coupled.SECONDS_PER_DAY,
        len(coupled.SYMBOLS),
    )
    if second_notional.shape != expected_shape:
        raise ValueError(
            f'''second_notional must have shape {expected_shape}'''
        )

    target_index = coupled.SYMBOLS.index(target_symbol)
    seconds = np.arange(coupled.SECONDS_PER_DAY, dtype=np.int64)
    future_seconds = seconds + horizon_seconds

    current_flow = day.phi[:, target_index]
    side = np.sign(current_flow)
    safe_future = np.minimum(
        future_seconds,
        coupled.SECONDS_PER_DAY - 1,
    )

    current_vwap = day.vwap[:, target_index]
    future_vwap = day.vwap[safe_future, target_index]

    valid = (
        (seconds >= max(coupled.SCALES_SECONDS) - 1)
        & (future_seconds < coupled.SECONDS_PER_DAY)
        & day.active[:, target_index]
        & (side != 0)
        & np.isfinite(current_vwap)
        & np.isfinite(future_vwap)
        & (current_vwap > 0.0)
        & (future_vwap > 0.0)
    )
    indices = np.flatnonzero(valid)
    if indices.size == 0:
        raise ValueError(
            f'''no valid observations for {target_symbol}, '''
            f'''{day.trade_date}, H={horizon_seconds}'''
        )

    notional = second_notional[indices, target_index]
    positive_notional = np.isfinite(notional) & (notional > 0.0)
    indices = indices[positive_notional]
    notional = notional[positive_notional].astype(
        np.float64,
        copy=False,
    )
    if indices.size == 0:
        raise ValueError(
            f'''no positive notional observations for {target_symbol}, '''
            f'''{day.trade_date}, H={horizon_seconds}'''
        )

    markout = (
        side[indices].astype(np.float64)
        * (
            day.vwap[indices + horizon_seconds, target_index]
            - day.vwap[indices, target_index]
        )
        / day.vwap[indices, target_index]
        * 10_000.0
    )
    if np.any(~np.isfinite(markout)):
        raise ValueError('non-finite markout after validation')

    adverse_loss = (
        notional
        * np.maximum(markout, 0.0)
        / 10_000.0
    )
    return OracleDayData(
        markout_bps=markout,
        notional_usdt=notional,
        adverse_loss_usdt=adverse_loss,
    )


def distribution_metrics(
    data: OracleDayData,
    *,
    break_even_markout_bps: float,
):
    positive = np.maximum(data.markout_bps, 0.0)
    positive_values = positive[positive > 0.0]
    above_break_even = positive > break_even_markout_bps

    total_notional = float(
        np.sum(data.notional_usdt, dtype=np.float64)
    )
    above_notional = float(
        np.sum(
            data.notional_usdt[above_break_even],
            dtype=np.float64,
        )
    )

    if positive_values.size:
        quantiles = np.quantile(
            positive_values,
            [0.50, 0.90, 0.95, 0.99],
        )
        maximum = float(np.max(positive_values))
    else:
        quantiles = np.zeros(4, dtype=np.float64)
        maximum = 0.0

    return MarkoutDistribution(
        observations=int(data.markout_bps.size),
        positive_markout_fraction=float(
            np.mean(data.markout_bps > 0.0)
        ),
        above_break_even_event_fraction=float(
            np.mean(above_break_even)
        ),
        above_break_even_notional_fraction=float(
            above_notional / total_notional
            if total_notional > 0.0
            else 0.0
        ),
        positive_markout_p50_bps=float(quantiles[0]),
        positive_markout_p90_bps=float(quantiles[1]),
        positive_markout_p95_bps=float(quantiles[2]),
        positive_markout_p99_bps=float(quantiles[3]),
        maximum_positive_markout_bps=maximum,
    )


def _empty_oracle_metrics(
    data: OracleDayData,
):
    total_notional = float(
        np.sum(data.notional_usdt, dtype=np.float64)
    )
    total_loss = float(
        np.sum(data.adverse_loss_usdt, dtype=np.float64)
    )
    return OracleMetrics(
        observations=int(data.markout_bps.size),
        acted_observations=0,
        acted_event_fraction=0.0,
        mean_action_fraction_on_acted_events=0.0,
        total_notional_usdt=total_notional,
        acted_notional_usdt=0.0,
        acted_notional_fraction=0.0,
        total_adverse_loss_usdt=total_loss,
        captured_adverse_loss_usdt=0.0,
        capture_rate=0.0,
        risk_concentration=0.0,
        gross_protected_value_usdt=0.0,
        action_cost_usdt=0.0,
        net_protected_value_usdt=0.0,
        gross_value_per_million_usdt=0.0,
        net_value_per_million_usdt=0.0,
        break_even_action_cost_bps=0.0,
        benefit_cost_ratio=0.0,
        profitable=False,
    )


def oracle_metrics_for_budgets(
    data: OracleDayData,
    *,
    scenario: OracleScenario,
    budget_fractions: tuple[float, ...],
):
    if not budget_fractions:
        raise ValueError('budget_fractions cannot be empty')

    positive_markout = np.maximum(data.markout_bps, 0.0)
    realized_net_bps = (
        scenario.protection_fraction * positive_markout
        - scenario.action_cost_bps
    )
    eligible_indices = np.flatnonzero(realized_net_bps > 0.0)

    if eligible_indices.size == 0:
        empty = _empty_oracle_metrics(data)
        return {
            budget: empty for budget in budget_fractions
        }

    order = eligible_indices[
        np.argsort(
            realized_net_bps[eligible_indices],
            kind='stable',
        )[::-1]
    ]
    sorted_notional = data.notional_usdt[order]
    sorted_loss = data.adverse_loss_usdt[order]

    cumulative_notional = np.cumsum(
        sorted_notional,
        dtype=np.float64,
    )
    cumulative_loss = np.cumsum(
        sorted_loss,
        dtype=np.float64,
    )

    total_notional = float(
        np.sum(data.notional_usdt, dtype=np.float64)
    )
    total_loss = float(
        np.sum(data.adverse_loss_usdt, dtype=np.float64)
    )
    eligible_notional = float(cumulative_notional[-1])

    output: dict[float, OracleMetrics] = {}
    for budget_fraction in budget_fractions:
        if not 0.0 < budget_fraction <= 1.0:
            raise ValueError('budget fraction must be in (0, 1]')

        requested_budget = total_notional * budget_fraction
        acted_notional = min(
            requested_budget,
            eligible_notional,
        )

        full_count = int(
            np.searchsorted(
                cumulative_notional,
                acted_notional,
                side='right',
            )
        )
        previous_notional = (
            float(cumulative_notional[full_count - 1])
            if full_count > 0
            else 0.0
        )
        captured_loss = (
            float(cumulative_loss[full_count - 1])
            if full_count > 0
            else 0.0
        )

        partial_fraction = 0.0
        if (
            full_count < sorted_notional.size
            and acted_notional > previous_notional
        ):
            remainder = acted_notional - previous_notional
            partial_fraction = (
                remainder / float(sorted_notional[full_count])
            )
            captured_loss += (
                partial_fraction
                * float(sorted_loss[full_count])
            )

        acted_observations = (
            full_count + int(partial_fraction > 0.0)
        )
        action_fraction_sum = full_count + partial_fraction
        mean_action_fraction = (
            action_fraction_sum / acted_observations
            if acted_observations > 0
            else 0.0
        )

        gross_value = (
            scenario.protection_fraction * captured_loss
        )
        action_cost = (
            acted_notional
            * scenario.action_cost_bps
            / 10_000.0
        )
        net_value = gross_value - action_cost

        acted_notional_fraction = (
            acted_notional / total_notional
            if total_notional > 0.0
            else 0.0
        )
        capture_rate = (
            captured_loss / total_loss
            if total_loss > 0.0
            else 0.0
        )
        risk_concentration = (
            capture_rate / acted_notional_fraction
            if acted_notional_fraction > 0.0
            else 0.0
        )
        break_even_cost = (
            10_000.0 * gross_value / acted_notional
            if acted_notional > 0.0
            else 0.0
        )
        benefit_cost_ratio = (
            gross_value / action_cost
            if action_cost > 0.0
            else 0.0
        )

        output[budget_fraction] = OracleMetrics(
            observations=int(data.markout_bps.size),
            acted_observations=acted_observations,
            acted_event_fraction=float(
                acted_observations / data.markout_bps.size
            ),
            mean_action_fraction_on_acted_events=float(
                mean_action_fraction
            ),
            total_notional_usdt=total_notional,
            acted_notional_usdt=float(acted_notional),
            acted_notional_fraction=float(
                acted_notional_fraction
            ),
            total_adverse_loss_usdt=total_loss,
            captured_adverse_loss_usdt=float(captured_loss),
            capture_rate=float(capture_rate),
            risk_concentration=float(risk_concentration),
            gross_protected_value_usdt=float(gross_value),
            action_cost_usdt=float(action_cost),
            net_protected_value_usdt=float(net_value),
            gross_value_per_million_usdt=float(
                gross_value / total_notional * 1_000_000.0
            ),
            net_value_per_million_usdt=float(
                net_value / total_notional * 1_000_000.0
            ),
            break_even_action_cost_bps=float(
                break_even_cost
            ),
            benefit_cost_ratio=float(benefit_cost_ratio),
            profitable=bool(net_value > 0.0),
        )

    return output


def aggregate_oracle_metrics(
    daily_metrics: list[OracleMetrics],
    *,
    scenario: OracleScenario,
):
    if not daily_metrics:
        raise ValueError('daily_metrics cannot be empty')

    observations = sum(item.observations for item in daily_metrics)
    acted_observations = sum(
        item.acted_observations for item in daily_metrics
    )
    total_notional = sum(
        item.total_notional_usdt for item in daily_metrics
    )
    acted_notional = sum(
        item.acted_notional_usdt for item in daily_metrics
    )
    total_loss = sum(
        item.total_adverse_loss_usdt for item in daily_metrics
    )
    captured_loss = sum(
        item.captured_adverse_loss_usdt for item in daily_metrics
    )

    gross_value = scenario.protection_fraction * captured_loss
    action_cost = (
        acted_notional
        * scenario.action_cost_bps
        / 10_000.0
    )
    net_value = gross_value - action_cost

    acted_event_fraction = (
        acted_observations / observations
        if observations > 0
        else 0.0
    )
    acted_notional_fraction = (
        acted_notional / total_notional
        if total_notional > 0.0
        else 0.0
    )
    capture_rate = (
        captured_loss / total_loss
        if total_loss > 0.0
        else 0.0
    )
    risk_concentration = (
        capture_rate / acted_notional_fraction
        if acted_notional_fraction > 0.0
        else 0.0
    )

    weighted_action_fraction = sum(
        item.mean_action_fraction_on_acted_events
        * item.acted_observations
        for item in daily_metrics
    )
    mean_action_fraction = (
        weighted_action_fraction / acted_observations
        if acted_observations > 0
        else 0.0
    )

    return OracleMetrics(
        observations=observations,
        acted_observations=acted_observations,
        acted_event_fraction=float(acted_event_fraction),
        mean_action_fraction_on_acted_events=float(
            mean_action_fraction
        ),
        total_notional_usdt=float(total_notional),
        acted_notional_usdt=float(acted_notional),
        acted_notional_fraction=float(acted_notional_fraction),
        total_adverse_loss_usdt=float(total_loss),
        captured_adverse_loss_usdt=float(captured_loss),
        capture_rate=float(capture_rate),
        risk_concentration=float(risk_concentration),
        gross_protected_value_usdt=float(gross_value),
        action_cost_usdt=float(action_cost),
        net_protected_value_usdt=float(net_value),
        gross_value_per_million_usdt=float(
            gross_value / total_notional * 1_000_000.0
            if total_notional > 0.0
            else 0.0
        ),
        net_value_per_million_usdt=float(
            net_value / total_notional * 1_000_000.0
            if total_notional > 0.0
            else 0.0
        ),
        break_even_action_cost_bps=float(
            10_000.0 * gross_value / acted_notional
            if acted_notional > 0.0
            else 0.0
        ),
        benefit_cost_ratio=float(
            gross_value / action_cost
            if action_cost > 0.0
            else 0.0
        ),
        profitable=bool(net_value > 0.0),
    )


def bootstrap_daily_mean(
    values: list[float],
    *,
    samples: int,
    seed: int,
):
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or np.any(~np.isfinite(array)):
        raise ValueError('bootstrap values must be finite and non-empty')
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0,
        array.size,
        size=(samples, array.size),
    )
    means = np.mean(array[indices], axis=1)
    return (
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def stability_metrics(
    daily_metrics: list[OracleMetrics],
    *,
    risk_penalty: float,
    minimum_positive_day_fraction: float,
    bootstrap_samples: int,
    seed: int,
):
    values = np.asarray(
        [
            item.net_value_per_million_usdt
            for item in daily_metrics
        ],
        dtype=np.float64,
    )
    mean = float(np.mean(values))
    median = float(np.median(values))
    standard_deviation = float(np.std(values, ddof=0))
    worst = float(np.min(values))
    positive_fraction = float(np.mean(values > 0.0))
    robust_score = mean - risk_penalty * standard_deviation
    ci_lower, ci_upper = bootstrap_daily_mean(
        values.tolist(),
        samples=bootstrap_samples,
        seed=seed,
    )

    strictly_feasible = bool(
        mean > 0.0
        and robust_score > 0.0
        and positive_fraction >= minimum_positive_day_fraction
        and ci_lower > 0.0
    )
    return StabilityMetrics(
        days=int(values.size),
        mean_daily_net_value_per_million_usdt=mean,
        median_daily_net_value_per_million_usdt=median,
        std_daily_net_value_per_million_usdt=standard_deviation,
        worst_day_net_value_per_million_usdt=worst,
        positive_day_fraction=positive_fraction,
        robust_score=float(robust_score),
        bootstrap_ci_lower=ci_lower,
        bootstrap_ci_upper=ci_upper,
        strictly_feasible=strictly_feasible,
    )


def pooled_distribution(
    markout_arrays: list[np.ndarray],
    notional_arrays: list[np.ndarray],
    *,
    break_even_markout_bps: float,
):
    if not markout_arrays or not notional_arrays:
        raise ValueError('pooled arrays cannot be empty')
    return distribution_metrics(
        OracleDayData(
            markout_bps=np.concatenate(markout_arrays),
            notional_usdt=np.concatenate(notional_arrays),
            adverse_loss_usdt=np.empty(0, dtype=np.float64),
        ),
        break_even_markout_bps=break_even_markout_bps,
    )


def _candidate_record(
    *,
    target_symbol: str,
    horizon_seconds: int,
    budget_fraction: float,
    aggregate: OracleMetrics,
    stability: StabilityMetrics,
    distribution: MarkoutDistribution,
):
    return {
        'target_symbol': target_symbol,
        'horizon_seconds': horizon_seconds,
        'notional_budget_fraction': budget_fraction,
        'aggregate_net_value_per_million_usdt': (
            aggregate.net_value_per_million_usdt
        ),
        'mean_daily_net_value_per_million_usdt': (
            stability.mean_daily_net_value_per_million_usdt
        ),
        'robust_score': stability.robust_score,
        'positive_day_fraction': stability.positive_day_fraction,
        'bootstrap_ci_lower': stability.bootstrap_ci_lower,
        'bootstrap_ci_upper': stability.bootstrap_ci_upper,
        'strictly_feasible': stability.strictly_feasible,
        'above_break_even_event_fraction': (
            distribution.above_break_even_event_fraction
        ),
        'above_break_even_notional_fraction': (
            distribution.above_break_even_notional_fraction
        ),
        'acted_notional_fraction': (
            aggregate.acted_notional_fraction
        ),
        'capture_rate': aggregate.capture_rate,
        'break_even_action_cost_bps': (
            aggregate.break_even_action_cost_bps
        ),
        'benefit_cost_ratio': aggregate.benefit_cost_ratio,
    }


def select_recommendations(
    candidates: list[dict[str, Any]],
):
    feasible = [
        item for item in candidates
        if item['strictly_feasible']
    ]
    if not feasible:
        return {
            'status': 'no_strictly_feasible_oracle_candidate',
            'best_by_robust_score': None,
            'capital_efficient_candidate': None,
        }

    best = max(
        feasible,
        key=lambda item: (
            item['robust_score'],
            item['mean_daily_net_value_per_million_usdt'],
        ),
    )
    threshold = best['robust_score'] * 0.95
    near_best = [
        item for item in feasible
        if item['robust_score'] >= threshold
    ]
    capital_efficient = min(
        near_best,
        key=lambda item: (
            item['notional_budget_fraction'],
            item['horizon_seconds'],
            -item['robust_score'],
        ),
    )
    return {
        'status': 'strictly_feasible_oracle_candidates_found',
        'best_by_robust_score': best,
        'capital_efficient_candidate': capital_efficient,
    }


def write_json(path: str | Path, payload: dict[str, Any]):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.part')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(temporary, output)


def write_csv(
    path: str | Path,
    rows: list[dict[str, Any]],
):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError('CSV rows cannot be empty')
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Scan the oracle economic upper bound across markout '
            'horizons on development data.'
        )
    )
    parser.add_argument(
        '--target-symbols',
        nargs='+',
        default=list(coupled.TARGET_SYMBOLS),
    )
    parser.add_argument(
        '--scan-start',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--scan-end',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--horizons-seconds',
        nargs='+',
        type=parse_positive_int,
        default=list(DEFAULT_HORIZONS_SECONDS),
    )
    parser.add_argument(
        '--notional-budget-fractions',
        nargs='+',
        type=parse_fraction,
        default=list(DEFAULT_NOTIONAL_BUDGETS),
    )
    parser.add_argument(
        '--scenario',
        type=parse_scenario,
        default=parse_scenario('base:0.50:0.25:0.50'),
    )
    parser.add_argument(
        '--risk-penalty',
        type=parse_non_negative_float,
        default=0.50,
    )
    parser.add_argument(
        '--minimum-positive-day-fraction',
        type=parse_fraction,
        default=5.0 / 7.0,
    )
    parser.add_argument(
        '--bootstrap-samples',
        type=parse_positive_int,
        default=5000,
    )
    parser.add_argument('--output-json', required=True)
    parser.add_argument('--output-csv', required=True)
    arguments = parser.parse_args()

    scan_dates = coupled.date_range(
        arguments.scan_start,
        arguments.scan_end,
    )
    target_symbols = tuple(
        dict.fromkeys(arguments.target_symbols)
    )
    invalid_targets = [
        symbol for symbol in target_symbols
        if symbol not in coupled.TARGET_SYMBOLS
    ]
    if invalid_targets:
        raise ValueError(
            f'''unsupported target symbols: {invalid_targets}'''
        )

    horizons = tuple(
        sorted(set(arguments.horizons_seconds))
    )
    budgets = tuple(
        sorted(set(arguments.notional_budget_fractions))
    )
    scenario: OracleScenario = arguments.scenario

    clickhouse = coupled.create_client()

    daily_store: dict[
        str,
        dict[int, dict[float, list[dict[str, Any]]]],
    ] = {
        symbol: {
            horizon: {budget: [] for budget in budgets}
            for horizon in horizons
        }
        for symbol in target_symbols
    }
    markout_store: dict[str, dict[int, list[np.ndarray]]] = {
        symbol: {horizon: [] for horizon in horizons}
        for symbol in target_symbols
    }
    notional_store: dict[str, dict[int, list[np.ndarray]]] = {
        symbol: {horizon: [] for horizon in horizons}
        for symbol in target_symbols
    }

    for trade_date in scan_dates:
        print(f'''Loading oracle day {trade_date}''', flush=True)
        day = coupled.load_market_day(clickhouse, trade_date)
        second_notional = load_second_notional(
            clickhouse,
            trade_date,
        )

        for target_symbol in target_symbols:
            for horizon in horizons:
                data = build_oracle_day_data(
                    day,
                    second_notional,
                    target_symbol=target_symbol,
                    horizon_seconds=horizon,
                )
                markout_store[target_symbol][horizon].append(
                    data.markout_bps.astype(np.float32)
                )
                notional_store[target_symbol][horizon].append(
                    data.notional_usdt.astype(np.float32)
                )

                distribution = distribution_metrics(
                    data,
                    break_even_markout_bps=(
                        scenario.break_even_markout_bps
                    ),
                )
                metrics_by_budget = oracle_metrics_for_budgets(
                    data,
                    scenario=scenario,
                    budget_fractions=budgets,
                )

                for budget, metrics in metrics_by_budget.items():
                    daily_store[target_symbol][horizon][budget].append(
                        {
                            'date': trade_date.isoformat(),
                            'distribution': asdict(distribution),
                            'metrics': asdict(metrics),
                        }
                    )

    output: dict[str, Any] = {
        'configuration': {
            'scan_dates': [
                value.isoformat() for value in scan_dates
            ],
            'target_symbols': list(target_symbols),
            'horizons_seconds': list(horizons),
            'notional_budget_fractions': list(budgets),
            'scenario': asdict(scenario),
            'protection_fraction': scenario.protection_fraction,
            'break_even_markout_bps': (
                scenario.break_even_markout_bps
            ),
            'oracle_definition': (
                'uses realized future markout and is an unattainable '
                'upper bound, not a deployable forecast'
            ),
            'selection_rule': (
                'select realized positive net bps under an exact '
                'fractional daily notional budget'
            ),
            'markout_definition': (
                'sign(current second order flow) * '
                '(future VWAP - current VWAP) / current VWAP * 10000'
            ),
            'cross_day_targets': False,
            'risk_penalty': arguments.risk_penalty,
            'minimum_positive_day_fraction': (
                arguments.minimum_positive_day_fraction
            ),
        },
        'targets': {},
    }
    csv_rows: list[dict[str, Any]] = []

    for target_symbol in target_symbols:
        target_candidates: list[dict[str, Any]] = []
        target_horizons: dict[str, Any] = {}

        for horizon in horizons:
            distribution = pooled_distribution(
                markout_store[target_symbol][horizon],
                notional_store[target_symbol][horizon],
                break_even_markout_bps=(
                    scenario.break_even_markout_bps
                ),
            )
            budget_payload: dict[str, Any] = {}

            for budget in budgets:
                daily_payload = daily_store[
                    target_symbol
                ][horizon][budget]
                daily_metrics = [
                    OracleMetrics(**item['metrics'])
                    for item in daily_payload
                ]
                aggregate = aggregate_oracle_metrics(
                    daily_metrics,
                    scenario=scenario,
                )
                stability = stability_metrics(
                    daily_metrics,
                    risk_penalty=arguments.risk_penalty,
                    minimum_positive_day_fraction=(
                        arguments.minimum_positive_day_fraction
                    ),
                    bootstrap_samples=arguments.bootstrap_samples,
                    seed=(
                        coupled.SEED
                        + coupled.SYMBOLS.index(target_symbol) * 100_000
                        + horizon * 10
                        + int(budget * 100_000)
                    ),
                )
                candidate = _candidate_record(
                    target_symbol=target_symbol,
                    horizon_seconds=horizon,
                    budget_fraction=budget,
                    aggregate=aggregate,
                    stability=stability,
                    distribution=distribution,
                )
                target_candidates.append(candidate)
                csv_rows.append(candidate)

                budget_payload[f'''{budget:.6f}'''] = {
                    'notional_budget_fraction': budget,
                    'daily': daily_payload,
                    'aggregate': asdict(aggregate),
                    'stability': asdict(stability),
                }

            best_for_horizon = max(
                (
                    item for item in target_candidates
                    if item['horizon_seconds'] == horizon
                ),
                key=lambda item: (
                    item['robust_score'],
                    item['mean_daily_net_value_per_million_usdt'],
                ),
            )

            print(
                f'''{target_symbol} H={horizon:4d}s '''
                f'''P(markout>{scenario.break_even_markout_bps:.2f}bps)='''
                f'''{distribution.above_break_even_event_fraction:.4%} '''
                f'''best_budget='''
                f'''{best_for_horizon['notional_budget_fraction']:.1%} '''
                f'''oracle_mean='''
                f'''{best_for_horizon['mean_daily_net_value_per_million_usdt']:+.4f} '''
                f'''CI=[{best_for_horizon['bootstrap_ci_lower']:+.4f},'''
                f'''{best_for_horizon['bootstrap_ci_upper']:+.4f}] '''
                f'''positive_days='''
                f'''{best_for_horizon['positive_day_fraction']:.2%}''',
                flush=True,
            )

            target_horizons[str(horizon)] = {
                'horizon_seconds': horizon,
                'label_overlap_note': (
                    'adjacent labels overlap when horizon_seconds > 1; '
                    'day-cluster bootstrap is used for uncertainty'
                ),
                'pooled_distribution': asdict(distribution),
                'budgets': budget_payload,
            }

        recommendations = select_recommendations(
            target_candidates
        )
        output['targets'][target_symbol] = {
            'horizons': target_horizons,
            'recommendations': recommendations,
            'candidate_ranking': sorted(
                target_candidates,
                key=lambda item: (
                    item['strictly_feasible'],
                    item['robust_score'],
                ),
                reverse=True,
            ),
        }

        print(
            f'''{target_symbol}: {recommendations['status']}''',
            flush=True,
        )
        if recommendations['capital_efficient_candidate'] is not None:
            selected = recommendations[
                'capital_efficient_candidate'
            ]
            print(
                f'''{target_symbol}: capital-efficient oracle region '''
                f'''H={selected['horizon_seconds']}s, '''
                f'''budget={selected['notional_budget_fraction']:.1%}, '''
                f'''robust={selected['robust_score']:+.4f} USDT/$1M''',
                flush=True,
            )

    write_json(arguments.output_json, output)
    write_csv(arguments.output_csv, csv_rows)


if __name__ == '__main__':
    main()
