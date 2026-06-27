from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
from clickhouse_driver import Client
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

from revolut_app.real_market.experiments.adverse_selection_oos import (
    DayData,
    EPS,
    SCALES,
    SEED,
    causal_imbalances,
    future_vwap_markout,
    load_day,
)

MODEL_NAMES = ("m0_single_scale", "m1_multiscale")
DEFAULT_CAPACITY_FRACTIONS = (0.01, 0.05, 0.10, 0.20)


@dataclass
class ModelState:
    scaler: StandardScaler
    classifier: SGDClassifier


@dataclass(frozen=True)
class EconomicDayData:
    features: dict[str, np.ndarray]
    labels: np.ndarray
    markout_bps: np.ndarray
    notional_usdt: np.ndarray
    adverse_loss_usdt: np.ndarray


@dataclass(frozen=True)
class CaptureMetrics:
    observations: int
    selected_observations: int
    selected_trade_fraction: float

    total_notional_usdt: float
    selected_notional_usdt: float
    selected_notional_fraction: float

    total_adverse_loss_usdt: float
    captured_adverse_loss_usdt: float
    capture_rate: float

    mean_loss_usdt: float
    selected_mean_loss_usdt: float
    loss_lift: float
    capture_lift_vs_random: float

    captured_loss_per_million_total_notional: float
    selected_loss_per_million_selected_notional: float

    oracle_captured_loss_usdt: float
    oracle_capture_rate: float
    oracle_efficiency: float


def clickhouse_client() -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default"),
    )


def date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date is before start date")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def model_state() -> ModelState:
    return ModelState(
        scaler=StandardScaler(),
        classifier=SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-4,
            learning_rate="optimal",
            average=True,
            random_state=SEED,
        ),
    )


def economic_feature_matrices(
    data: DayData,
    phi: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build only M0 and M1 to avoid the memory cost of the rejected M2 model."""
    sign = data.aggressor_sign.astype(np.float32, copy=False)
    phi32 = phi.astype(np.float32, copy=False)

    aligned = phi32 * sign[:, None]
    absolute = np.abs(phi32)
    q2 = phi32 * phi32
    q4 = q2 * q2
    log_notional = np.log1p(data.notional_usdt).astype(np.float32)[:, None]

    i16 = SCALES.index(16)

    m0 = np.column_stack(
        (
            log_notional[:, 0],
            aligned[:, i16],
            absolute[:, i16],
            q2[:, i16],
            q4[:, i16],
        )
    ).astype(np.float32, copy=False)

    m1 = np.column_stack(
        (
            log_notional,
            aligned,
            absolute,
            q2,
            q4,
        )
    ).astype(np.float32, copy=False)

    return {
        "m0_single_scale": m0,
        "m1_multiscale": m1,
    }


def adverse_loss_usdt(
    notional_usdt: np.ndarray,
    markout_bps: np.ndarray,
) -> np.ndarray:
    """Observed markout loss of a passive maker; non-toxic trades contribute zero."""
    if notional_usdt.shape != markout_bps.shape:
        raise ValueError("notional and markout shapes differ")
    return notional_usdt * np.maximum(markout_bps, 0.0) / 10_000.0


def economic_day_dataset(
    data: DayData,
    horizon_seconds: int,
    target_window_seconds: int,
) -> EconomicDayData:
    phi = causal_imbalances(data)
    markout = future_vwap_markout(
        data,
        horizon_seconds=horizon_seconds,
        window_seconds=target_window_seconds,
    )
    features = economic_feature_matrices(data, phi)

    valid = (
        np.all(np.isfinite(features["m1_multiscale"]), axis=1)
        & np.isfinite(markout)
        & np.isfinite(data.notional_usdt)
        & (data.notional_usdt > 0)
    )

    valid_markout = markout[valid].astype(np.float64, copy=False)
    valid_notional = data.notional_usdt[valid].astype(np.float64, copy=False)

    return EconomicDayData(
        features={name: matrix[valid] for name, matrix in features.items()},
        labels=(valid_markout > 0.0).astype(np.uint8),
        markout_bps=valid_markout,
        notional_usdt=valid_notional,
        adverse_loss_usdt=adverse_loss_usdt(valid_notional, valid_markout),
    )


def fit_models(
    ch: Client,
    symbol: str,
    train_dates: list[date],
    horizons_seconds: tuple[int, ...],
    target_window_seconds: int,
) -> dict[int, dict[str, ModelState]]:
    states = {
        horizon: {name: model_state() for name in MODEL_NAMES}
        for horizon in horizons_seconds
    }

    for pass_name in ("scaler", "classifier"):
        print(f"{symbol}: {pass_name} pass", flush=True)

        for trade_date in train_dates:
            data = load_day(ch, trade_date, symbol)
            print(f"{symbol} {trade_date}: rows={data.price.size}", flush=True)

            for horizon in horizons_seconds:
                dataset = economic_day_dataset(
                    data,
                    horizon_seconds=horizon,
                    target_window_seconds=target_window_seconds,
                )

                for model_name in MODEL_NAMES:
                    state = states[horizon][model_name]
                    x = dataset.features[model_name]

                    if pass_name == "scaler":
                        state.scaler.partial_fit(x)
                    else:
                        transformed = state.scaler.transform(x)
                        state.classifier.partial_fit(
                            transformed,
                            dataset.labels,
                            classes=np.array([0, 1], dtype=np.uint8),
                        )

    return states


def exact_top_fraction_mask(
    scores: np.ndarray,
    fraction: float,
) -> np.ndarray:
    if scores.ndim != 1:
        raise ValueError("scores must be one-dimensional")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    if scores.size == 0:
        raise ValueError("scores cannot be empty")

    selected_count = max(1, int(np.ceil(scores.size * fraction)))
    selected_indices = np.argpartition(scores, scores.size - selected_count)[
        scores.size - selected_count :
    ]

    mask = np.zeros(scores.size, dtype=bool)
    mask[selected_indices] = True
    return mask


def capture_metrics(
    *,
    scores: np.ndarray,
    losses_usdt: np.ndarray,
    notional_usdt: np.ndarray,
    capacity_fraction: float,
) -> CaptureMetrics:
    if not (scores.shape == losses_usdt.shape == notional_usdt.shape):
        raise ValueError("score, loss and notional shapes differ")
    if np.any(losses_usdt < 0):
        raise ValueError("losses must be non-negative")
    if np.any(notional_usdt <= 0):
        raise ValueError("notional must be positive")

    selected = exact_top_fraction_mask(scores, capacity_fraction)
    oracle_selected = exact_top_fraction_mask(losses_usdt, capacity_fraction)

    observations = int(scores.size)
    selected_observations = int(np.sum(selected))

    total_notional = float(np.sum(notional_usdt, dtype=np.float64))
    selected_notional = float(np.sum(notional_usdt[selected], dtype=np.float64))

    total_loss = float(np.sum(losses_usdt, dtype=np.float64))
    captured_loss = float(np.sum(losses_usdt[selected], dtype=np.float64))
    oracle_loss = float(np.sum(losses_usdt[oracle_selected], dtype=np.float64))

    mean_loss = total_loss / observations
    selected_mean_loss = captured_loss / selected_observations

    selected_trade_fraction = selected_observations / observations
    capture_rate = captured_loss / total_loss if total_loss > 0 else float("nan")
    oracle_capture_rate = oracle_loss / total_loss if total_loss > 0 else float("nan")

    return CaptureMetrics(
        observations=observations,
        selected_observations=selected_observations,
        selected_trade_fraction=float(selected_trade_fraction),
        total_notional_usdt=total_notional,
        selected_notional_usdt=selected_notional,
        selected_notional_fraction=(
            selected_notional / total_notional if total_notional > 0 else float("nan")
        ),
        total_adverse_loss_usdt=total_loss,
        captured_adverse_loss_usdt=captured_loss,
        capture_rate=capture_rate,
        mean_loss_usdt=float(mean_loss),
        selected_mean_loss_usdt=float(selected_mean_loss),
        loss_lift=(
            selected_mean_loss / mean_loss if mean_loss > 0 else float("nan")
        ),
        capture_lift_vs_random=(
            capture_rate / selected_trade_fraction
            if selected_trade_fraction > 0 and np.isfinite(capture_rate)
            else float("nan")
        ),
        captured_loss_per_million_total_notional=(
            captured_loss / total_notional * 1_000_000.0
            if total_notional > 0
            else float("nan")
        ),
        selected_loss_per_million_selected_notional=(
            captured_loss / selected_notional * 1_000_000.0
            if selected_notional > 0
            else float("nan")
        ),
        oracle_captured_loss_usdt=oracle_loss,
        oracle_capture_rate=oracle_capture_rate,
        oracle_efficiency=(
            captured_loss / oracle_loss if oracle_loss > 0 else float("nan")
        ),
    )


def paired_bootstrap(
    values: list[float],
    *,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    finite = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    if finite.size == 0:
        raise ValueError("no finite values for bootstrap")

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, finite.size, size=(samples, finite.size))
    means = np.mean(finite[indices], axis=1)

    return {
        "days": int(finite.size),
        "mean": float(np.mean(finite)),
        "ci_025": float(np.quantile(means, 0.025)),
        "ci_975": float(np.quantile(means, 0.975)),
        "positive_day_fraction": float(np.mean(finite > 0)),
    }


def aggregate_capture_metrics(
    daily_metrics: list[CaptureMetrics],
    *,
    capacity_fraction: float,
) -> dict[str, float | int]:
    observations = sum(metric.observations for metric in daily_metrics)
    selected_observations = sum(metric.selected_observations for metric in daily_metrics)
    total_notional = sum(metric.total_notional_usdt for metric in daily_metrics)
    selected_notional = sum(metric.selected_notional_usdt for metric in daily_metrics)
    total_loss = sum(metric.total_adverse_loss_usdt for metric in daily_metrics)
    captured_loss = sum(metric.captured_adverse_loss_usdt for metric in daily_metrics)
    oracle_loss = sum(metric.oracle_captured_loss_usdt for metric in daily_metrics)

    return {
        "days": len(daily_metrics),
        "capacity_fraction": capacity_fraction,
        "observations": observations,
        "selected_observations": selected_observations,
        "selected_trade_fraction": selected_observations / observations,
        "total_notional_usdt": total_notional,
        "selected_notional_usdt": selected_notional,
        "selected_notional_fraction": selected_notional / total_notional,
        "total_adverse_loss_usdt": total_loss,
        "captured_adverse_loss_usdt": captured_loss,
        "capture_rate": captured_loss / total_loss,
        "loss_lift": (captured_loss / selected_observations) / (total_loss / observations),
        "capture_lift_vs_random": (captured_loss / total_loss) / capacity_fraction,
        "captured_loss_per_million_total_notional": (
            captured_loss / total_notional * 1_000_000.0
        ),
        "selected_loss_per_million_selected_notional": (
            captured_loss / selected_notional * 1_000_000.0
        ),
        "oracle_captured_loss_usdt": oracle_loss,
        "oracle_capture_rate": oracle_loss / total_loss,
        "oracle_efficiency": captured_loss / oracle_loss,
    }


def evaluate_capture(
    ch: Client,
    *,
    symbol: str,
    test_dates: list[date],
    horizons_seconds: tuple[int, ...],
    target_window_seconds: int,
    capacity_fractions: tuple[float, ...],
    states: dict[int, dict[str, ModelState]],
    bootstrap_samples: int,
) -> dict[str, object]:
    result: dict[str, object] = {}

    for horizon in horizons_seconds:
        daily: list[dict[str, object]] = []

        for trade_date in test_dates:
            print(f"{symbol} capture H={horizon}s {trade_date}", flush=True)
            data = load_day(ch, trade_date, symbol)
            dataset = economic_day_dataset(
                data,
                horizon_seconds=horizon,
                target_window_seconds=target_window_seconds,
            )

            scores: dict[str, np.ndarray] = {}
            for model_name in MODEL_NAMES:
                state = states[horizon][model_name]
                transformed = state.scaler.transform(dataset.features[model_name])
                scores[model_name] = state.classifier.predict_proba(transformed)[:, 1]

            capacities: dict[str, object] = {}
            for fraction in capacity_fractions:
                key = f"{fraction:.6f}"
                model_metrics = {
                    model_name: capture_metrics(
                        scores=scores[model_name],
                        losses_usdt=dataset.adverse_loss_usdt,
                        notional_usdt=dataset.notional_usdt,
                        capacity_fraction=fraction,
                    )
                    for model_name in MODEL_NAMES
                }

                m0 = model_metrics["m0_single_scale"]
                m1 = model_metrics["m1_multiscale"]

                capacities[key] = {
                    "models": {
                        name: asdict(metric) for name, metric in model_metrics.items()
                    },
                    "m1_minus_m0": {
                        "captured_adverse_loss_usdt": (
                            m1.captured_adverse_loss_usdt
                            - m0.captured_adverse_loss_usdt
                        ),
                        "capture_rate": m1.capture_rate - m0.capture_rate,
                        "loss_lift": m1.loss_lift - m0.loss_lift,
                        "captured_loss_per_million_total_notional": (
                            m1.captured_loss_per_million_total_notional
                            - m0.captured_loss_per_million_total_notional
                        ),
                        "oracle_efficiency": (
                            m1.oracle_efficiency - m0.oracle_efficiency
                        ),
                    },
                }

            daily.append({"date": trade_date.isoformat(), "capacities": capacities})

        aggregate: dict[str, object] = {}
        bootstrap_result: dict[str, object] = {}

        for fraction in capacity_fractions:
            key = f"{fraction:.6f}"
            aggregate[key] = {
                model_name: aggregate_capture_metrics(
                    [
                        CaptureMetrics(**day["capacities"][key]["models"][model_name])
                        for day in daily
                    ],
                    capacity_fraction=fraction,
                )
                for model_name in MODEL_NAMES
            }

            bootstrap_result[key] = {}
            for metric_name in (
                "captured_adverse_loss_usdt",
                "capture_rate",
                "loss_lift",
                "captured_loss_per_million_total_notional",
                "oracle_efficiency",
            ):
                values = [
                    day["capacities"][key]["m1_minus_m0"][metric_name]
                    for day in daily
                ]
                bootstrap_result[key][metric_name] = paired_bootstrap(
                    values,
                    samples=bootstrap_samples,
                    seed=SEED + horizon + int(fraction * 10_000) + len(metric_name),
                )

        result[str(horizon)] = {
            "daily": daily,
            "aggregate": aggregate,
            "bootstrap": bootstrap_result,
        }

    return result


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_capacity(value: str) -> float:
    fraction = float(value)
    if not 0.0 < fraction <= 1.0:
        raise argparse.ArgumentTypeError("capacity must be in (0, 1]")
    return fraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--horizons-seconds", nargs="+", type=int, default=[1, 5])
    parser.add_argument("--target-window-seconds", type=int, default=1)
    parser.add_argument("--capacity-fractions", nargs="+", type=parse_capacity, default=list(DEFAULT_CAPACITY_FRACTIONS))
    parser.add_argument("--train-start", type=parse_date, required=True)
    parser.add_argument("--train-end", type=parse_date, required=True)
    parser.add_argument("--test-start", type=parse_date, required=True)
    parser.add_argument("--test-end", type=parse_date, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    train_dates = date_range(args.train_start, args.train_end)
    test_dates = date_range(args.test_start, args.test_end)
    if set(train_dates) & set(test_dates):
        raise ValueError("train and test date ranges overlap")

    horizons = tuple(sorted(set(args.horizons_seconds)))
    capacities = tuple(sorted(set(args.capacity_fractions)))

    ch = clickhouse_client()
    output: dict[str, object] = {
        "configuration": {
            "symbols": args.symbols,
            "horizons_seconds": horizons,
            "target_window_seconds": args.target_window_seconds,
            "capacity_fractions": capacities,
            "train_dates": [value.isoformat() for value in train_dates],
            "test_dates": [value.isoformat() for value in test_dates],
            "loss_definition": "notional_usdt * max(markout_bps, 0) / 10000",
            "selection_definition": "exact top-k by model score independently within each test day",
        },
        "symbols": {},
    }

    for symbol in args.symbols:
        states = fit_models(
            ch,
            symbol=symbol,
            train_dates=train_dates,
            horizons_seconds=horizons,
            target_window_seconds=args.target_window_seconds,
        )

        symbol_result = evaluate_capture(
            ch,
            symbol=symbol,
            test_dates=test_dates,
            horizons_seconds=horizons,
            target_window_seconds=args.target_window_seconds,
            capacity_fractions=capacities,
            states=states,
            bootstrap_samples=args.bootstrap_samples,
        )
        output["symbols"][symbol] = symbol_result

        for horizon in horizons:
            for fraction in capacities:
                key = f"{fraction:.6f}"
                boot = symbol_result[str(horizon)]["bootstrap"][key]
                delta_capture = boot["capture_rate"]
                delta_dollars = boot["captured_loss_per_million_total_notional"]
                print(
                    f"{symbol} H={horizon}s q={fraction:.0%} "
                    f"delta_capture_rate={delta_capture['mean']:+.6f} "
                    f"CI=[{delta_capture['ci_025']:+.6f},{delta_capture['ci_975']:+.6f}] "
                    f"delta_loss_per_$1m={delta_dollars['mean']:+.2f} "
                    f"CI=[{delta_dollars['ci_025']:+.2f},{delta_dollars['ci_975']:+.2f}]",
                    flush=True,
                )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
