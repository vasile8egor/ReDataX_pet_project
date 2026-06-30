from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from revolut_app.real_market.experiments import coupled_rg_final as coupled


DEFAULT_CAPACITY_FRACTIONS = (0.01, 0.05, 0.10, 0.20)
DEFAULT_SCENARIOS = (
    ("conservative", 0.25, 0.10, 1.00),
    ("base", 0.50, 0.25, 0.50),
    ("optimistic", 0.75, 0.50, 0.25),
)
COMPARISONS = (
    ("rg_no_j_minus_m1", "rg_no_j", "m1_local"),
    ("rg_with_j_minus_no_j", "rg_with_j", "rg_no_j"),
)
BOOTSTRAP_METRICS = (
    "net_protected_value_per_million_total_notional",
    "gross_protected_value_per_million_total_notional",
    "break_even_action_cost_bps",
    "capture_rate",
    "risk_concentration",
    "selected_notional_fraction",
)


SECONDLY_NOTIONAL_SQL = """
SELECT
    toUInt32(
        intDiv(
            timestamp_us - %(day_start_us)s,
            1000000
        )
    ) AS second_index,
    symbol,
    sum(toFloat64(quote_quantity)) AS quote_notional_usdt
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol IN %(symbols)s
GROUP BY
    second_index,
    symbol
ORDER BY
    second_index,
    symbol
"""


@dataclass(frozen=True)
class BusinessScenario:
    name: str
    mitigation_efficiency: float
    internalization_rate: float
    action_cost_bps: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scenario name cannot be empty")
        if not 0.0 <= self.mitigation_efficiency <= 1.0:
            raise ValueError("mitigation_efficiency must be in [0, 1]")
        if not 0.0 <= self.internalization_rate <= 1.0:
            raise ValueError("internalization_rate must be in [0, 1]")
        if self.action_cost_bps < 0.0:
            raise ValueError("action_cost_bps cannot be negative")


@dataclass(frozen=True)
class BusinessDayDataset:
    features: dict[str, np.ndarray]
    markout_bps: np.ndarray
    notional_usdt: np.ndarray
    adverse_loss_usdt: np.ndarray


@dataclass(frozen=True)
class BusinessMetrics:
    observations: int
    selected_observations: int
    selected_trade_fraction: float

    total_notional_usdt: float
    selected_notional_usdt: float
    selected_notional_fraction: float

    total_adverse_loss_usdt: float
    captured_adverse_loss_usdt: float
    capture_rate: float
    risk_concentration: float

    gross_protected_value_usdt: float
    action_cost_usdt: float
    net_protected_value_usdt: float

    gross_protected_value_per_million_total_notional: float
    net_protected_value_per_million_total_notional: float
    break_even_action_cost_bps: float
    benefit_cost_ratio: float


def parse_scenario(value: str) -> BusinessScenario:
    """
    Parse NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS.

    Example:
        base:0.50:0.25:0.50
    """
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "scenario must be NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS"
        )
    name, mitigation, internalization, action_cost = parts
    try:
        return BusinessScenario(
            name=name,
            mitigation_efficiency=float(mitigation),
            internalization_rate=float(internalization),
            action_cost_bps=float(action_cost),
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def default_scenarios() -> tuple[BusinessScenario, ...]:
    return tuple(
        BusinessScenario(
            name=name,
            mitigation_efficiency=mitigation,
            internalization_rate=internalization,
            action_cost_bps=action_cost,
        )
        for name, mitigation, internalization, action_cost in DEFAULT_SCENARIOS
    )


def parse_capacity(value: str) -> float:
    fraction = float(value)
    if not 0.0 < fraction <= 1.0:
        raise argparse.ArgumentTypeError("capacity must be in (0, 1]")
    return fraction


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_frozen_result(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("frozen result root must be an object")
    required = {"configuration", "targets"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"frozen result misses keys: {sorted(missing)}")
    return payload


def exact_top_fraction_mask(
    scores: np.ndarray,
    fraction: float,
) -> np.ndarray:
    if scores.ndim != 1 or scores.size == 0:
        raise ValueError("scores must be a non-empty vector")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")

    selected_count = max(1, int(np.ceil(scores.size * fraction)))
    selected_indices = np.argpartition(
        scores,
        scores.size - selected_count,
    )[scores.size - selected_count :]

    selected = np.zeros(scores.size, dtype=bool)
    selected[selected_indices] = True
    return selected


def adverse_loss_usdt(
    notional_usdt: np.ndarray,
    markout_bps: np.ndarray,
) -> np.ndarray:
    if notional_usdt.shape == markout_bps.shape:
        if np.any(notional_usdt <= 0.0):
            raise ValueError("notional must be positive")
        return (
            notional_usdt
            * np.maximum(markout_bps, 0.0)
            / 10_000.0
        )
    raise ValueError("notional and markout shapes differ")


def calculate_business_metrics(
    *,
    scores: np.ndarray,
    losses_usdt: np.ndarray,
    notional_usdt: np.ndarray,
    capacity_fraction: float,
    scenario: BusinessScenario,
) -> BusinessMetrics:
    if not (scores.shape == losses_usdt.shape == notional_usdt.shape):
        raise ValueError("scores, losses and notional shapes differ")
    if scores.ndim != 1 or scores.size == 0:
        raise ValueError("business arrays must be non-empty vectors")
    if np.any(losses_usdt < 0.0):
        raise ValueError("losses cannot be negative")
    if np.any(notional_usdt <= 0.0):
        raise ValueError("notional must be positive")

    selected = exact_top_fraction_mask(scores, capacity_fraction)

    observations = int(scores.size)
    selected_observations = int(np.sum(selected))

    total_notional = float(np.sum(notional_usdt, dtype=np.float64))
    selected_notional = float(
        np.sum(notional_usdt[selected], dtype=np.float64)
    )
    total_loss = float(np.sum(losses_usdt, dtype=np.float64))
    captured_loss = float(
        np.sum(losses_usdt[selected], dtype=np.float64)
    )

    selected_trade_fraction = selected_observations / observations
    selected_notional_fraction = selected_notional / total_notional
    capture_rate = (
        captured_loss / total_loss
        if total_loss > 0.0
        else float("nan")
    )
    risk_concentration = (
        capture_rate / selected_notional_fraction
        if selected_notional_fraction > 0.0 and np.isfinite(capture_rate)
        else float("nan")
    )

    gross_protected_value = (
        scenario.internalization_rate
        * scenario.mitigation_efficiency
        * captured_loss
    )
    action_cost = (
        selected_notional
        * scenario.action_cost_bps
        / 10_000.0
    )
    net_protected_value = gross_protected_value - action_cost

    gross_per_million = (
        gross_protected_value / total_notional * 1_000_000.0
    )
    net_per_million = (
        net_protected_value / total_notional * 1_000_000.0
    )
    break_even_cost_bps = (
        10_000.0 * gross_protected_value / selected_notional
        if selected_notional > 0.0
        else float("nan")
    )
    benefit_cost_ratio = (
        gross_protected_value / action_cost
        if action_cost > 0.0
        else (
            float("inf")
            if gross_protected_value > 0.0
            else float("nan")
        )
    )

    return BusinessMetrics(
        observations=observations,
        selected_observations=selected_observations,
        selected_trade_fraction=float(selected_trade_fraction),
        total_notional_usdt=total_notional,
        selected_notional_usdt=selected_notional,
        selected_notional_fraction=float(selected_notional_fraction),
        total_adverse_loss_usdt=total_loss,
        captured_adverse_loss_usdt=captured_loss,
        capture_rate=float(capture_rate),
        risk_concentration=float(risk_concentration),
        gross_protected_value_usdt=float(gross_protected_value),
        action_cost_usdt=float(action_cost),
        net_protected_value_usdt=float(net_protected_value),
        gross_protected_value_per_million_total_notional=float(
            gross_per_million
        ),
        net_protected_value_per_million_total_notional=float(
            net_per_million
        ),
        break_even_action_cost_bps=float(break_even_cost_bps),
        benefit_cost_ratio=float(benefit_cost_ratio),
    )


def aggregate_business_metrics(
    daily_metrics: list[BusinessMetrics],
    *,
    scenario: BusinessScenario,
) -> BusinessMetrics:
    if not daily_metrics:
        raise ValueError("daily_metrics cannot be empty")

    observations = sum(item.observations for item in daily_metrics)
    selected_observations = sum(
        item.selected_observations for item in daily_metrics
    )
    total_notional = sum(
        item.total_notional_usdt for item in daily_metrics
    )
    selected_notional = sum(
        item.selected_notional_usdt for item in daily_metrics
    )
    total_loss = sum(
        item.total_adverse_loss_usdt for item in daily_metrics
    )
    captured_loss = sum(
        item.captured_adverse_loss_usdt for item in daily_metrics
    )

    selected_trade_fraction = selected_observations / observations
    selected_notional_fraction = selected_notional / total_notional
    capture_rate = (
        captured_loss / total_loss
        if total_loss > 0.0
        else float("nan")
    )
    risk_concentration = (
        capture_rate / selected_notional_fraction
        if selected_notional_fraction > 0.0 and np.isfinite(capture_rate)
        else float("nan")
    )

    gross_protected_value = (
        scenario.internalization_rate
        * scenario.mitigation_efficiency
        * captured_loss
    )
    action_cost = (
        selected_notional
        * scenario.action_cost_bps
        / 10_000.0
    )
    net_protected_value = gross_protected_value - action_cost

    return BusinessMetrics(
        observations=observations,
        selected_observations=selected_observations,
        selected_trade_fraction=float(selected_trade_fraction),
        total_notional_usdt=float(total_notional),
        selected_notional_usdt=float(selected_notional),
        selected_notional_fraction=float(selected_notional_fraction),
        total_adverse_loss_usdt=float(total_loss),
        captured_adverse_loss_usdt=float(captured_loss),
        capture_rate=float(capture_rate),
        risk_concentration=float(risk_concentration),
        gross_protected_value_usdt=float(gross_protected_value),
        action_cost_usdt=float(action_cost),
        net_protected_value_usdt=float(net_protected_value),
        gross_protected_value_per_million_total_notional=float(
            gross_protected_value / total_notional * 1_000_000.0
        ),
        net_protected_value_per_million_total_notional=float(
            net_protected_value / total_notional * 1_000_000.0
        ),
        break_even_action_cost_bps=float(
            10_000.0 * gross_protected_value / selected_notional
        ),
        benefit_cost_ratio=float(
            gross_protected_value / action_cost
            if action_cost > 0.0
            else (
                float("inf")
                if gross_protected_value > 0.0
                else float("nan")
            )
        ),
    )


def paired_day_bootstrap(
    values: list[float],
    *,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    finite = np.asarray(
        [value for value in values if np.isfinite(value)],
        dtype=np.float64,
    )
    if finite.size == 0:
        raise ValueError("no finite values for bootstrap")

    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(
        0,
        finite.size,
        size=(samples, finite.size),
    )
    sampled_means = np.mean(finite[sampled_indices], axis=1)

    return {
        "days": int(finite.size),
        "mean": float(np.mean(finite)),
        "ci_025": float(np.quantile(sampled_means, 0.025)),
        "ci_975": float(np.quantile(sampled_means, 0.975)),
        "positive_day_fraction": float(np.mean(finite > 0.0)),
    }


def valid_observation_indices(
    day: coupled.MarketDay,
    *,
    target_symbol: str,
    horizon_seconds: int,
) -> np.ndarray:
    target_index = coupled.SYMBOLS.index(target_symbol)
    seconds = np.arange(coupled.SECONDS_PER_DAY, dtype=np.int64)
    future_seconds = seconds + horizon_seconds

    side = np.sign(day.phi[:, target_index])
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
    return np.flatnonzero(valid)


def load_second_notional(
    clickhouse: Any,
    trade_date: date,
) -> np.ndarray:
    rows = clickhouse.execute(
        SECONDLY_NOTIONAL_SQL,
        {
            "trade_date": trade_date,
            "day_start_us": coupled.utc_midnight_us(trade_date),
            "symbols": coupled.TARGET_SYMBOLS,
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

    for second_index, symbol, quote_notional in rows:
        second = int(second_index)
        symbol_text = str(symbol)
        if symbol_text not in symbol_index:
            raise ValueError(f"unexpected symbol: {symbol_text}")
        if not 0 <= second < coupled.SECONDS_PER_DAY:
            raise ValueError(f"invalid second index: {second}")
        value = float(quote_notional)
        if value < 0.0:
            raise ValueError("negative quote notional")
        matrix[second, symbol_index[symbol_text]] = value

    return matrix


def build_business_day_dataset(
    day: coupled.MarketDay,
    second_notional: np.ndarray,
    *,
    target_symbol: str,
    horizon_seconds: int,
) -> BusinessDayDataset:
    if second_notional.shape != (
        coupled.SECONDS_PER_DAY,
        len(coupled.SYMBOLS),
    ):
        raise ValueError("invalid second_notional matrix shape")

    model_dataset = coupled.build_feature_matrices(
        day,
        target_symbol=target_symbol,
        horizon_seconds=horizon_seconds,
    )
    indices = valid_observation_indices(
        day,
        target_symbol=target_symbol,
        horizon_seconds=horizon_seconds,
    )

    if indices.size != model_dataset.markout_bps.size:
        raise RuntimeError(
            "business observation mapping differs from model feature mapping"
        )

    target_index = coupled.SYMBOLS.index(target_symbol)
    notional = second_notional[indices, target_index]
    valid_positive_notional = np.isfinite(notional) & (notional > 0.0)

    features = {
        name: matrix[valid_positive_notional]
        for name, matrix in model_dataset.features.items()
    }
    markout = model_dataset.markout_bps[valid_positive_notional].astype(
        np.float64,
        copy=False,
    )
    notional = notional[valid_positive_notional].astype(
        np.float64,
        copy=False,
    )

    return BusinessDayDataset(
        features=features,
        markout_bps=markout,
        notional_usdt=notional,
        adverse_loss_usdt=adverse_loss_usdt(notional, markout),
    )


def comparison_values(
    model_metrics: dict[str, BusinessMetrics],
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for comparison, first_model, second_model in COMPARISONS:
        first = model_metrics[first_model]
        second = model_metrics[second_model]
        output[comparison] = {
            metric: float(
                getattr(first, metric) - getattr(second, metric)
            )
            for metric in BOOTSTRAP_METRICS
        }
    return output


def evaluate_business_value(
    *,
    clickhouse: Any,
    cache: dict[date, coupled.MarketDay],
    final_dates: list[date],
    target_symbol: str,
    horizon_seconds: int,
    states: dict[str, coupled.ModelState],
    capacity_fractions: tuple[float, ...],
    scenarios: tuple[BusinessScenario, ...],
    bootstrap_samples: int,
) -> dict[str, Any]:
    daily: list[dict[str, Any]] = []

    for trade_date in final_dates:
        print(
            f"{target_symbol}: business scoring {trade_date}",
            flush=True,
        )
        second_notional = load_second_notional(
            clickhouse,
            trade_date,
        )
        dataset = build_business_day_dataset(
            cache[trade_date],
            second_notional,
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
        )

        scores: dict[str, np.ndarray] = {}
        for model_name in coupled.MODEL_NAMES:
            state = states[model_name]
            transformed = state.scaler.transform(
                dataset.features[model_name]
            )
            scores[model_name] = state.classifier.predict_proba(
                transformed
            )[:, 1]

        capacity_payload: dict[str, Any] = {}
        for capacity in capacity_fractions:
            capacity_key = f"{capacity:.6f}"
            scenario_payload: dict[str, Any] = {}

            for scenario in scenarios:
                model_metrics = {
                    model_name: calculate_business_metrics(
                        scores=scores[model_name],
                        losses_usdt=dataset.adverse_loss_usdt,
                        notional_usdt=dataset.notional_usdt,
                        capacity_fraction=capacity,
                        scenario=scenario,
                    )
                    for model_name in coupled.MODEL_NAMES
                }
                scenario_payload[scenario.name] = {
                    "scenario": asdict(scenario),
                    "models": {
                        name: asdict(metrics)
                        for name, metrics in model_metrics.items()
                    },
                    "comparisons": comparison_values(model_metrics),
                }

            capacity_payload[capacity_key] = {
                "capacity_fraction": capacity,
                "scenarios": scenario_payload,
            }

        daily.append(
            {
                "date": trade_date.isoformat(),
                "capacities": capacity_payload,
            }
        )

    aggregate: dict[str, Any] = {}
    bootstrap: dict[str, Any] = {}

    for capacity in capacity_fractions:
        capacity_key = f"{capacity:.6f}"
        aggregate[capacity_key] = {}
        bootstrap[capacity_key] = {}

        for scenario in scenarios:
            aggregate_models: dict[str, BusinessMetrics] = {}
            for model_name in coupled.MODEL_NAMES:
                daily_metrics = [
                    BusinessMetrics(
                        **day["capacities"][capacity_key]["scenarios"][
                            scenario.name
                        ]["models"][model_name]
                    )
                    for day in daily
                ]
                aggregate_models[model_name] = aggregate_business_metrics(
                    daily_metrics,
                    scenario=scenario,
                )

            aggregate[capacity_key][scenario.name] = {
                "scenario": asdict(scenario),
                "models": {
                    name: asdict(metrics)
                    for name, metrics in aggregate_models.items()
                },
                "comparisons": comparison_values(aggregate_models),
            }

            scenario_bootstrap: dict[str, Any] = {}
            for comparison, _, _ in COMPARISONS:
                scenario_bootstrap[comparison] = {}
                for metric in BOOTSTRAP_METRICS:
                    values = [
                        day["capacities"][capacity_key]["scenarios"][
                            scenario.name
                        ]["comparisons"][comparison][metric]
                        for day in daily
                    ]
                    scenario_bootstrap[comparison][metric] = (
                        paired_day_bootstrap(
                            values,
                            samples=bootstrap_samples,
                            seed=(
                                coupled.SEED
                                + horizon_seconds
                                + int(capacity * 10_000)
                                + len(scenario.name)
                                + len(comparison)
                                + len(metric)
                            ),
                        )
                    )
            bootstrap[capacity_key][scenario.name] = scenario_bootstrap

    return {
        "daily": daily,
        "aggregate": aggregate,
        "bootstrap": bootstrap,
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate scenario-adjusted business value of the frozen "
            "cross-market models without retuning the final holdout."
        )
    )
    parser.add_argument(
        "--frozen-result",
        required=True,
        help="Path to the already evaluated coupled_rg_final.json.",
    )
    parser.add_argument(
        "--target-symbols",
        nargs="+",
        choices=coupled.TARGET_SYMBOLS,
        default=list(coupled.TARGET_SYMBOLS),
    )
    parser.add_argument(
        "--capacity-fractions",
        nargs="+",
        type=parse_capacity,
        default=list(DEFAULT_CAPACITY_FRACTIONS),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        type=parse_scenario,
        help=(
            "NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS. "
            "Repeat for multiple scenarios. Defaults to conservative, "
            "base and optimistic."
        ),
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=5000,
    )
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()

    frozen = read_frozen_result(arguments.frozen_result)
    configuration = frozen["configuration"]

    horizon_seconds = int(configuration["horizon_seconds"])
    train_dates = [
        date.fromisoformat(value)
        for value in configuration["train_dates"]
    ]
    development_dates = [
        date.fromisoformat(value)
        for value in configuration["development_dates"]
    ]
    final_dates = [
        date.fromisoformat(value)
        for value in configuration["final_test_dates"]
    ]
    fit_dates = train_dates + development_dates

    if len(set(fit_dates + final_dates)) != len(fit_dates + final_dates):
        raise ValueError("frozen date ranges overlap")

    capacity_fractions = tuple(
        sorted(set(arguments.capacity_fractions))
    )
    scenarios = (
        tuple(arguments.scenario)
        if arguments.scenario
        else default_scenarios()
    )
    if len({scenario.name for scenario in scenarios}) != len(scenarios):
        raise ValueError("scenario names must be unique")

    target_symbols = tuple(dict.fromkeys(arguments.target_symbols))
    missing_targets = [
        symbol for symbol in target_symbols
        if symbol not in frozen["targets"]
    ]
    if missing_targets:
        raise ValueError(
            f"frozen result misses targets: {missing_targets}"
        )

    clickhouse = coupled.create_client()
    all_dates = fit_dates + final_dates
    cache: dict[date, coupled.MarketDay] = {}

    for trade_date in all_dates:
        print(f"Loading synchronized day {trade_date}", flush=True)
        cache[trade_date] = coupled.load_market_day(
            clickhouse,
            trade_date,
        )

    output: dict[str, Any] = {
        "configuration": {
            "source_frozen_result": str(arguments.frozen_result),
            "source_sha256": sha256_file(arguments.frozen_result),
            "target_symbols": list(target_symbols),
            "horizon_seconds": horizon_seconds,
            "capacity_fractions": list(capacity_fractions),
            "scenarios": [asdict(item) for item in scenarios],
            "train_dates": [
                value.isoformat() for value in train_dates
            ],
            "development_dates": [
                value.isoformat() for value in development_dates
            ],
            "final_test_dates": [
                value.isoformat() for value in final_dates
            ],
            "loss_definition": (
                "current_second_quote_notional * "
                "max(aggressor_aligned_future_markout_bps, 0) / 10000"
            ),
            "gross_value_definition": (
                "internalization_rate * mitigation_efficiency * "
                "captured_adverse_loss"
            ),
            "action_cost_definition": (
                "selected_notional * action_cost_bps / 10000"
            ),
            "net_value_definition": (
                "gross_protected_value - action_cost"
            ),
            "interpretation": (
                "scenario-adjusted potential value; not realized PnL"
            ),
            "model_selection_policy": (
                "selected alphas are read from the frozen result; "
                "the final holdout is not used for retuning"
            ),
        },
        "targets": {},
    }

    for target_symbol in target_symbols:
        selected_alphas = {
            name: float(value)
            for name, value in frozen["targets"][target_symbol][
                "selected_alphas"
            ].items()
        }
        missing_models = set(coupled.MODEL_NAMES) - selected_alphas.keys()
        if missing_models:
            raise ValueError(
                f"{target_symbol}: selected alphas miss "
                f"{sorted(missing_models)}"
            )

        print(
            f"{target_symbol}: refitting frozen specification "
            f"{selected_alphas}",
            flush=True,
        )
        states = coupled.fit_final_states(
            cache,
            fit_dates,
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
            selected_alphas=selected_alphas,
        )

        evaluation = evaluate_business_value(
            clickhouse=clickhouse,
            cache=cache,
            final_dates=final_dates,
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
            states=states,
            capacity_fractions=capacity_fractions,
            scenarios=scenarios,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        output["targets"][target_symbol] = {
            "selected_alphas": selected_alphas,
            **evaluation,
        }

        base_scenario = next(
            (
                scenario
                for scenario in scenarios
                if scenario.name == "base"
            ),
            scenarios[0],
        )
        for capacity in capacity_fractions:
            key = f"{capacity:.6f}"
            delta = evaluation["bootstrap"][key][
                base_scenario.name
            ]["rg_no_j_minus_m1"][
                "net_protected_value_per_million_total_notional"
            ]
            print(
                f"{target_symbol} q={capacity:.0%} "
                f"scenario={base_scenario.name} "
                f"RG-noJ minus M1 net value per $1m="
                f"{delta['mean']:+.4f} "
                f"CI=[{delta['ci_025']:+.4f},"
                f"{delta['ci_975']:+.4f}]",
                flush=True,
            )

        write_json(arguments.output, output)

    write_json(arguments.output, output)


if __name__ == "__main__":
    main()
