from __future__ import annotations

import argparse
import gc
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)

from revolut_app.real_market.experiments import coupled_rg_final as coupled


DEFAULT_HORIZONS_SECONDS = (120, 300, 600)
DEFAULT_NOTIONAL_BUDGETS = (0.01, 0.02, 0.05, 0.10)
DEFAULT_MIN_NET_MARGINS_BPS = (0.0, 0.05, 0.10)
DEFAULT_MIN_BREAK_EVEN_PROBABILITIES = (0.0, 0.40, 0.50, 0.60)
DEFAULT_PREDICTION_MULTIPLIERS = (1.0, 1.25, 1.50)
DEFAULT_MODEL_PRESETS = ('compact', 'medium')

RETURN_LOOKBACKS_SECONDS = (5, 10, 30, 60, 120, 300, 600)
VOLATILITY_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)
FLOW_WINDOWS_SECONDS = (10, 30, 60, 120, 300, 600)

POLICY_NAMES = (
    'no_action',
    'probability_budget',
    'direct_economic',
    'hurdle_economic',
    'oracle_upper_bound',
)


@dataclass(frozen=True)
class EconomicScenario:
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
class HurdleDayDataset:
    trade_date: date
    seconds: np.ndarray
    features: np.ndarray
    feature_names: tuple[str, ...]
    markout_bps: np.ndarray
    positive_labels: np.ndarray
    break_even_labels: np.ndarray
    notional_usdt: np.ndarray
    adverse_loss_usdt: np.ndarray


@dataclass(frozen=True)
class ModelSpec:
    preset: str
    learning_rate: float
    max_iter: int
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    target_clip_bps: float
    notional_weight_power: float

    @property
    def model_id(self):
        return (
            f'''{self.preset}|leaf={self.max_leaf_nodes}|'''
            f'''minleaf={self.min_samples_leaf}|'''
            f'''iter={self.max_iter}|clip={self.target_clip_bps:g}|'''
            f'''weight={self.notional_weight_power:g}'''
        )


@dataclass(frozen=True)
class PolicySpec:
    notional_budget_fraction: float
    min_expected_net_margin_bps: float
    min_break_even_probability: float
    prediction_multiplier: float

    @property
    def policy_id(self):
        return (
            f'''budget={self.notional_budget_fraction:g}|'''
            f'''margin={self.min_expected_net_margin_bps:g}|'''
            f'''pbe={self.min_break_even_probability:g}|'''
            f'''mult={self.prediction_multiplier:g}'''
        )


@dataclass
class HurdleState:
    spec: ModelSpec
    positive_classifier: HistGradientBoostingClassifier
    break_even_classifier: HistGradientBoostingClassifier
    severity_regressor: HistGradientBoostingRegressor
    direct_regressor: HistGradientBoostingRegressor
    notional_scale: float


@dataclass(frozen=True)
class PredictionBundle:
    probability_positive: np.ndarray
    probability_break_even: np.ndarray
    conditional_positive_markout_bps: np.ndarray
    expected_positive_markout_bps: np.ndarray
    direct_expected_positive_markout_bps: np.ndarray


@dataclass(frozen=True)
class PolicyMetrics:
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
class CandidateSummary:
    horizon_seconds: int
    model_spec: ModelSpec
    policy_spec: PolicySpec
    mean_daily_net_value_per_million_usdt: float
    median_daily_net_value_per_million_usdt: float
    std_daily_net_value_per_million_usdt: float
    worst_day_net_value_per_million_usdt: float
    positive_day_fraction: float
    robust_score: float
    accepted: bool


def parse_scenario(value: str):
    parts = value.split(':')
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            'scenario must be '
            'NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS'
        )
    name, mitigation, internalization, cost = parts
    try:
        return EconomicScenario(
            name=name,
            mitigation_efficiency=float(mitigation),
            internalization_rate=float(internalization),
            action_cost_bps=float(cost),
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_positive_int(value: str):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('value must be positive')
    return result


def parse_fraction(value: str):
    result = float(value)
    if not 0.0 < result <= 1.0:
        raise argparse.ArgumentTypeError('fraction must be in (0, 1]')
    return result


def parse_probability(value: str):
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise argparse.ArgumentTypeError('probability must be in [0, 1]')
    return result


def parse_non_negative_float(value: str):
    result = float(value)
    if result < 0.0:
        raise argparse.ArgumentTypeError('value cannot be negative')
    return result


def parse_positive_float(value: str):
    result = float(value)
    if result <= 0.0:
        raise argparse.ArgumentTypeError('value must be positive')
    return result


def model_spec_from_preset(name: str):
    if name == 'compact':
        return ModelSpec(
            preset=name,
            learning_rate=0.06,
            max_iter=120,
            max_leaf_nodes=15,
            min_samples_leaf=100,
            l2_regularization=1.0,
            target_clip_bps=50.0,
            notional_weight_power=0.25,
        )
    if name == 'medium':
        return ModelSpec(
            preset=name,
            learning_rate=0.05,
            max_iter=160,
            max_leaf_nodes=31,
            min_samples_leaf=60,
            l2_regularization=1.0,
            target_clip_bps=100.0,
            notional_weight_power=0.25,
        )
    raise ValueError(f'''unknown model preset: {name}''')


def build_model_specs(presets: Iterable[str]):
    unique = tuple(dict.fromkeys(presets))
    if not unique:
        raise ValueError('at least one model preset is required')
    return tuple(model_spec_from_preset(name) for name in unique)


def build_policy_specs(
    budgets: Iterable[float],
    margins: Iterable[float],
    probabilities: Iterable[float],
    multipliers: Iterable[float],
):
    specs = tuple(
        PolicySpec(
            notional_budget_fraction=float(budget),
            min_expected_net_margin_bps=float(margin),
            min_break_even_probability=float(probability),
            prediction_multiplier=float(multiplier),
        )
        for budget in sorted(set(budgets))
        for margin in sorted(set(margins))
        for probability in sorted(set(probabilities))
        for multiplier in sorted(set(multipliers))
    )
    if not specs:
        raise ValueError('policy grid cannot be empty')
    return specs


def forward_fill_prices(vwap: np.ndarray):
    if vwap.ndim != 2:
        raise ValueError('vwap must have shape (time, symbols)')
    count, components = vwap.shape
    output = np.full((count, components), np.nan, dtype=np.float64)

    for component in range(components):
        values = vwap[:, component]
        valid = np.isfinite(values) & (values > 0.0)
        if not np.any(valid):
            continue
        source_index = np.where(
            valid,
            np.arange(count, dtype=np.int64),
            -1,
        )
        np.maximum.accumulate(source_index, out=source_index)
        fillable = source_index >= 0
        output[fillable, component] = values[
            source_index[fillable]
        ]
    return output


def rolling_sum(values: np.ndarray, window: int):
    if values.ndim != 2:
        raise ValueError('values must have shape (time, columns)')
    if window <= 0:
        raise ValueError('window must be positive')

    count, columns = values.shape
    output = np.full((count, columns), np.nan, dtype=np.float64)
    if window > count:
        return output

    cumulative = np.vstack(
        (
            np.zeros((1, columns), dtype=np.float64),
            np.cumsum(values, axis=0, dtype=np.float64),
        )
    )
    output[window - 1 :] = (
        cumulative[window:] - cumulative[:-window]
    )
    return output


def rolling_mean(values: np.ndarray, window: int):
    return rolling_sum(values, window) / float(window)


def rolling_std(values: np.ndarray, window: int):
    if values.ndim != 2:
        raise ValueError('values must have shape (time, columns)')
    if window <= 0:
        raise ValueError('window must be positive')

    mean = rolling_mean(values, window)
    mean_square = rolling_mean(values * values, window)
    variance = np.maximum(mean_square - mean * mean, 0.0)
    return np.sqrt(variance)


def _append_columns(
    columns: list[np.ndarray],
    names: list[str],
    values: np.ndarray,
    value_names: Iterable[str],
):
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2:
        raise ValueError('feature values must be one- or two-dimensional')
    value_names_tuple = tuple(value_names)
    if values.shape[1] != len(value_names_tuple):
        raise ValueError('feature names and columns differ')
    for index, name in enumerate(value_names_tuple):
        columns.append(values[:, index].astype(np.float32, copy=False))
        names.append(name)


def build_hurdle_day_dataset(
    day: coupled.MarketDay,
    *,
    target_symbol: str,
    horizon_seconds: int,
    decision_stride_seconds: int,
    scenario: EconomicScenario,
):
    if target_symbol not in coupled.TARGET_SYMBOLS:
        raise ValueError(f'''unsupported target symbol: {target_symbol}''')
    if horizon_seconds <= 0:
        raise ValueError('horizon_seconds must be positive')
    if decision_stride_seconds <= 0:
        raise ValueError('decision_stride_seconds must be positive')

    target_index = coupled.SYMBOLS.index(target_symbol)
    seconds = np.arange(coupled.SECONDS_PER_DAY, dtype=np.int64)
    future_seconds = seconds + horizon_seconds

    maximum_history = max(
        max(coupled.SCALES_SECONDS),
        max(RETURN_LOOKBACKS_SECONDS),
        max(VOLATILITY_WINDOWS_SECONDS),
        max(FLOW_WINDOWS_SECONDS),
    )

    side = np.sign(day.phi[:, target_index])
    current_vwap = day.vwap[:, target_index]
    safe_future = np.minimum(
        future_seconds,
        coupled.SECONDS_PER_DAY - 1,
    )
    future_vwap = day.vwap[safe_future, target_index]

    total_quote = np.expm1(
        day.log_volume.astype(np.float64)
    )
    target_notional = total_quote[:, target_index]

    valid = (
        (seconds >= maximum_history)
        & (future_seconds < coupled.SECONDS_PER_DAY)
        & (seconds % decision_stride_seconds == 0)
        & day.active[:, target_index]
        & (side != 0)
        & np.isfinite(current_vwap)
        & np.isfinite(future_vwap)
        & (current_vwap > 0.0)
        & (future_vwap > 0.0)
        & np.isfinite(target_notional)
        & (target_notional > 0.0)
    )
    indices = np.flatnonzero(valid)
    if indices.size == 0:
        raise ValueError(
            f'''no valid observations for {target_symbol}, '''
            f'''{day.trade_date}, H={horizon_seconds}'''
        )

    side_valid = side[indices].astype(np.float64, copy=False)
    field = day.coarse_phi[indices].astype(np.float64, copy=False)
    aligned_field = field * side_valid[:, None, None]
    absolute_field = np.abs(field)
    q2 = field * field
    q4 = q2 * q2

    columns: list[np.ndarray] = []
    names: list[str] = []

    _append_columns(
        columns,
        names,
        day.log_volume[indices],
        (f'''log_volume[{symbol}]''' for symbol in coupled.SYMBOLS),
    )

    for scale_index, scale in enumerate(coupled.SCALES_SECONDS):
        for component, symbol in enumerate(coupled.SYMBOLS):
            _append_columns(
                columns,
                names,
                np.column_stack(
                    (
                        aligned_field[:, scale_index, component],
                        absolute_field[:, scale_index, component],
                        q2[:, scale_index, component],
                        q4[:, scale_index, component],
                    )
                ),
                (
                    f'''h[{symbol},B={scale}]''',
                    f'''abs_phi[{symbol},B={scale}]''',
                    f'''phi2[{symbol},B={scale}]''',
                    f'''phi4[{symbol},B={scale}]''',
                ),
            )

    filled_price = forward_fill_prices(day.vwap)
    log_price = np.log(filled_price)
    one_second_return_bps = np.zeros_like(log_price)
    one_second_return_bps[1:] = (
        log_price[1:] - log_price[:-1]
    ) * 10_000.0
    one_second_return_bps[~np.isfinite(one_second_return_bps)] = 0.0

    for lookback in RETURN_LOOKBACKS_SECONDS:
        lagged_return = (
            log_price[indices]
            - log_price[indices - lookback]
        ) * 10_000.0
        aligned_return = lagged_return * side_valid[:, None]
        _append_columns(
            columns,
            names,
            aligned_return,
            (
                f'''aligned_return_bps[{symbol},L={lookback}]'''
                for symbol in coupled.SYMBOLS
            ),
        )
        _append_columns(
            columns,
            names,
            np.abs(lagged_return),
            (
                f'''abs_return_bps[{symbol},L={lookback}]'''
                for symbol in coupled.SYMBOLS
            ),
        )

    for window in VOLATILITY_WINDOWS_SECONDS:
        volatility = rolling_std(
            one_second_return_bps,
            window,
        )[indices]
        _append_columns(
            columns,
            names,
            volatility,
            (
                f'''realized_vol_bps[{symbol},W={window}]'''
                for symbol in coupled.SYMBOLS
            ),
        )

    signed_quote = day.phi.astype(np.float64) * total_quote
    for window in FLOW_WINDOWS_SECONDS:
        signed_sum = rolling_sum(signed_quote, window)[indices]
        total_sum = rolling_sum(total_quote, window)[indices]
        imbalance = np.divide(
            signed_sum,
            total_sum,
            out=np.zeros_like(signed_sum),
            where=total_sum > 0.0,
        )
        aligned_imbalance = imbalance * side_valid[:, None]
        _append_columns(
            columns,
            names,
            aligned_imbalance,
            (
                f'''aligned_volume_imbalance[{symbol},W={window}]'''
                for symbol in coupled.SYMBOLS
            ),
        )
        _append_columns(
            columns,
            names,
            np.log1p(total_sum),
            (
                f'''log_rolling_quote[{symbol},W={window}]'''
                for symbol in coupled.SYMBOLS
            ),
        )

    scale_index = {
        scale: index
        for index, scale in enumerate(coupled.SCALES_SECONDS)
    }
    for short_scale, long_scale in ((8, 64), (16, 64), (32, 64)):
        acceleration = (
            field[:, scale_index[short_scale], :]
            - field[:, scale_index[long_scale], :]
        ) * side_valid[:, None]
        _append_columns(
            columns,
            names,
            acceleration,
            (
                f'''aligned_flow_acceleration[{symbol},'''
                f'''{short_scale}-{long_scale}]'''
                for symbol in coupled.SYMBOLS
            ),
        )

    btc_index = coupled.SYMBOLS.index('BTCUSDT')
    eth_index = coupled.SYMBOLS.index('ETHUSDT')
    cross_index = coupled.SYMBOLS.index('ETHBTC')
    triangular_residual = (
        log_price[:, eth_index]
        - log_price[:, cross_index]
        - log_price[:, btc_index]
    )
    for lookback in RETURN_LOOKBACKS_SECONDS:
        residual_change = (
            triangular_residual[indices]
            - triangular_residual[indices - lookback]
        ) * 10_000.0
        _append_columns(
            columns,
            names,
            np.column_stack(
                (
                    residual_change,
                    residual_change * side_valid,
                )
            ),
            (
                f'''triangular_residual_change_bps[L={lookback}]''',
                f'''aligned_triangular_residual_change_bps[L={lookback}]''',
            ),
        )

    seconds_in_day = indices.astype(np.float64)
    angle = 2.0 * math.pi * seconds_in_day / coupled.SECONDS_PER_DAY
    _append_columns(
        columns,
        names,
        np.column_stack((np.sin(angle), np.cos(angle))),
        ('time_of_day_sin', 'time_of_day_cos'),
    )

    feature_matrix = np.column_stack(columns).astype(
        np.float32,
        copy=False,
    )
    finite_rows = np.all(np.isfinite(feature_matrix), axis=1)
    if not np.all(finite_rows):
        indices = indices[finite_rows]
        side_valid = side_valid[finite_rows]
        feature_matrix = feature_matrix[finite_rows]

    notional = target_notional[indices].astype(np.float64, copy=False)
    markout = (
        side_valid
        * (
            day.vwap[indices + horizon_seconds, target_index]
            - day.vwap[indices, target_index]
        )
        / day.vwap[indices, target_index]
        * 10_000.0
    )
    if np.any(~np.isfinite(markout)):
        raise ValueError('non-finite markout after filtering')

    positive = (markout > 0.0).astype(np.uint8)
    break_even = (
        markout > scenario.break_even_markout_bps
    ).astype(np.uint8)
    adverse_loss = (
        notional
        * np.maximum(markout, 0.0)
        / 10_000.0
    )

    return HurdleDayDataset(
        trade_date=day.trade_date,
        seconds=indices,
        features=feature_matrix,
        feature_names=tuple(names),
        markout_bps=markout.astype(np.float64, copy=False),
        positive_labels=positive,
        break_even_labels=break_even,
        notional_usdt=notional,
        adverse_loss_usdt=adverse_loss,
    )


def concatenate_datasets(
    datasets: list[HurdleDayDataset],
):
    if not datasets:
        raise ValueError('datasets cannot be empty')
    feature_names = datasets[0].feature_names
    if any(item.feature_names != feature_names for item in datasets):
        raise ValueError('feature schemas differ')

    return HurdleDayDataset(
        trade_date=datasets[-1].trade_date,
        seconds=np.concatenate([item.seconds for item in datasets]),
        features=np.concatenate(
            [item.features for item in datasets],
            axis=0,
        ).astype(np.float32, copy=False),
        feature_names=feature_names,
        markout_bps=np.concatenate(
            [item.markout_bps for item in datasets]
        ),
        positive_labels=np.concatenate(
            [item.positive_labels for item in datasets]
        ),
        break_even_labels=np.concatenate(
            [item.break_even_labels for item in datasets]
        ),
        notional_usdt=np.concatenate(
            [item.notional_usdt for item in datasets]
        ),
        adverse_loss_usdt=np.concatenate(
            [item.adverse_loss_usdt for item in datasets]
        ),
    )


def build_datasets_for_dates(
    market_cache: dict[date, coupled.MarketDay],
    dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
    decision_stride_seconds: int,
    scenario: EconomicScenario,
):
    output: dict[date, HurdleDayDataset] = {}
    for trade_date in dates:
        print(
            f'''{target_symbol} H={horizon_seconds}s: '''
            f'''building {trade_date}''',
            flush=True,
        )
        output[trade_date] = build_hurdle_day_dataset(
            market_cache[trade_date],
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
            decision_stride_seconds=decision_stride_seconds,
            scenario=scenario,
        )
    return output


def notional_sample_weights(
    notional_usdt: np.ndarray,
    *,
    scale: float,
    power: float,
):
    if scale <= 0.0:
        raise ValueError('notional scale must be positive')
    if power < 0.0:
        raise ValueError('notional weight power cannot be negative')
    if power == 0.0:
        return np.ones(notional_usdt.size, dtype=np.float64)
    raw = np.power(
        np.maximum(notional_usdt / scale, 1e-12),
        power,
    )
    return np.clip(raw, 0.25, 4.0).astype(np.float64)


def _new_classifier(
    spec: ModelSpec,
    *,
    seed_offset: int,
):
    return HistGradientBoostingClassifier(
        loss='log_loss',
        learning_rate=spec.learning_rate,
        max_iter=spec.max_iter,
        max_leaf_nodes=spec.max_leaf_nodes,
        min_samples_leaf=spec.min_samples_leaf,
        l2_regularization=spec.l2_regularization,
        max_bins=63,
        early_stopping=False,
        random_state=coupled.SEED + seed_offset,
    )


def _new_regressor(
    spec: ModelSpec,
    *,
    seed_offset: int,
):
    return HistGradientBoostingRegressor(
        loss='squared_error',
        learning_rate=spec.learning_rate,
        max_iter=spec.max_iter,
        max_leaf_nodes=spec.max_leaf_nodes,
        min_samples_leaf=spec.min_samples_leaf,
        l2_regularization=spec.l2_regularization,
        max_bins=63,
        early_stopping=False,
        random_state=coupled.SEED + seed_offset,
    )


def fit_hurdle_state(
    training: HurdleDayDataset,
    spec: ModelSpec,
):
    if np.unique(training.positive_labels).size != 2:
        raise ValueError('positive classifier requires both classes')
    if np.unique(training.break_even_labels).size != 2:
        raise ValueError('break-even classifier requires both classes')

    positive_mask = training.positive_labels == 1
    if int(np.sum(positive_mask)) < spec.min_samples_leaf * 2:
        raise ValueError('too few positive observations for severity model')

    notional_scale = float(np.median(training.notional_usdt))
    if not np.isfinite(notional_scale) or notional_scale <= 0.0:
        raise ValueError('invalid notional scale')

    weights = notional_sample_weights(
        training.notional_usdt,
        scale=notional_scale,
        power=spec.notional_weight_power,
    )

    positive_classifier = _new_classifier(spec, seed_offset=11)
    break_even_classifier = _new_classifier(spec, seed_offset=23)
    severity_regressor = _new_regressor(spec, seed_offset=37)
    direct_regressor = _new_regressor(spec, seed_offset=41)

    positive_classifier.fit(
        training.features,
        training.positive_labels,
        sample_weight=weights,
    )
    break_even_classifier.fit(
        training.features,
        training.break_even_labels,
        sample_weight=weights,
    )

    positive_target = np.minimum(
        training.markout_bps[positive_mask],
        spec.target_clip_bps,
    )
    severity_regressor.fit(
        training.features[positive_mask],
        np.log1p(positive_target),
        sample_weight=weights[positive_mask],
    )

    direct_target = np.minimum(
        np.maximum(training.markout_bps, 0.0),
        spec.target_clip_bps,
    )
    direct_regressor.fit(
        training.features,
        np.log1p(direct_target),
        sample_weight=weights,
    )

    return HurdleState(
        spec=spec,
        positive_classifier=positive_classifier,
        break_even_classifier=break_even_classifier,
        severity_regressor=severity_regressor,
        direct_regressor=direct_regressor,
        notional_scale=notional_scale,
    )


def predict_hurdle(
    state: HurdleState,
    dataset: HurdleDayDataset,
):
    probability_positive = state.positive_classifier.predict_proba(
        dataset.features
    )[:, 1]
    probability_break_even = (
        state.break_even_classifier.predict_proba(
            dataset.features
        )[:, 1]
    )

    conditional_positive = np.expm1(
        state.severity_regressor.predict(dataset.features)
    )
    conditional_positive = np.clip(
        conditional_positive,
        0.0,
        state.spec.target_clip_bps,
    )

    direct = np.expm1(
        state.direct_regressor.predict(dataset.features)
    )
    direct = np.clip(
        direct,
        0.0,
        state.spec.target_clip_bps,
    )

    expected_positive = (
        probability_positive * conditional_positive
    )

    return PredictionBundle(
        probability_positive=probability_positive.astype(
            np.float64,
            copy=False,
        ),
        probability_break_even=probability_break_even.astype(
            np.float64,
            copy=False,
        ),
        conditional_positive_markout_bps=conditional_positive.astype(
            np.float64,
            copy=False,
        ),
        expected_positive_markout_bps=expected_positive.astype(
            np.float64,
            copy=False,
        ),
        direct_expected_positive_markout_bps=direct.astype(
            np.float64,
            copy=False,
        ),
    )


def fractional_notional_allocation(
    priority_score: np.ndarray,
    notional_usdt: np.ndarray,
    *,
    budget_fraction: float,
    eligible: np.ndarray | None = None,
):
    if priority_score.shape != notional_usdt.shape:
        raise ValueError('score and notional shapes differ')
    if priority_score.ndim != 1 or priority_score.size == 0:
        raise ValueError('allocation arrays must be non-empty')
    if np.any(~np.isfinite(priority_score)):
        raise ValueError('priority contains non-finite values')
    if np.any(~np.isfinite(notional_usdt)) or np.any(notional_usdt <= 0.0):
        raise ValueError('notional must be finite and positive')
    if not 0.0 <= budget_fraction <= 1.0:
        raise ValueError('budget_fraction must be in [0, 1]')

    action = np.zeros(priority_score.size, dtype=np.float64)
    if budget_fraction == 0.0:
        return action

    if eligible is None:
        eligible = np.ones(priority_score.size, dtype=bool)
    if eligible.shape != priority_score.shape:
        raise ValueError('eligible mask shape differs')

    candidates = np.flatnonzero(eligible)
    if candidates.size == 0:
        return action

    order = candidates[
        np.argsort(
            priority_score[candidates],
            kind='stable',
        )[::-1]
    ]
    remaining = (
        float(np.sum(notional_usdt, dtype=np.float64))
        * budget_fraction
    )

    for index in order:
        if remaining <= 0.0:
            break
        amount = float(notional_usdt[index])
        fraction = min(1.0, remaining / amount)
        action[index] = fraction
        remaining -= fraction * amount

    return action


def predicted_net_bps(
    predicted_positive_markout_bps: np.ndarray,
    *,
    scenario: EconomicScenario,
    multiplier: float,
):
    if multiplier <= 0.0:
        raise ValueError('multiplier must be positive')
    return (
        scenario.protection_fraction
        * multiplier
        * predicted_positive_markout_bps
        - scenario.action_cost_bps
    )


def hurdle_action_fraction(
    predictions: PredictionBundle,
    notional_usdt: np.ndarray,
    *,
    scenario: EconomicScenario,
    policy: PolicySpec,
):
    net_bps = predicted_net_bps(
        predictions.expected_positive_markout_bps,
        scenario=scenario,
        multiplier=policy.prediction_multiplier,
    )
    eligible = (
        (net_bps >= policy.min_expected_net_margin_bps)
        & (
            predictions.probability_break_even
            >= policy.min_break_even_probability
        )
    )
    return (
        fractional_notional_allocation(
            net_bps,
            notional_usdt,
            budget_fraction=policy.notional_budget_fraction,
            eligible=eligible,
        ),
        net_bps,
    )


def direct_action_fraction(
    predictions: PredictionBundle,
    notional_usdt: np.ndarray,
    *,
    scenario: EconomicScenario,
    policy: PolicySpec,
):
    net_bps = predicted_net_bps(
        predictions.direct_expected_positive_markout_bps,
        scenario=scenario,
        multiplier=policy.prediction_multiplier,
    )
    eligible = (
        (net_bps >= policy.min_expected_net_margin_bps)
        & (
            predictions.probability_break_even
            >= policy.min_break_even_probability
        )
    )
    return (
        fractional_notional_allocation(
            net_bps,
            notional_usdt,
            budget_fraction=policy.notional_budget_fraction,
            eligible=eligible,
        ),
        net_bps,
    )


def probability_action_fraction(
    predictions: PredictionBundle,
    notional_usdt: np.ndarray,
    *,
    policy: PolicySpec,
):
    eligible = (
        predictions.probability_break_even
        >= policy.min_break_even_probability
    )
    return fractional_notional_allocation(
        predictions.probability_break_even,
        notional_usdt,
        budget_fraction=policy.notional_budget_fraction,
        eligible=eligible,
    )


def oracle_action_fraction(
    dataset: HurdleDayDataset,
    *,
    scenario: EconomicScenario,
    policy: PolicySpec,
):
    realized_net = (
        scenario.protection_fraction
        * np.maximum(dataset.markout_bps, 0.0)
        - scenario.action_cost_bps
    )
    return fractional_notional_allocation(
        realized_net,
        dataset.notional_usdt,
        budget_fraction=policy.notional_budget_fraction,
        eligible=realized_net > 0.0,
    )


def calculate_policy_metrics(
    *,
    action_fraction: np.ndarray,
    dataset: HurdleDayDataset,
    scenario: EconomicScenario,
):
    if not (
        action_fraction.shape
        == dataset.notional_usdt.shape
        == dataset.adverse_loss_usdt.shape
    ):
        raise ValueError('policy metric array shapes differ')
    if np.any((action_fraction < 0.0) | (action_fraction > 1.0)):
        raise ValueError('action_fraction must be in [0, 1]')

    acted = action_fraction > 0.0
    observations = int(action_fraction.size)
    acted_observations = int(np.sum(acted))

    total_notional = float(
        np.sum(dataset.notional_usdt, dtype=np.float64)
    )
    acted_notional = float(
        np.sum(
            action_fraction * dataset.notional_usdt,
            dtype=np.float64,
        )
    )
    total_loss = float(
        np.sum(dataset.adverse_loss_usdt, dtype=np.float64)
    )
    captured_loss = float(
        np.sum(
            action_fraction * dataset.adverse_loss_usdt,
            dtype=np.float64,
        )
    )

    acted_event_fraction = acted_observations / observations
    mean_action_fraction = (
        float(np.mean(action_fraction[acted]))
        if acted_observations > 0
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

    gross_value = scenario.protection_fraction * captured_loss
    action_cost = (
        acted_notional
        * scenario.action_cost_bps
        / 10_000.0
    )
    net_value = gross_value - action_cost

    gross_per_million = (
        gross_value / total_notional * 1_000_000.0
        if total_notional > 0.0
        else 0.0
    )
    net_per_million = (
        net_value / total_notional * 1_000_000.0
        if total_notional > 0.0
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

    return PolicyMetrics(
        observations=observations,
        acted_observations=acted_observations,
        acted_event_fraction=float(acted_event_fraction),
        mean_action_fraction_on_acted_events=mean_action_fraction,
        total_notional_usdt=total_notional,
        acted_notional_usdt=acted_notional,
        acted_notional_fraction=float(acted_notional_fraction),
        total_adverse_loss_usdt=total_loss,
        captured_adverse_loss_usdt=captured_loss,
        capture_rate=float(capture_rate),
        risk_concentration=float(risk_concentration),
        gross_protected_value_usdt=float(gross_value),
        action_cost_usdt=float(action_cost),
        net_protected_value_usdt=float(net_value),
        gross_value_per_million_usdt=float(gross_per_million),
        net_value_per_million_usdt=float(net_per_million),
        break_even_action_cost_bps=float(break_even_cost),
        benefit_cost_ratio=float(benefit_cost_ratio),
        profitable=bool(net_value > 0.0),
    )


def aggregate_policy_metrics(
    daily: list[PolicyMetrics],
    *,
    scenario: EconomicScenario,
):
    if not daily:
        raise ValueError('daily metrics cannot be empty')

    observations = sum(item.observations for item in daily)
    acted_observations = sum(
        item.acted_observations for item in daily
    )
    total_notional = sum(
        item.total_notional_usdt for item in daily
    )
    acted_notional = sum(
        item.acted_notional_usdt for item in daily
    )
    total_loss = sum(
        item.total_adverse_loss_usdt for item in daily
    )
    captured_loss = sum(
        item.captured_adverse_loss_usdt for item in daily
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
    weighted_action = sum(
        item.mean_action_fraction_on_acted_events
        * item.acted_observations
        for item in daily
    )
    mean_action_fraction = (
        weighted_action / acted_observations
        if acted_observations > 0
        else 0.0
    )

    return PolicyMetrics(
        observations=observations,
        acted_observations=acted_observations,
        acted_event_fraction=float(acted_event_fraction),
        mean_action_fraction_on_acted_events=float(mean_action_fraction),
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


def summarize_candidate(
    *,
    horizon_seconds: int,
    model_spec: ModelSpec,
    policy_spec: PolicySpec,
    daily_metrics: list[PolicyMetrics],
    risk_penalty: float,
    minimum_positive_day_fraction: float,
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

    accepted = bool(
        mean > 0.0
        and robust_score > 0.0
        and positive_fraction >= minimum_positive_day_fraction
    )
    return CandidateSummary(
        horizon_seconds=horizon_seconds,
        model_spec=model_spec,
        policy_spec=policy_spec,
        mean_daily_net_value_per_million_usdt=mean,
        median_daily_net_value_per_million_usdt=median,
        std_daily_net_value_per_million_usdt=standard_deviation,
        worst_day_net_value_per_million_usdt=worst,
        positive_day_fraction=positive_fraction,
        robust_score=float(robust_score),
        accepted=accepted,
    )


def select_best_candidate(
    candidates: list[CandidateSummary],
):
    accepted = [item for item in candidates if item.accepted]
    if not accepted:
        return None
    return max(
        accepted,
        key=lambda item: (
            item.robust_score,
            item.mean_daily_net_value_per_million_usdt,
            -item.policy_spec.notional_budget_fraction,
            item.policy_spec.min_expected_net_margin_bps,
            item.policy_spec.min_break_even_probability,
        ),
    )


def bootstrap_daily_difference(
    differences: list[float],
    *,
    samples: int,
    seed: int,
):
    values = np.asarray(differences, dtype=np.float64)
    if values.size == 0 or np.any(~np.isfinite(values)):
        raise ValueError('bootstrap input must be finite and non-empty')
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0,
        values.size,
        size=(samples, values.size),
    )
    means = np.mean(values[indices], axis=1)
    return {
        'days': int(values.size),
        'mean': float(np.mean(values)),
        'ci_025': float(np.quantile(means, 0.025)),
        'ci_975': float(np.quantile(means, 0.975)),
        'positive_day_fraction': float(np.mean(values > 0.0)),
    }


def evaluate_predictions(
    *,
    datasets: dict[date, HurdleDayDataset],
    predictions: dict[date, PredictionBundle],
    policy: PolicySpec,
    scenario: EconomicScenario,
    bootstrap_samples: int,
    seed_offset: int,
):
    daily_output: list[dict[str, Any]] = []
    collected: dict[str, list[PolicyMetrics]] = {
        name: [] for name in POLICY_NAMES
    }

    for trade_date, dataset in datasets.items():
        prediction = predictions[trade_date]
        zero_action = np.zeros(
            dataset.notional_usdt.size,
            dtype=np.float64,
        )
        probability_action = probability_action_fraction(
            prediction,
            dataset.notional_usdt,
            policy=policy,
        )
        direct_action, direct_net = direct_action_fraction(
            prediction,
            dataset.notional_usdt,
            scenario=scenario,
            policy=policy,
        )
        hurdle_action, hurdle_net = hurdle_action_fraction(
            prediction,
            dataset.notional_usdt,
            scenario=scenario,
            policy=policy,
        )
        oracle_action = oracle_action_fraction(
            dataset,
            scenario=scenario,
            policy=policy,
        )

        actions = {
            'no_action': zero_action,
            'probability_budget': probability_action,
            'direct_economic': direct_action,
            'hurdle_economic': hurdle_action,
            'oracle_upper_bound': oracle_action,
        }
        metrics = {
            name: calculate_policy_metrics(
                action_fraction=action,
                dataset=dataset,
                scenario=scenario,
            )
            for name, action in actions.items()
        }
        for name, value in metrics.items():
            collected[name].append(value)

        daily_output.append(
            {
                'date': trade_date.isoformat(),
                'policies': {
                    name: asdict(value)
                    for name, value in metrics.items()
                },
                'prediction_diagnostics': {
                    'probability_positive_mean': float(
                        np.mean(prediction.probability_positive)
                    ),
                    'probability_break_even_mean': float(
                        np.mean(prediction.probability_break_even)
                    ),
                    'expected_positive_markout_p95_bps': float(
                        np.quantile(
                            prediction.expected_positive_markout_bps,
                            0.95,
                        )
                    ),
                    'expected_positive_markout_max_bps': float(
                        np.max(
                            prediction.expected_positive_markout_bps
                        )
                    ),
                    'direct_expected_markout_p95_bps': float(
                        np.quantile(
                            prediction.direct_expected_positive_markout_bps,
                            0.95,
                        )
                    ),
                    'hurdle_predicted_net_positive_fraction': float(
                        np.mean(hurdle_net > 0.0)
                    ),
                    'direct_predicted_net_positive_fraction': float(
                        np.mean(direct_net > 0.0)
                    ),
                },
                'comparisons': {
                    'hurdle_minus_no_action': (
                        metrics[
                            'hurdle_economic'
                        ].net_value_per_million_usdt
                    ),
                    'hurdle_minus_probability': (
                        metrics[
                            'hurdle_economic'
                        ].net_value_per_million_usdt
                        - metrics[
                            'probability_budget'
                        ].net_value_per_million_usdt
                    ),
                    'hurdle_minus_direct': (
                        metrics[
                            'hurdle_economic'
                        ].net_value_per_million_usdt
                        - metrics[
                            'direct_economic'
                        ].net_value_per_million_usdt
                    ),
                },
            }
        )

    aggregate = {
        name: asdict(
            aggregate_policy_metrics(values, scenario=scenario)
        )
        for name, values in collected.items()
    }

    oracle_value = aggregate['oracle_upper_bound'][
        'net_value_per_million_usdt'
    ]
    hurdle_value = aggregate['hurdle_economic'][
        'net_value_per_million_usdt'
    ]
    oracle_capture_fraction = (
        hurdle_value / oracle_value
        if oracle_value > 0.0
        else 0.0
    )

    bootstrap: dict[str, Any] = {}
    for comparison in (
        'hurdle_minus_no_action',
        'hurdle_minus_probability',
        'hurdle_minus_direct',
    ):
        bootstrap[comparison] = bootstrap_daily_difference(
            [
                day['comparisons'][comparison]
                for day in daily_output
            ],
            samples=bootstrap_samples,
            seed=(
                coupled.SEED
                + seed_offset
                + len(comparison)
            ),
        )

    return {
        'daily': daily_output,
        'aggregate': aggregate,
        'oracle_capture_fraction': float(oracle_capture_fraction),
        'bootstrap': bootstrap,
    }


def evaluate_candidate_on_days(
    *,
    predictions: dict[date, PredictionBundle],
    datasets: dict[date, HurdleDayDataset],
    policy: PolicySpec,
    scenario: EconomicScenario,
):
    output: list[PolicyMetrics] = []
    for trade_date, dataset in datasets.items():
        action, _ = hurdle_action_fraction(
            predictions[trade_date],
            dataset.notional_usdt,
            scenario=scenario,
            policy=policy,
        )
        output.append(
            calculate_policy_metrics(
                action_fraction=action,
                dataset=dataset,
                scenario=scenario,
            )
        )
    return output


def predictions_for_days(
    state: HurdleState,
    datasets: dict[date, HurdleDayDataset],
):
    return {
        trade_date: predict_hurdle(state, dataset)
        for trade_date, dataset in datasets.items()
    }


def load_market_cache(
    clickhouse: Any,
    dates: list[date],
):
    cache: dict[date, coupled.MarketDay] = {}
    for trade_date in dates:
        print(f'''Loading synchronized day {trade_date}''', flush=True)
        cache[trade_date] = coupled.load_market_day(
            clickhouse,
            trade_date,
        )
    return cache


def write_json(path: str | Path, payload: dict[str, Any]):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.part')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(temporary, output)


def validate_splits(
    train_dates: list[date],
    development_dates: list[date],
    validation_dates: list[date],
    final_dates: list[date],
):
    combined = (
        train_dates
        + development_dates
        + validation_dates
        + final_dates
    )
    if len(set(combined)) != len(combined):
        raise ValueError('temporal splits overlap')
    if not all(
        (train_dates, development_dates, validation_dates, final_dates)
    ):
        raise ValueError('all temporal splits must be non-empty')
    if max(train_dates) >= min(development_dates):
        raise ValueError('development must follow training')
    if max(development_dates) >= min(validation_dates):
        raise ValueError('validation must follow development')
    if max(validation_dates) >= min(final_dates):
        raise ValueError('final must follow validation')


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Train and validate a notional-constrained hurdle economic '
            'policy on RG-noJ and extended market-state features.'
        )
    )
    parser.add_argument(
        '--target-symbols',
        nargs='+',
        default=list(coupled.TARGET_SYMBOLS),
    )
    parser.add_argument(
        '--horizons-seconds',
        nargs='+',
        type=parse_positive_int,
        default=list(DEFAULT_HORIZONS_SECONDS),
    )
    parser.add_argument(
        '--decision-stride-seconds',
        type=parse_positive_int,
        default=10,
    )
    parser.add_argument('--train-start', type=date.fromisoformat, required=True)
    parser.add_argument('--train-end', type=date.fromisoformat, required=True)
    parser.add_argument(
        '--development-start',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--development-end',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--validation-start',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--validation-end',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--final-test-start',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--final-test-end',
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument(
        '--scenario',
        type=parse_scenario,
        default=parse_scenario('base:0.50:0.25:0.50'),
    )
    parser.add_argument(
        '--model-presets',
        nargs='+',
        choices=DEFAULT_MODEL_PRESETS,
        default=list(DEFAULT_MODEL_PRESETS),
    )
    parser.add_argument(
        '--notional-budget-fractions',
        nargs='+',
        type=parse_fraction,
        default=list(DEFAULT_NOTIONAL_BUDGETS),
    )
    parser.add_argument(
        '--minimum-net-margins-bps',
        nargs='+',
        type=parse_non_negative_float,
        default=list(DEFAULT_MIN_NET_MARGINS_BPS),
    )
    parser.add_argument(
        '--minimum-break-even-probabilities',
        nargs='+',
        type=parse_probability,
        default=list(DEFAULT_MIN_BREAK_EVEN_PROBABILITIES),
    )
    parser.add_argument(
        '--prediction-multipliers',
        nargs='+',
        type=parse_positive_float,
        default=list(DEFAULT_PREDICTION_MULTIPLIERS),
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
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()

    train_dates = coupled.date_range(
        arguments.train_start,
        arguments.train_end,
    )
    development_dates = coupled.date_range(
        arguments.development_start,
        arguments.development_end,
    )
    validation_dates = coupled.date_range(
        arguments.validation_start,
        arguments.validation_end,
    )
    final_dates = coupled.date_range(
        arguments.final_test_start,
        arguments.final_test_end,
    )
    validate_splits(
        train_dates,
        development_dates,
        validation_dates,
        final_dates,
    )

    targets = tuple(dict.fromkeys(arguments.target_symbols))
    invalid_targets = [
        symbol for symbol in targets
        if symbol not in coupled.TARGET_SYMBOLS
    ]
    if invalid_targets:
        raise ValueError(
            f'''unsupported target symbols: {invalid_targets}'''
        )

    horizons = tuple(sorted(set(arguments.horizons_seconds)))
    model_specs = build_model_specs(arguments.model_presets)
    policy_specs = build_policy_specs(
        arguments.notional_budget_fractions,
        arguments.minimum_net_margins_bps,
        arguments.minimum_break_even_probabilities,
        arguments.prediction_multipliers,
    )
    scenario: EconomicScenario = arguments.scenario

    all_dates = (
        train_dates
        + development_dates
        + validation_dates
        + final_dates
    )
    clickhouse = coupled.create_client()
    market_cache = load_market_cache(clickhouse, all_dates)

    output: dict[str, Any] = {
        'configuration': {
            'target_symbols': list(targets),
            'horizons_seconds': list(horizons),
            'decision_stride_seconds': (
                arguments.decision_stride_seconds
            ),
            'scenario': asdict(scenario),
            'break_even_markout_bps': (
                scenario.break_even_markout_bps
            ),
            'train_dates': [item.isoformat() for item in train_dates],
            'development_dates': [
                item.isoformat() for item in development_dates
            ],
            'validation_dates': [
                item.isoformat() for item in validation_dates
            ],
            'final_test_dates': [
                item.isoformat() for item in final_dates
            ],
            'model_specs': [asdict(item) for item in model_specs],
            'policy_grid_size': len(policy_specs),
            'risk_penalty': arguments.risk_penalty,
            'minimum_positive_day_fraction': (
                arguments.minimum_positive_day_fraction
            ),
            'selection_protocol': (
                'train models on train; select one policy per horizon '
                'on development; select one horizon on validation; '
                'refit on train+development+validation; evaluate final once'
            ),
            'main_target': (
                'expected positive aggressor-aligned markout in bps'
            ),
            'hurdle_definition': (
                'P(markout>0) * E[markout | markout>0], with an '
                'additional P(markout>break-even) gate'
            ),
            'interpretation': (
                'scenario-adjusted potential protected value; '
                'not realized bank PnL'
            ),
        },
        'targets': {},
    }

    for target_index, target_symbol in enumerate(targets):
        print('=' * 100, flush=True)
        print(f'''TARGET {target_symbol}''', flush=True)

        development_winners: list[CandidateSummary] = []
        development_payload: dict[str, Any] = {}

        for horizon in horizons:
            train_map = build_datasets_for_dates(
                market_cache,
                train_dates,
                target_symbol=target_symbol,
                horizon_seconds=horizon,
                decision_stride_seconds=(
                    arguments.decision_stride_seconds
                ),
                scenario=scenario,
            )
            development_map = build_datasets_for_dates(
                market_cache,
                development_dates,
                target_symbol=target_symbol,
                horizon_seconds=horizon,
                decision_stride_seconds=(
                    arguments.decision_stride_seconds
                ),
                scenario=scenario,
            )
            training = concatenate_datasets(
                [train_map[item] for item in train_dates]
            )

            horizon_candidates: list[CandidateSummary] = []
            for model_spec in model_specs:
                print(
                    f'''{target_symbol} H={horizon}s: '''
                    f'''fitting {model_spec.preset}''',
                    flush=True,
                )
                state = fit_hurdle_state(training, model_spec)
                predictions = predictions_for_days(
                    state,
                    development_map,
                )

                for policy_spec in policy_specs:
                    daily_metrics = evaluate_candidate_on_days(
                        predictions=predictions,
                        datasets=development_map,
                        policy=policy_spec,
                        scenario=scenario,
                    )
                    horizon_candidates.append(
                        summarize_candidate(
                            horizon_seconds=horizon,
                            model_spec=model_spec,
                            policy_spec=policy_spec,
                            daily_metrics=daily_metrics,
                            risk_penalty=arguments.risk_penalty,
                            minimum_positive_day_fraction=(
                                arguments.minimum_positive_day_fraction
                            ),
                        )
                    )

                del state, predictions
                gc.collect()

            winner = select_best_candidate(horizon_candidates)
            ranking = sorted(
                horizon_candidates,
                key=lambda item: (
                    item.accepted,
                    item.robust_score,
                    item.mean_daily_net_value_per_million_usdt,
                ),
                reverse=True,
            )
            if winner is not None:
                development_winners.append(winner)
                print(
                    f'''{target_symbol} H={horizon}s DEV winner: '''
                    f'''{winner.model_spec.preset}, '''
                    f'''{winner.policy_spec.policy_id}, '''
                    f'''mean={winner.mean_daily_net_value_per_million_usdt:+.4f}, '''
                    f'''robust={winner.robust_score:+.4f}, '''
                    f'''positive_days={winner.positive_day_fraction:.2%}''',
                    flush=True,
                )
            else:
                print(
                    f'''{target_symbol} H={horizon}s: '''
                    'no accepted development candidate',
                    flush=True,
                )

            development_payload[str(horizon)] = {
                'winner': asdict(winner) if winner else None,
                'leaderboard_top20': [
                    asdict(item) for item in ranking[:20]
                ],
            }

            del training, train_map, development_map
            gc.collect()

        validation_candidates: list[CandidateSummary] = []
        validation_payload: dict[str, Any] = {}

        for dev_winner in development_winners:
            horizon = dev_winner.horizon_seconds
            fit_dates = train_dates + development_dates
            fit_map = build_datasets_for_dates(
                market_cache,
                fit_dates,
                target_symbol=target_symbol,
                horizon_seconds=horizon,
                decision_stride_seconds=(
                    arguments.decision_stride_seconds
                ),
                scenario=scenario,
            )
            validation_map = build_datasets_for_dates(
                market_cache,
                validation_dates,
                target_symbol=target_symbol,
                horizon_seconds=horizon,
                decision_stride_seconds=(
                    arguments.decision_stride_seconds
                ),
                scenario=scenario,
            )
            fitting = concatenate_datasets(
                [fit_map[item] for item in fit_dates]
            )
            state = fit_hurdle_state(
                fitting,
                dev_winner.model_spec,
            )
            predictions = predictions_for_days(
                state,
                validation_map,
            )
            validation_metrics = evaluate_candidate_on_days(
                predictions=predictions,
                datasets=validation_map,
                policy=dev_winner.policy_spec,
                scenario=scenario,
            )
            validation_summary = summarize_candidate(
                horizon_seconds=horizon,
                model_spec=dev_winner.model_spec,
                policy_spec=dev_winner.policy_spec,
                daily_metrics=validation_metrics,
                risk_penalty=arguments.risk_penalty,
                minimum_positive_day_fraction=(
                    arguments.minimum_positive_day_fraction
                ),
            )
            validation_candidates.append(validation_summary)

            evaluation = evaluate_predictions(
                datasets=validation_map,
                predictions=predictions,
                policy=dev_winner.policy_spec,
                scenario=scenario,
                bootstrap_samples=arguments.bootstrap_samples,
                seed_offset=target_index * 100_000 + horizon,
            )
            validation_payload[str(horizon)] = {
                'candidate': asdict(validation_summary),
                'evaluation': evaluation,
            }
            print(
                f'''{target_symbol} H={horizon}s VALIDATION: '''
                f'''mean={validation_summary.mean_daily_net_value_per_million_usdt:+.4f}, '''
                f'''robust={validation_summary.robust_score:+.4f}, '''
                f'''positive_days={validation_summary.positive_day_fraction:.2%}, '''
                f'''accepted={validation_summary.accepted}''',
                flush=True,
            )

            del (
                fitting,
                fit_map,
                validation_map,
                state,
                predictions,
                validation_metrics,
            )
            gc.collect()

        final_candidate = select_best_candidate(
            validation_candidates
        )

        if final_candidate is None:
            print(
                f'''{target_symbol}: no accepted validation candidate; '''
                'final policy is no_action',
                flush=True,
            )
            target_output = {
                'development': development_payload,
                'validation': validation_payload,
                'selected_final_candidate': None,
                'status': 'no_action_fallback_after_validation',
                'final_test': None,
            }
            output['targets'][target_symbol] = target_output
            write_json(arguments.output, output)
            continue

        selected_horizon = final_candidate.horizon_seconds
        fit_dates = (
            train_dates
            + development_dates
            + validation_dates
        )
        fit_map = build_datasets_for_dates(
            market_cache,
            fit_dates,
            target_symbol=target_symbol,
            horizon_seconds=selected_horizon,
            decision_stride_seconds=(
                arguments.decision_stride_seconds
            ),
            scenario=scenario,
        )
        final_map = build_datasets_for_dates(
            market_cache,
            final_dates,
            target_symbol=target_symbol,
            horizon_seconds=selected_horizon,
            decision_stride_seconds=(
                arguments.decision_stride_seconds
            ),
            scenario=scenario,
        )
        fitting = concatenate_datasets(
            [fit_map[item] for item in fit_dates]
        )
        final_state = fit_hurdle_state(
            fitting,
            final_candidate.model_spec,
        )
        final_predictions = predictions_for_days(
            final_state,
            final_map,
        )
        final_evaluation = evaluate_predictions(
            datasets=final_map,
            predictions=final_predictions,
            policy=final_candidate.policy_spec,
            scenario=scenario,
            bootstrap_samples=arguments.bootstrap_samples,
            seed_offset=(
                target_index * 100_000
                + selected_horizon
                + 50_000
            ),
        )

        hurdle_aggregate = final_evaluation['aggregate'][
            'hurdle_economic'
        ]
        hurdle_bootstrap = final_evaluation['bootstrap'][
            'hurdle_minus_no_action'
        ]
        print(
            f'''{target_symbol}: FINAL H={selected_horizon}s '''
            f'''net={hurdle_aggregate['net_value_per_million_usdt']:+.4f} '''
            f'''USDT/$1M, '''
            f'''CI=[{hurdle_bootstrap['ci_025']:+.4f}, '''
            f'''{hurdle_bootstrap['ci_975']:+.4f}], '''
            f'''positive_days='''
            f'''{hurdle_bootstrap['positive_day_fraction']:.2%}, '''
            f'''oracle_capture='''
            f'''{final_evaluation['oracle_capture_fraction']:.2%}''',
            flush=True,
        )

        target_output = {
            'development': development_payload,
            'validation': validation_payload,
            'selected_final_candidate': asdict(final_candidate),
            'status': 'final_candidate_evaluated',
            'final_test': final_evaluation,
        }
        output['targets'][target_symbol] = target_output
        write_json(arguments.output, output)

        del (
            fit_map,
            final_map,
            fitting,
            final_state,
            final_predictions,
        )
        gc.collect()

    write_json(arguments.output, output)


if __name__ == '__main__':
    main()
