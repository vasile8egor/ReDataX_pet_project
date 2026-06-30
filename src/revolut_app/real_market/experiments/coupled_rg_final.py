from __future__ import annotations

import argparse
import calendar
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

try:
    from clickhouse_driver import Client
except ImportError:  # Allows pure unit tests outside the project container.
    Client = Any  # type: ignore[misc,assignment]


SYMBOLS = ("BTCUSDT", "ETHUSDT", "ETHBTC")
TARGET_SYMBOLS = ("BTCUSDT", "ETHUSDT")
SCALES_SECONDS = (1, 2, 4, 8, 16, 32, 64)
MODEL_NAMES = ("m1_local", "rg_no_j", "rg_with_j")
DEFAULT_ALPHAS = (1e-5, 1e-4, 1e-3)

SECONDS_PER_DAY = 86_400
SEED = 20260628


SECONDLY_FLOW_SQL = """
SELECT
    toUInt32(
        intDiv(
            timestamp_us - %(day_start_us)s,
            1000000
        )
    ) AS second_index,
    symbol,
    sumIf(
        toFloat64(quote_quantity),
        aggressor_side = 'buy_base'
    ) AS buy_quote_quantity,
    sumIf(
        toFloat64(quote_quantity),
        aggressor_side = 'sell_base'
    ) AS sell_quote_quantity,
    sum(toFloat64(quote_quantity))
        / sum(toFloat64(base_quantity))
        AS vwap
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
class MarketDay:
    trade_date: date
    phi: np.ndarray
    log_volume: np.ndarray
    vwap: np.ndarray
    active: np.ndarray
    coarse_phi: np.ndarray


@dataclass(frozen=True)
class DayDataset:
    features: dict[str, np.ndarray]
    feature_names: dict[str, tuple[str, ...]]
    labels: np.ndarray
    markout_bps: np.ndarray


@dataclass
class ModelState:
    scaler: StandardScaler
    classifier: SGDClassifier
    alpha: float


@dataclass(frozen=True)
class Metrics:
    observations: int
    toxic_rate: float
    roc_auc: float
    average_precision: float
    brier_score: float
    top_decile_lift: float


def date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date is before start date")
    return [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
    ]


def utc_midnight_us(value: date) -> int:
    return calendar.timegm(value.timetuple()) * 1_000_000


def create_client() -> Client:
    if Client is Any:
        raise RuntimeError(
            "clickhouse-driver is required inside the project container"
        )
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default"),
    )


def trailing_means(
    values: np.ndarray,
    scales: tuple[int, ...] = SCALES_SECONDS,
) -> np.ndarray:
    """
    Clock-time trailing means including the current completed second.

    Result[t, j] uses values[t-scale+1 : t+1].
    Seconds without trades must already be represented by zero.
    """
    if values.ndim != 2:
        raise ValueError("values must have shape (time, components)")
    if not scales or any(scale <= 0 for scale in scales):
        raise ValueError("scales must contain positive integers")

    count, components = values.shape
    cumulative = np.vstack(
        (
            np.zeros((1, components), dtype=np.float64),
            np.cumsum(values, axis=0, dtype=np.float64),
        )
    )
    output = np.full(
        (count, len(scales), components),
        np.nan,
        dtype=np.float32,
    )

    for scale_index, scale in enumerate(scales):
        if scale > count:
            continue
        sums = cumulative[scale:] - cumulative[:-scale]
        output[scale - 1 :, scale_index, :] = (
            sums / float(scale)
        ).astype(np.float32)

    return output


def load_market_day(
    clickhouse: Client,
    trade_date: date,
) -> MarketDay:
    rows = clickhouse.execute(
        SECONDLY_FLOW_SQL,
        {
            "trade_date": trade_date,
            "day_start_us": utc_midnight_us(trade_date),
            "symbols": SYMBOLS,
        },
    )

    buy = np.zeros(
        (SECONDS_PER_DAY, len(SYMBOLS)),
        dtype=np.float64,
    )
    sell = np.zeros_like(buy)
    vwap = np.full_like(buy, np.nan)

    symbol_index = {
        symbol: index
        for index, symbol in enumerate(SYMBOLS)
    }
    row_counts = {symbol: 0 for symbol in SYMBOLS}

    for (
        second_index,
        symbol,
        buy_quote,
        sell_quote,
        second_vwap,
    ) in rows:
        second = int(second_index)
        if not 0 <= second < SECONDS_PER_DAY:
            raise ValueError(
                f"second_index outside UTC day: {second}"
            )
        symbol_text = str(symbol)
        if symbol_text not in symbol_index:
            raise ValueError(f"unexpected symbol: {symbol_text}")

        component = symbol_index[symbol_text]
        buy_value = float(buy_quote)
        sell_value = float(sell_quote)
        price_value = float(second_vwap)

        if buy_value < 0 or sell_value < 0:
            raise ValueError("negative aggregated quote volume")
        if price_value <= 0:
            raise ValueError("non-positive second VWAP")

        buy[second, component] = buy_value
        sell[second, component] = sell_value
        vwap[second, component] = price_value
        row_counts[symbol_text] += 1

    missing = [
        symbol
        for symbol, row_count in row_counts.items()
        if row_count == 0
    ]
    if missing:
        raise ValueError(
            f"missing symbols on {trade_date}: {missing}"
        )

    total = buy + sell
    signed = buy - sell
    active = total > 0

    phi = np.zeros_like(total, dtype=np.float32)
    phi[active] = (
        signed[active] / total[active]
    ).astype(np.float32)

    log_volume = np.log1p(total).astype(np.float32)
    coarse_phi = trailing_means(phi)

    return MarketDay(
        trade_date=trade_date,
        phi=phi,
        log_volume=log_volume,
        vwap=vwap,
        active=active,
        coarse_phi=coarse_phi,
    )


def _flatten_scale_component(
    values: np.ndarray,
) -> np.ndarray:
    if values.ndim != 3:
        raise ValueError(
            "values must have shape "
            "(observations, scales, components)"
        )
    return values.reshape(values.shape[0], -1)


def build_feature_matrices(
    day: MarketDay,
    *,
    target_symbol: str,
    horizon_seconds: int,
) -> DayDataset:
    if target_symbol not in TARGET_SYMBOLS:
        raise ValueError(
            f"unsupported target symbol: {target_symbol}"
        )
    if horizon_seconds <= 0:
        raise ValueError(
            "horizon_seconds must be positive"
        )

    target_index = SYMBOLS.index(target_symbol)
    seconds = np.arange(SECONDS_PER_DAY, dtype=np.int64)
    future_seconds = seconds + horizon_seconds

    current_flow = day.phi[:, target_index]
    side = np.sign(current_flow)

    valid = (
        (seconds >= max(SCALES_SECONDS) - 1)
        & (future_seconds < SECONDS_PER_DAY)
        & day.active[:, target_index]
        & (side != 0)
    )

    safe_future = np.minimum(
        future_seconds,
        SECONDS_PER_DAY - 1,
    )
    current_vwap = day.vwap[:, target_index]
    future_vwap = day.vwap[safe_future, target_index]

    valid &= (
        np.isfinite(current_vwap)
        & np.isfinite(future_vwap)
        & (current_vwap > 0)
        & (future_vwap > 0)
    )

    indices = np.flatnonzero(valid)
    if indices.size == 0:
        raise ValueError(
            f"no valid observations for "
            f"{target_symbol} on {day.trade_date}"
        )

    side_valid = side[indices].astype(
        np.float32,
        copy=False,
    )
    field = day.coarse_phi[indices].astype(
        np.float32,
        copy=False,
    )
    aligned = field * side_valid[:, None, None]
    absolute = np.abs(field)
    q2 = field * field
    q4 = q2 * q2
    current_log_volume = day.log_volume[indices]

    local_columns: list[np.ndarray] = [
        current_log_volume[:, target_index]
    ]
    local_names = [f"log_volume[{target_symbol}]"]

    for scale_index, scale in enumerate(SCALES_SECONDS):
        local_columns.extend(
            (
                aligned[:, scale_index, target_index],
                absolute[:, scale_index, target_index],
                q2[:, scale_index, target_index],
                q4[:, scale_index, target_index],
            )
        )
        local_names.extend(
            (
                f"h[{target_symbol},B={scale}]",
                f"abs[{target_symbol},B={scale}]",
                f"a[{target_symbol},B={scale}]",
                f"b[{target_symbol},B={scale}]",
            )
        )

    m1_local = np.column_stack(local_columns).astype(
        np.float32,
        copy=False,
    )

    no_j_columns: list[np.ndarray] = []
    no_j_names: list[str] = []

    for component, symbol in enumerate(SYMBOLS):
        no_j_columns.append(current_log_volume[:, component])
        no_j_names.append(f"log_volume[{symbol}]")

    for scale_index, scale in enumerate(SCALES_SECONDS):
        for component, symbol in enumerate(SYMBOLS):
            no_j_columns.extend(
                (
                    aligned[:, scale_index, component],
                    absolute[:, scale_index, component],
                    q2[:, scale_index, component],
                    q4[:, scale_index, component],
                )
            )
            no_j_names.extend(
                (
                    f"h[{symbol},B={scale}]",
                    f"abs[{symbol},B={scale}]",
                    f"a[{symbol},B={scale}]",
                    f"b[{symbol},B={scale}]",
                )
            )

    rg_no_j = np.column_stack(no_j_columns).astype(
        np.float32,
        copy=False,
    )

    j_columns: list[np.ndarray] = [rg_no_j]
    j_names = list(no_j_names)
    pairs = (
        ("BTCUSDT", "ETHUSDT"),
        ("BTCUSDT", "ETHBTC"),
        ("ETHUSDT", "ETHBTC"),
    )

    for scale_index, scale in enumerate(SCALES_SECONDS):
        for first, second in pairs:
            first_index = SYMBOLS.index(first)
            second_index = SYMBOLS.index(second)
            # Multiplication by the current target side cancels,
            # so this is the physical pair interaction phi_i * phi_j.
            interaction = (
                aligned[:, scale_index, first_index]
                * aligned[:, scale_index, second_index]
            )
            j_columns.append(interaction)
            j_names.append(
                f"J[{first},{second},B={scale}]"
            )

    rg_with_j = np.column_stack(j_columns).astype(
        np.float32,
        copy=False,
    )

    markout = (
        side_valid.astype(np.float64)
        * (
            future_vwap[indices]
            - current_vwap[indices]
        )
        / current_vwap[indices]
        * 10_000.0
    )
    labels = (markout > 0).astype(np.uint8)

    return DayDataset(
        features={
            "m1_local": m1_local,
            "rg_no_j": rg_no_j,
            "rg_with_j": rg_with_j,
        },
        feature_names={
            "m1_local": tuple(local_names),
            "rg_no_j": tuple(no_j_names),
            "rg_with_j": tuple(j_names),
        },
        labels=labels,
        markout_bps=markout,
    )


def new_classifier(alpha: float) -> SGDClassifier:
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    return SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=alpha,
        learning_rate="optimal",
        average=True,
        random_state=SEED,
        shuffle=True,
    )


def fit_scalers(
    cache: dict[date, MarketDay],
    dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
) -> dict[str, StandardScaler]:
    scalers = {
        model_name: StandardScaler()
        for model_name in MODEL_NAMES
    }

    for trade_date in dates:
        dataset = build_feature_matrices(
            cache[trade_date],
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
        )
        for model_name in MODEL_NAMES:
            scalers[model_name].partial_fit(
                dataset.features[model_name]
            )

    return scalers


def fit_alpha_candidates(
    cache: dict[date, MarketDay],
    dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
    scalers: dict[str, StandardScaler],
    alphas: tuple[float, ...],
) -> dict[str, dict[float, ModelState]]:
    states: dict[str, dict[float, ModelState]] = {
        model_name: {
            alpha: ModelState(
                scaler=scalers[model_name],
                classifier=new_classifier(alpha),
                alpha=alpha,
            )
            for alpha in alphas
        }
        for model_name in MODEL_NAMES
    }
    classes = np.array([0, 1], dtype=np.uint8)

    for trade_date in dates:
        dataset = build_feature_matrices(
            cache[trade_date],
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
        )
        for model_name in MODEL_NAMES:
            transformed = scalers[model_name].transform(
                dataset.features[model_name]
            )
            for alpha in alphas:
                states[model_name][alpha].classifier.partial_fit(
                    transformed,
                    dataset.labels,
                    classes=classes,
                )

    return states


def exact_top_fraction_mask(
    scores: np.ndarray,
    fraction: float = 0.10,
) -> np.ndarray:
    if scores.ndim != 1 or scores.size == 0:
        raise ValueError(
            "scores must be a non-empty vector"
        )
    if not 0 < fraction <= 1:
        raise ValueError(
            "fraction must be in (0, 1]"
        )
    selected_count = max(
        1,
        int(np.ceil(scores.size * fraction)),
    )
    selected_indices = np.argpartition(
        scores,
        scores.size - selected_count,
    )[scores.size - selected_count :]
    mask = np.zeros(scores.size, dtype=bool)
    mask[selected_indices] = True
    return mask


def calculate_metrics(
    labels: np.ndarray,
    scores: np.ndarray,
) -> Metrics:
    if labels.shape != scores.shape:
        raise ValueError(
            "labels and scores have different shapes"
        )
    if np.unique(labels).size != 2:
        raise ValueError(
            "both target classes are required"
        )

    toxic_rate = float(np.mean(labels))
    selected = exact_top_fraction_mask(
        scores,
        fraction=0.10,
    )
    selected_rate = float(
        np.mean(labels[selected])
    )

    return Metrics(
        observations=int(labels.size),
        toxic_rate=toxic_rate,
        roc_auc=float(
            roc_auc_score(labels, scores)
        ),
        average_precision=float(
            average_precision_score(
                labels,
                scores,
            )
        ),
        brier_score=float(
            brier_score_loss(labels, scores)
        ),
        top_decile_lift=(
            selected_rate / toxic_rate
        ),
    )


def evaluate_states(
    cache: dict[date, MarketDay],
    dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
    states: dict[str, ModelState],
) -> dict[str, Any]:
    daily: list[dict[str, Any]] = []
    pooled_labels: list[np.ndarray] = []
    pooled_scores = {
        model_name: []
        for model_name in MODEL_NAMES
    }

    for trade_date in dates:
        dataset = build_feature_matrices(
            cache[trade_date],
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
        )
        model_metrics: dict[str, dict[str, Any]] = {}

        for model_name in MODEL_NAMES:
            state = states[model_name]
            transformed = state.scaler.transform(
                dataset.features[model_name]
            )
            scores = state.classifier.predict_proba(
                transformed
            )[:, 1]
            pooled_scores[model_name].append(
                scores.astype(np.float32)
            )
            model_metrics[model_name] = asdict(
                calculate_metrics(
                    dataset.labels,
                    scores,
                )
            )

        pooled_labels.append(dataset.labels)
        m1 = model_metrics["m1_local"]
        no_j = model_metrics["rg_no_j"]
        with_j = model_metrics["rg_with_j"]

        daily.append(
            {
                "date": trade_date.isoformat(),
                "models": model_metrics,
                "rg_no_j_minus_m1": {
                    "roc_auc": (
                        no_j["roc_auc"] - m1["roc_auc"]
                    ),
                    "average_precision": (
                        no_j["average_precision"]
                        - m1["average_precision"]
                    ),
                    "brier_improvement": (
                        m1["brier_score"]
                        - no_j["brier_score"]
                    ),
                    "top_decile_lift": (
                        no_j["top_decile_lift"]
                        - m1["top_decile_lift"]
                    ),
                },
                "rg_with_j_minus_no_j": {
                    "roc_auc": (
                        with_j["roc_auc"]
                        - no_j["roc_auc"]
                    ),
                    "average_precision": (
                        with_j["average_precision"]
                        - no_j["average_precision"]
                    ),
                    "brier_improvement": (
                        no_j["brier_score"]
                        - with_j["brier_score"]
                    ),
                    "top_decile_lift": (
                        with_j["top_decile_lift"]
                        - no_j["top_decile_lift"]
                    ),
                },
            }
        )

    all_labels = np.concatenate(pooled_labels)
    pooled = {
        model_name: asdict(
            calculate_metrics(
                all_labels,
                np.concatenate(
                    pooled_scores[model_name]
                ),
            )
        )
        for model_name in MODEL_NAMES
    }

    return {
        "daily": daily,
        "pooled": pooled,
    }


def mean_daily_ap(
    evaluation: dict[str, Any],
    model_name: str,
) -> float:
    return float(
        np.mean(
            [
                day["models"][model_name][
                    "average_precision"
                ]
                for day in evaluation["daily"]
            ]
        )
    )


def select_alphas(
    cache: dict[date, MarketDay],
    development_dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
    candidate_states: dict[
        str,
        dict[float, ModelState],
    ],
) -> tuple[
    dict[str, float],
    dict[str, dict[str, float]],
]:
    selected: dict[str, float] = {}
    scores: dict[str, dict[str, float]] = {}

    for model_name in MODEL_NAMES:
        model_scores: dict[str, float] = {}
        best_alpha: float | None = None
        best_score = -np.inf

        for alpha, state in candidate_states[
            model_name
        ].items():
            proxy_states = {
                name: (
                    state
                    if name == model_name
                    else next(
                        iter(
                            candidate_states[
                                name
                            ].values()
                        )
                    )
                )
                for name in MODEL_NAMES
            }
            evaluation = evaluate_states(
                cache,
                development_dates,
                target_symbol=target_symbol,
                horizon_seconds=horizon_seconds,
                states=proxy_states,
            )
            score = mean_daily_ap(
                evaluation,
                model_name,
            )
            model_scores[str(alpha)] = score

            if (
                score > best_score
                or (
                    np.isclose(score, best_score)
                    and (
                        best_alpha is None
                        or alpha > best_alpha
                    )
                )
            ):
                best_score = score
                best_alpha = alpha

        assert best_alpha is not None
        selected[model_name] = best_alpha
        scores[model_name] = model_scores

    return selected, scores


def fit_final_states(
    cache: dict[date, MarketDay],
    fit_dates: list[date],
    *,
    target_symbol: str,
    horizon_seconds: int,
    selected_alphas: dict[str, float],
) -> dict[str, ModelState]:
    scalers = fit_scalers(
        cache,
        fit_dates,
        target_symbol=target_symbol,
        horizon_seconds=horizon_seconds,
    )
    states = {
        model_name: ModelState(
            scaler=scalers[model_name],
            classifier=new_classifier(
                selected_alphas[model_name]
            ),
            alpha=selected_alphas[model_name],
        )
        for model_name in MODEL_NAMES
    }
    classes = np.array([0, 1], dtype=np.uint8)

    for trade_date in fit_dates:
        dataset = build_feature_matrices(
            cache[trade_date],
            target_symbol=target_symbol,
            horizon_seconds=horizon_seconds,
        )
        for model_name in MODEL_NAMES:
            state = states[model_name]
            transformed = state.scaler.transform(
                dataset.features[model_name]
            )
            state.classifier.partial_fit(
                transformed,
                dataset.labels,
                classes=classes,
            )

    return states


def bootstrap_daily_difference(
    daily: list[dict[str, Any]],
    *,
    comparison: str,
    metric_name: str,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    values = np.asarray(
        [
            day[comparison][metric_name]
            for day in daily
        ],
        dtype=np.float64,
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0,
        values.size,
        size=(samples, values.size),
    )
    means = np.mean(values[indices], axis=1)

    return {
        "days": int(values.size),
        "mean": float(np.mean(values)),
        "ci_025": float(
            np.quantile(means, 0.025)
        ),
        "ci_975": float(
            np.quantile(means, 0.975)
        ),
        "positive_day_fraction": float(
            np.mean(values > 0)
        ),
    }


def add_bootstrap(
    evaluation: dict[str, Any],
    *,
    bootstrap_samples: int,
    seed_offset: int,
) -> None:
    bootstrap: dict[str, Any] = {}
    comparisons = (
        "rg_no_j_minus_m1",
        "rg_with_j_minus_no_j",
    )
    metric_names = (
        "roc_auc",
        "average_precision",
        "brier_improvement",
        "top_decile_lift",
    )

    for comparison in comparisons:
        bootstrap[comparison] = {}
        for metric_name in metric_names:
            bootstrap[comparison][metric_name] = (
                bootstrap_daily_difference(
                    evaluation["daily"],
                    comparison=comparison,
                    metric_name=metric_name,
                    samples=bootstrap_samples,
                    seed=(
                        SEED
                        + seed_offset
                        + len(comparison)
                        + len(metric_name)
                    ),
                )
            )

    evaluation["bootstrap"] = bootstrap


def extract_raw_coefficients(
    state: ModelState,
    feature_names: tuple[str, ...],
) -> dict[str, float]:
    coefficients = (
        state.classifier.coef_[0]
        / state.scaler.scale_
    )
    if coefficients.size != len(feature_names):
        raise ValueError(
            "coefficient and feature counts differ"
        )
    return {
        name: float(value)
        for name, value in zip(
            feature_names,
            coefficients,
            strict=True,
        )
    }


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_alpha(value: str) -> float:
    alpha = float(value)
    if alpha <= 0:
        raise argparse.ArgumentTypeError(
            "alpha must be positive"
        )
    return alpha


def write_json(
    output_path: str,
    payload: dict[str, Any],
) -> None:
    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True,
    )
    temporary = f"{output_path}.part"
    with open(
        temporary,
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            payload,
            stream,
            ensure_ascii=False,
            indent=2,
        )
        stream.write("\n")
    os.replace(temporary, output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-symbols",
        nargs="+",
        default=list(TARGET_SYMBOLS),
    )
    parser.add_argument(
        "--horizon-seconds",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--alphas",
        nargs="+",
        type=parse_alpha,
        default=list(DEFAULT_ALPHAS),
    )
    parser.add_argument(
        "--train-start",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--train-end",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--development-start",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--development-end",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--final-test-start",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--final-test-end",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--output",
        required=True,
    )
    arguments = parser.parse_args()

    train_dates = date_range(
        arguments.train_start,
        arguments.train_end,
    )
    development_dates = date_range(
        arguments.development_start,
        arguments.development_end,
    )
    final_test_dates = date_range(
        arguments.final_test_start,
        arguments.final_test_end,
    )

    all_dates = (
        train_dates
        + development_dates
        + final_test_dates
    )
    if len(set(all_dates)) != len(all_dates):
        raise ValueError(
            "train, development and final-test dates overlap"
        )

    target_symbols = tuple(
        dict.fromkeys(arguments.target_symbols)
    )
    invalid_targets = [
        symbol
        for symbol in target_symbols
        if symbol not in TARGET_SYMBOLS
    ]
    if invalid_targets:
        raise ValueError(
            f"unsupported target symbols: {invalid_targets}"
        )

    alphas = tuple(
        sorted(set(arguments.alphas))
    )
    clickhouse = create_client()

    cache: dict[date, MarketDay] = {}
    for trade_date in all_dates:
        print(
            f"Loading synchronized day {trade_date}",
            flush=True,
        )
        cache[trade_date] = load_market_day(
            clickhouse,
            trade_date,
        )

    output: dict[str, Any] = {
        "configuration": {
            "symbols": list(SYMBOLS),
            "target_symbols": list(target_symbols),
            "scales_seconds": list(
                SCALES_SECONDS
            ),
            "horizon_seconds": (
                arguments.horizon_seconds
            ),
            "candidate_alphas": list(alphas),
            "train_dates": [
                value.isoformat()
                for value in train_dates
            ],
            "development_dates": [
                value.isoformat()
                for value in development_dates
            ],
            "final_test_dates": [
                value.isoformat()
                for value in final_test_dates
            ],
            "field_definition": (
                "(buy_quote - sell_quote) / "
                "(buy_quote + sell_quote), "
                "zero for inactive seconds"
            ),
            "target_definition": (
                "sign(current second net flow) * "
                "(future second VWAP - current second VWAP) "
                "/ current second VWAP"
            ),
            "model_interpretation": (
                "regularized predictive effective action; "
                "coefficients are not equilibrium free-energy "
                "parameters"
            ),
        },
        "targets": {},
    }

    fit_dates = train_dates + development_dates

    for target_symbol in target_symbols:
        print(
            f"{target_symbol}: fitting development candidates",
            flush=True,
        )
        scalers = fit_scalers(
            cache,
            train_dates,
            target_symbol=target_symbol,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
        )
        candidates = fit_alpha_candidates(
            cache,
            train_dates,
            target_symbol=target_symbol,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
            scalers=scalers,
            alphas=alphas,
        )
        selected_alphas, development_scores = (
            select_alphas(
                cache,
                development_dates,
                target_symbol=target_symbol,
                horizon_seconds=(
                    arguments.horizon_seconds
                ),
                candidate_states=candidates,
            )
        )

        print(
            f"{target_symbol}: selected alphas "
            f"{selected_alphas}",
            flush=True,
        )

        final_states = fit_final_states(
            cache,
            fit_dates,
            target_symbol=target_symbol,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
            selected_alphas=selected_alphas,
        )

        final_evaluation = evaluate_states(
            cache,
            final_test_dates,
            target_symbol=target_symbol,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
            states=final_states,
        )
        add_bootstrap(
            final_evaluation,
            bootstrap_samples=(
                arguments.bootstrap_samples
            ),
            seed_offset=(
                SYMBOLS.index(target_symbol) * 100
                + arguments.horizon_seconds
            ),
        )

        reference_dataset = build_feature_matrices(
            cache[fit_dates[0]],
            target_symbol=target_symbol,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
        )
        coefficients = {
            model_name: extract_raw_coefficients(
                final_states[model_name],
                reference_dataset.feature_names[
                    model_name
                ],
            )
            for model_name in MODEL_NAMES
        }

        output["targets"][target_symbol] = {
            "selected_alphas": selected_alphas,
            "development_mean_daily_ap": (
                development_scores
            ),
            "final_test": final_evaluation,
            "raw_scale_coefficients": coefficients,
        }

        no_j_ap = final_evaluation["bootstrap"][
            "rg_no_j_minus_m1"
        ]["average_precision"]
        j_ap = final_evaluation["bootstrap"][
            "rg_with_j_minus_no_j"
        ]["average_precision"]

        print(
            f"{target_symbol} H="
            f"{arguments.horizon_seconds}s "
            f"RG-noJ minus M1 AP="
            f"{no_j_ap['mean']:+.6f} "
            f"CI=[{no_j_ap['ci_025']:+.6f},"
            f"{no_j_ap['ci_975']:+.6f}] "
            f"RG-J minus RG-noJ AP="
            f"{j_ap['mean']:+.6f} "
            f"CI=[{j_ap['ci_025']:+.6f},"
            f"{j_ap['ci_975']:+.6f}]",
            flush=True,
        )

        write_json(arguments.output, output)

    write_json(arguments.output, output)


if __name__ == "__main__":
    main()
