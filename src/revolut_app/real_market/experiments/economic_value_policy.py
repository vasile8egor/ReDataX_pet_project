from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.preprocessing import StandardScaler

from revolut_app.real_market.experiments import coupled_business_value as business
from revolut_app.real_market.experiments import coupled_rg_final as coupled


DEFAULT_ALPHAS = (1e-4, 1e-3)
DEFAULT_TARGET_CLIPS_BPS = (5.0, 10.0, 20.0)
DEFAULT_NOTIONAL_WEIGHT_POWERS = (0.0, 0.5)
DEFAULT_NOTIONAL_BUDGETS = (0.005, 0.01, 0.02, 0.05, 0.10)
DEFAULT_MIN_NET_MARGINS_BPS = (0.0, 0.05, 0.10, 0.20)

POLICY_NAMES = (
    "no_action",
    "probability_budget",
    "economic_value_policy",
)


@dataclass(frozen=True)
class EconomicScenario:
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

    @property
    def protection_fraction(self) -> float:
        return self.mitigation_efficiency * self.internalization_rate


@dataclass(frozen=True)
class ValueModelSpec:
    alpha: float
    target_clip_bps: float
    notional_weight_power: float

    @property
    def model_id(self) -> str:
        return (
            f"alpha={self.alpha:g}|"
            f"clip={self.target_clip_bps:g}|"
            f"weight={self.notional_weight_power:g}"
        )


@dataclass(frozen=True)
class PolicySpec:
    notional_budget_fraction: float
    min_expected_net_margin_bps: float

    @property
    def policy_id(self) -> str:
        return (
            f"budget={self.notional_budget_fraction:g}|"
            f"margin={self.min_expected_net_margin_bps:g}"
        )


@dataclass
class ValueModelState:
    scaler: StandardScaler
    regressor: SGDRegressor
    spec: ValueModelSpec
    notional_scale: float


@dataclass
class ProbabilityState:
    scaler: StandardScaler
    classifier: SGDClassifier
    alpha: float


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
    model_spec: ValueModelSpec
    policy_spec: PolicySpec
    mean_daily_net_value_per_million: float
    median_daily_net_value_per_million: float
    std_daily_net_value_per_million: float
    worst_day_net_value_per_million: float
    positive_day_fraction: float
    robust_score: float
    development_profitable: bool


def parse_scenario(value: str) -> EconomicScenario:
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "scenario must be NAME:MITIGATION:INTERNALIZATION:ACTION_COST_BPS"
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


def parse_positive_float(value: str) -> float:
    result = float(value)
    if result <= 0.0:
        raise argparse.ArgumentTypeError("value must be positive")
    return result


def parse_non_negative_float(value: str) -> float:
    result = float(value)
    if result < 0.0:
        raise argparse.ArgumentTypeError("value cannot be negative")
    return result


def parse_fraction(value: str) -> float:
    result = float(value)
    if not 0.0 < result <= 1.0:
        raise argparse.ArgumentTypeError("fraction must be in (0, 1]")
    return result


def new_value_regressor(alpha: float) -> SGDRegressor:
    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    return SGDRegressor(
        loss="huber",
        epsilon=1.35,
        penalty="l2",
        alpha=alpha,
        learning_rate="invscaling",
        eta0=0.01,
        power_t=0.25,
        average=True,
        random_state=coupled.SEED,
        shuffle=True,
    )


def build_model_specs(
    alphas: Iterable[float],
    target_clips_bps: Iterable[float],
    notional_weight_powers: Iterable[float],
) -> tuple[ValueModelSpec, ...]:
    specs = tuple(
        ValueModelSpec(
            alpha=float(alpha),
            target_clip_bps=float(clip),
            notional_weight_power=float(power),
        )
        for alpha in sorted(set(alphas))
        for clip in sorted(set(target_clips_bps))
        for power in sorted(set(notional_weight_powers))
    )
    if not specs:
        raise ValueError("empty value-model grid")
    for spec in specs:
        if spec.alpha <= 0.0:
            raise ValueError("alpha must be positive")
        if spec.target_clip_bps <= 0.0:
            raise ValueError("target clip must be positive")
        if spec.notional_weight_power < 0.0:
            raise ValueError("notional weight power cannot be negative")
    return specs


def build_policy_specs(
    notional_budgets: Iterable[float],
    minimum_net_margins_bps: Iterable[float],
) -> tuple[PolicySpec, ...]:
    specs = tuple(
        PolicySpec(
            notional_budget_fraction=float(budget),
            min_expected_net_margin_bps=float(margin),
        )
        for budget in sorted(set(notional_budgets))
        for margin in sorted(set(minimum_net_margins_bps))
    )
    if not specs:
        raise ValueError("empty policy grid")
    for spec in specs:
        if not 0.0 < spec.notional_budget_fraction <= 1.0:
            raise ValueError("notional budget must be in (0, 1]")
        if spec.min_expected_net_margin_bps < 0.0:
            raise ValueError("minimum margin cannot be negative")
    return specs


def fit_feature_scaler(
    datasets: dict[date, business.BusinessDayDataset],
    dates: list[date],
) -> StandardScaler:
    scaler = StandardScaler()
    for trade_date in dates:
        scaler.partial_fit(datasets[trade_date].features["rg_no_j"])
    return scaler


def training_notional_scale(
    datasets: dict[date, business.BusinessDayDataset],
    dates: list[date],
) -> float:
    notionals = np.concatenate(
        [datasets[trade_date].notional_usdt for trade_date in dates]
    )
    median = float(np.median(notionals))
    if not np.isfinite(median) or median <= 0.0:
        raise ValueError("invalid training notional median")
    return median


def notional_sample_weights(
    notional_usdt: np.ndarray,
    *,
    scale: float,
    power: float,
) -> np.ndarray:
    if power == 0.0:
        return np.ones(notional_usdt.size, dtype=np.float64)
    weights = np.power(
        np.maximum(notional_usdt / scale, 1e-12),
        power,
    )
    # Large seconds must influence the fit, but cannot dominate it.
    return np.clip(weights, 0.25, 4.0).astype(np.float64)


def fit_value_candidates(
    datasets: dict[date, business.BusinessDayDataset],
    train_dates: list[date],
    specs: tuple[ValueModelSpec, ...],
) -> dict[str, ValueModelState]:
    scaler = fit_feature_scaler(datasets, train_dates)
    notional_scale = training_notional_scale(datasets, train_dates)

    states = {
        spec.model_id: ValueModelState(
            scaler=scaler,
            regressor=new_value_regressor(spec.alpha),
            spec=spec,
            notional_scale=notional_scale,
        )
        for spec in specs
    }

    for trade_date in train_dates:
        dataset = datasets[trade_date]
        transformed = scaler.transform(dataset.features["rg_no_j"])
        positive_markout = np.maximum(dataset.markout_bps, 0.0)

        weight_cache: dict[float, np.ndarray] = {}
        for spec in specs:
            if spec.notional_weight_power not in weight_cache:
                weight_cache[spec.notional_weight_power] = (
                    notional_sample_weights(
                        dataset.notional_usdt,
                        scale=notional_scale,
                        power=spec.notional_weight_power,
                    )
                )
            target = np.minimum(
                positive_markout,
                spec.target_clip_bps,
            )
            states[spec.model_id].regressor.partial_fit(
                transformed,
                target,
                sample_weight=weight_cache[spec.notional_weight_power],
            )

    return states


def fit_single_value_state(
    datasets: dict[date, business.BusinessDayDataset],
    fit_dates: list[date],
    spec: ValueModelSpec,
) -> ValueModelState:
    return fit_value_candidates(
        datasets,
        fit_dates,
        (spec,),
    )[spec.model_id]


def predict_positive_markout_bps(
    state: ValueModelState,
    features: np.ndarray,
) -> np.ndarray:
    transformed = state.scaler.transform(features)
    prediction = state.regressor.predict(transformed)
    return np.clip(
        prediction,
        0.0,
        state.spec.target_clip_bps,
    ).astype(np.float64)


def fit_probability_state(
    datasets: dict[date, business.BusinessDayDataset],
    fit_dates: list[date],
    *,
    alpha: float,
) -> ProbabilityState:
    scaler = fit_feature_scaler(datasets, fit_dates)
    classifier = coupled.new_classifier(alpha)
    classes = np.array([0, 1], dtype=np.uint8)

    for trade_date in fit_dates:
        dataset = datasets[trade_date]
        transformed = scaler.transform(dataset.features["rg_no_j"])
        labels = (dataset.markout_bps > 0.0).astype(np.uint8)
        classifier.partial_fit(
            transformed,
            labels,
            classes=classes,
        )

    return ProbabilityState(
        scaler=scaler,
        classifier=classifier,
        alpha=alpha,
    )


def predict_toxic_probability(
    state: ProbabilityState,
    features: np.ndarray,
) -> np.ndarray:
    transformed = state.scaler.transform(features)
    return state.classifier.predict_proba(transformed)[:, 1]


def fractional_notional_allocation(
    priority_score: np.ndarray,
    notional_usdt: np.ndarray,
    *,
    budget_fraction: float,
    eligible: np.ndarray | None = None,
) -> np.ndarray:
    """
    Fractional-knapsack allocation under a total-notional budget.

    `priority_score` is value per unit of notional. The last selected
    observation can be partially acted on, representing a partial hedge
    or another proportional intervention.
    """
    if priority_score.shape != notional_usdt.shape:
        raise ValueError("score and notional shapes differ")
    if priority_score.ndim != 1 or priority_score.size == 0:
        raise ValueError("allocation arrays must be non-empty vectors")
    if np.any(~np.isfinite(priority_score)):
        raise ValueError("priority score contains non-finite values")
    if np.any(~np.isfinite(notional_usdt)) or np.any(notional_usdt <= 0.0):
        raise ValueError("notional must be finite and positive")
    if not 0.0 <= budget_fraction <= 1.0:
        raise ValueError("budget fraction must be in [0, 1]")

    action_fraction = np.zeros(priority_score.size, dtype=np.float64)
    if budget_fraction == 0.0:
        return action_fraction

    if eligible is None:
        eligible = np.ones(priority_score.size, dtype=bool)
    if eligible.shape != priority_score.shape:
        raise ValueError("eligible mask shape differs")

    candidates = np.flatnonzero(eligible)
    if candidates.size == 0:
        return action_fraction

    order = candidates[
        np.argsort(priority_score[candidates], kind="stable")[::-1]
    ]
    total_budget = float(np.sum(notional_usdt)) * budget_fraction
    remaining = total_budget

    for index in order:
        if remaining <= 0.0:
            break
        amount = float(notional_usdt[index])
        fraction = min(1.0, remaining / amount)
        action_fraction[index] = fraction
        remaining -= fraction * amount

    return action_fraction


def economic_action_fractions(
    predicted_positive_markout_bps: np.ndarray,
    notional_usdt: np.ndarray,
    *,
    scenario: EconomicScenario,
    policy: PolicySpec,
) -> tuple[np.ndarray, np.ndarray]:
    predicted_gross_benefit_bps = (
        scenario.protection_fraction
        * predicted_positive_markout_bps
    )
    predicted_net_bps = (
        predicted_gross_benefit_bps
        - scenario.action_cost_bps
    )
    eligible = (
        predicted_net_bps
        >= policy.min_expected_net_margin_bps
    )
    allocation = fractional_notional_allocation(
        predicted_net_bps,
        notional_usdt,
        budget_fraction=policy.notional_budget_fraction,
        eligible=eligible,
    )
    return allocation, predicted_net_bps


def probability_action_fractions(
    probability: np.ndarray,
    notional_usdt: np.ndarray,
    *,
    notional_budget_fraction: float,
) -> np.ndarray:
    return fractional_notional_allocation(
        probability,
        notional_usdt,
        budget_fraction=notional_budget_fraction,
    )


def calculate_policy_metrics(
    *,
    action_fraction: np.ndarray,
    losses_usdt: np.ndarray,
    notional_usdt: np.ndarray,
    scenario: EconomicScenario,
) -> PolicyMetrics:
    if not (
        action_fraction.shape
        == losses_usdt.shape
        == notional_usdt.shape
    ):
        raise ValueError("policy metric array shapes differ")
    if np.any((action_fraction < 0.0) | (action_fraction > 1.0)):
        raise ValueError("action fractions must be in [0, 1]")
    if np.any(losses_usdt < 0.0):
        raise ValueError("losses cannot be negative")
    if np.any(notional_usdt <= 0.0):
        raise ValueError("notional must be positive")

    acted = action_fraction > 0.0
    observations = int(action_fraction.size)
    acted_observations = int(np.sum(acted))

    total_notional = float(np.sum(notional_usdt, dtype=np.float64))
    acted_notional = float(
        np.sum(action_fraction * notional_usdt, dtype=np.float64)
    )
    total_loss = float(np.sum(losses_usdt, dtype=np.float64))
    captured_loss = float(
        np.sum(action_fraction * losses_usdt, dtype=np.float64)
    )

    acted_event_fraction = acted_observations / observations
    mean_action_fraction = (
        float(np.mean(action_fraction[acted]))
        if acted_observations
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
        acted_notional * scenario.action_cost_bps / 10_000.0
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
    break_even_bps = (
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
        break_even_action_cost_bps=float(break_even_bps),
        benefit_cost_ratio=float(benefit_cost_ratio),
        profitable=bool(net_value > 0.0),
    )


def aggregate_policy_metrics(
    daily_metrics: list[PolicyMetrics],
    *,
    scenario: EconomicScenario,
) -> PolicyMetrics:
    if not daily_metrics:
        raise ValueError("daily metrics cannot be empty")

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

    # Reconstruct an equivalent aggregate without retaining all events.
    acted_event_fraction = acted_observations / observations
    acted_notional_fraction = acted_notional / total_notional
    capture_rate = captured_loss / total_loss if total_loss > 0.0 else 0.0
    risk_concentration = (
        capture_rate / acted_notional_fraction
        if acted_notional_fraction > 0.0
        else 0.0
    )
    gross_value = scenario.protection_fraction * captured_loss
    action_cost = (
        acted_notional * scenario.action_cost_bps / 10_000.0
    )
    net_value = gross_value - action_cost

    weighted_action_numerator = sum(
        item.mean_action_fraction_on_acted_events
        * item.acted_observations
        for item in daily_metrics
    )
    mean_action_fraction = (
        weighted_action_numerator / acted_observations
        if acted_observations
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
        ),
        net_value_per_million_usdt=float(
            net_value / total_notional * 1_000_000.0
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
    model_spec: ValueModelSpec,
    policy_spec: PolicySpec,
    daily_metrics: list[PolicyMetrics],
    risk_penalty: float,
    minimum_positive_day_fraction: float,
) -> CandidateSummary:
    values = np.asarray(
        [item.net_value_per_million_usdt for item in daily_metrics],
        dtype=np.float64,
    )
    mean = float(np.mean(values))
    median = float(np.median(values))
    standard_deviation = float(np.std(values, ddof=0))
    worst = float(np.min(values))
    positive_fraction = float(np.mean(values > 0.0))
    robust_score = mean - risk_penalty * standard_deviation

    profitable = bool(
        mean > 0.0
        and robust_score > 0.0
        and positive_fraction >= minimum_positive_day_fraction
    )

    return CandidateSummary(
        model_spec=model_spec,
        policy_spec=policy_spec,
        mean_daily_net_value_per_million=mean,
        median_daily_net_value_per_million=median,
        std_daily_net_value_per_million=standard_deviation,
        worst_day_net_value_per_million=worst,
        positive_day_fraction=positive_fraction,
        robust_score=float(robust_score),
        development_profitable=profitable,
    )


def select_candidate(
    candidates: list[CandidateSummary],
) -> CandidateSummary | None:
    profitable = [
        item for item in candidates if item.development_profitable
    ]
    if not profitable:
        return None

    # Prefer robust value, then lower capital usage and a larger margin.
    return max(
        profitable,
        key=lambda item: (
            item.robust_score,
            item.mean_daily_net_value_per_million,
            -item.policy_spec.notional_budget_fraction,
            item.policy_spec.min_expected_net_margin_bps,
        ),
    )


def paired_day_bootstrap(
    daily_differences: list[float],
    *,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    values = np.asarray(daily_differences, dtype=np.float64)
    if values.size == 0 or np.any(~np.isfinite(values)):
        raise ValueError("bootstrap values must be finite and non-empty")
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
        "ci_025": float(np.quantile(means, 0.025)),
        "ci_975": float(np.quantile(means, 0.975)),
        "positive_day_fraction": float(np.mean(values > 0.0)),
    }


def load_target_datasets(
    clickhouse: Any,
    dates: list[date],
    *,
    target_symbol: str,
    market_cache: dict[date, coupled.MarketDay],
) -> dict[date, business.BusinessDayDataset]:
    datasets: dict[date, business.BusinessDayDataset] = {}
    for trade_date in dates:
        print(
            f"{target_symbol}: building economic dataset {trade_date}",
            flush=True,
        )
        second_notional = business.load_second_notional(
            clickhouse,
            trade_date,
        )
        datasets[trade_date] = business.build_business_day_dataset(
            market_cache[trade_date],
            second_notional,
            target_symbol=target_symbol,
            horizon_seconds=5,
        )
    return datasets


def evaluate_value_candidate_on_dates(
    *,
    state: ValueModelState,
    policy_spec: PolicySpec,
    datasets: dict[date, business.BusinessDayDataset],
    dates: list[date],
    scenario: EconomicScenario,
) -> list[PolicyMetrics]:
    output: list[PolicyMetrics] = []
    for trade_date in dates:
        dataset = datasets[trade_date]
        prediction = predict_positive_markout_bps(
            state,
            dataset.features["rg_no_j"],
        )
        action_fraction, _ = economic_action_fractions(
            prediction,
            dataset.notional_usdt,
            scenario=scenario,
            policy=policy_spec,
        )
        output.append(
            calculate_policy_metrics(
                action_fraction=action_fraction,
                losses_usdt=dataset.adverse_loss_usdt,
                notional_usdt=dataset.notional_usdt,
                scenario=scenario,
            )
        )
    return output


def evaluate_final_policies(
    *,
    value_state: ValueModelState | None,
    probability_state: ProbabilityState,
    policy_spec: PolicySpec | None,
    datasets: dict[date, business.BusinessDayDataset],
    final_dates: list[date],
    scenario: EconomicScenario,
    bootstrap_samples: int,
) -> dict[str, Any]:
    daily_output: list[dict[str, Any]] = []
    collected: dict[str, list[PolicyMetrics]] = {
        name: [] for name in POLICY_NAMES
    }

    for trade_date in final_dates:
        dataset = datasets[trade_date]
        zero_action = np.zeros(
            dataset.notional_usdt.size,
            dtype=np.float64,
        )
        no_action_metrics = calculate_policy_metrics(
            action_fraction=zero_action,
            losses_usdt=dataset.adverse_loss_usdt,
            notional_usdt=dataset.notional_usdt,
            scenario=scenario,
        )

        if policy_spec is None or value_state is None:
            probability_action = zero_action
            value_action = zero_action
        else:
            probability = predict_toxic_probability(
                probability_state,
                dataset.features["rg_no_j"],
            )
            probability_action = probability_action_fractions(
                probability,
                dataset.notional_usdt,
                notional_budget_fraction=(
                    policy_spec.notional_budget_fraction
                ),
            )
            predicted_loss = predict_positive_markout_bps(
                value_state,
                dataset.features["rg_no_j"],
            )
            value_action, _ = economic_action_fractions(
                predicted_loss,
                dataset.notional_usdt,
                scenario=scenario,
                policy=policy_spec,
            )

        probability_metrics = calculate_policy_metrics(
            action_fraction=probability_action,
            losses_usdt=dataset.adverse_loss_usdt,
            notional_usdt=dataset.notional_usdt,
            scenario=scenario,
        )
        value_metrics = calculate_policy_metrics(
            action_fraction=value_action,
            losses_usdt=dataset.adverse_loss_usdt,
            notional_usdt=dataset.notional_usdt,
            scenario=scenario,
        )

        policy_metrics = {
            "no_action": no_action_metrics,
            "probability_budget": probability_metrics,
            "economic_value_policy": value_metrics,
        }
        for name, metrics in policy_metrics.items():
            collected[name].append(metrics)

        daily_output.append(
            {
                "date": trade_date.isoformat(),
                "policies": {
                    name: asdict(metrics)
                    for name, metrics in policy_metrics.items()
                },
                "comparisons": {
                    "value_minus_probability": {
                        "net_value_per_million_usdt": (
                            value_metrics.net_value_per_million_usdt
                            - probability_metrics.net_value_per_million_usdt
                        )
                    },
                    "value_minus_no_action": {
                        "net_value_per_million_usdt": (
                            value_metrics.net_value_per_million_usdt
                        )
                    },
                },
            }
        )

    aggregate = {
        name: asdict(
            aggregate_policy_metrics(metrics, scenario=scenario)
        )
        for name, metrics in collected.items()
    }

    bootstrap = {}
    for comparison in (
        "value_minus_probability",
        "value_minus_no_action",
    ):
        values = [
            day["comparisons"][comparison][
                "net_value_per_million_usdt"
            ]
            for day in daily_output
        ]
        bootstrap[comparison] = paired_day_bootstrap(
            values,
            samples=bootstrap_samples,
            seed=coupled.SEED + len(comparison),
        )

    return {
        "daily": daily_output,
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


def validate_splits(
    train_dates: list[date],
    development_dates: list[date],
    final_dates: list[date],
) -> None:
    combined = train_dates + development_dates + final_dates
    if len(set(combined)) != len(combined):
        raise ValueError("train, development and final dates overlap")
    if not train_dates or not development_dates or not final_dates:
        raise ValueError("all temporal splits must be non-empty")
    if max(train_dates) >= min(development_dates):
        raise ValueError("development must follow training")
    if max(development_dates) >= min(final_dates):
        raise ValueError("final test must follow development")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train an RG-noJ expected-loss model and select an "
            "economically rational notional-constrained intervention "
            "policy on development data."
        )
    )
    parser.add_argument("--target-symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--train-start", type=date.fromisoformat, required=True)
    parser.add_argument("--train-end", type=date.fromisoformat, required=True)
    parser.add_argument("--development-start", type=date.fromisoformat, required=True)
    parser.add_argument("--development-end", type=date.fromisoformat, required=True)
    parser.add_argument("--final-test-start", type=date.fromisoformat, required=True)
    parser.add_argument("--final-test-end", type=date.fromisoformat, required=True)

    parser.add_argument(
        "--scenario",
        type=parse_scenario,
        default=parse_scenario("base:0.50:0.25:0.50"),
    )
    parser.add_argument(
        "--alphas",
        nargs="+",
        type=parse_positive_float,
        default=list(DEFAULT_ALPHAS),
    )
    parser.add_argument(
        "--target-clips-bps",
        nargs="+",
        type=parse_positive_float,
        default=list(DEFAULT_TARGET_CLIPS_BPS),
    )
    parser.add_argument(
        "--notional-weight-powers",
        nargs="+",
        type=parse_non_negative_float,
        default=list(DEFAULT_NOTIONAL_WEIGHT_POWERS),
    )
    parser.add_argument(
        "--notional-budget-fractions",
        nargs="+",
        type=parse_fraction,
        default=list(DEFAULT_NOTIONAL_BUDGETS),
    )
    parser.add_argument(
        "--minimum-net-margins-bps",
        nargs="+",
        type=parse_non_negative_float,
        default=list(DEFAULT_MIN_NET_MARGINS_BPS),
    )
    parser.add_argument("--probability-alpha", type=parse_positive_float, default=1e-3)
    parser.add_argument("--risk-penalty", type=parse_non_negative_float, default=0.50)
    parser.add_argument(
        "--minimum-positive-day-fraction",
        type=parse_fraction,
        default=5.0 / 7.0,
    )
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()

    train_dates = coupled.date_range(arguments.train_start, arguments.train_end)
    development_dates = coupled.date_range(
        arguments.development_start,
        arguments.development_end,
    )
    final_dates = coupled.date_range(
        arguments.final_test_start,
        arguments.final_test_end,
    )
    validate_splits(train_dates, development_dates, final_dates)

    targets = tuple(dict.fromkeys(arguments.target_symbols))
    invalid = [item for item in targets if item not in coupled.TARGET_SYMBOLS]
    if invalid:
        raise ValueError(f"unsupported target symbols: {invalid}")

    model_specs = build_model_specs(
        arguments.alphas,
        arguments.target_clips_bps,
        arguments.notional_weight_powers,
    )
    policy_specs = build_policy_specs(
        arguments.notional_budget_fractions,
        arguments.minimum_net_margins_bps,
    )
    scenario: EconomicScenario = arguments.scenario

    clickhouse = coupled.create_client()
    all_dates = train_dates + development_dates + final_dates
    market_cache: dict[date, coupled.MarketDay] = {}
    for trade_date in all_dates:
        print(f"Loading synchronized market day {trade_date}", flush=True)
        market_cache[trade_date] = coupled.load_market_day(
            clickhouse,
            trade_date,
        )

    output: dict[str, Any] = {
        "configuration": {
            "targets": list(targets),
            "feature_model": "rg_no_j",
            "prediction_target": "positive aggressor-aligned markout in bps",
            "decision_rule": (
                "predicted protection_fraction * positive_markout_bps "
                "- action_cost_bps; act only above selected safety margin"
            ),
            "capital_constraint": "fraction of total daily target-market notional",
            "partial_action_interpretation": "partial hedge or proportional intervention",
            "scenario": asdict(scenario),
            "train_dates": [item.isoformat() for item in train_dates],
            "development_dates": [item.isoformat() for item in development_dates],
            "final_test_dates": [item.isoformat() for item in final_dates],
            "candidate_value_models": [asdict(item) for item in model_specs],
            "candidate_policies": [asdict(item) for item in policy_specs],
            "risk_penalty": arguments.risk_penalty,
            "minimum_positive_day_fraction": (
                arguments.minimum_positive_day_fraction
            ),
            "fallback": (
                "no_action when no development candidate has positive "
                "risk-adjusted value"
            ),
            "interpretation": (
                "scenario-adjusted potential value, not realized bank PnL"
            ),
        },
        "targets": {},
    }

    for target_symbol in targets:
        print(f"{target_symbol}: loading target datasets", flush=True)
        datasets = load_target_datasets(
            clickhouse,
            all_dates,
            target_symbol=target_symbol,
            market_cache=market_cache,
        )

        print(f"{target_symbol}: fitting value-model candidates", flush=True)
        candidate_states = fit_value_candidates(
            datasets,
            train_dates,
            model_specs,
        )

        leaderboard: list[CandidateSummary] = []
        for state in candidate_states.values():
            for policy_spec in policy_specs:
                daily_metrics = evaluate_value_candidate_on_dates(
                    state=state,
                    policy_spec=policy_spec,
                    datasets=datasets,
                    dates=development_dates,
                    scenario=scenario,
                )
                leaderboard.append(
                    summarize_candidate(
                        model_spec=state.spec,
                        policy_spec=policy_spec,
                        daily_metrics=daily_metrics,
                        risk_penalty=arguments.risk_penalty,
                        minimum_positive_day_fraction=(
                            arguments.minimum_positive_day_fraction
                        ),
                    )
                )

        selected = select_candidate(leaderboard)
        leaderboard_sorted = sorted(
            leaderboard,
            key=lambda item: item.robust_score,
            reverse=True,
        )

        if selected is None:
            print(
                f"{target_symbol}: no robust profitable development policy; "
                "falling back to no_action",
                flush=True,
            )
            final_value_state = None
            selected_policy = None
        else:
            print(
                f"{target_symbol}: selected {selected.model_spec.model_id} "
                f"{selected.policy_spec.policy_id}; "
                f"development mean="
                f"{selected.mean_daily_net_value_per_million:+.4f} "
                f"robust={selected.robust_score:+.4f}",
                flush=True,
            )
            final_value_state = fit_single_value_state(
                datasets,
                train_dates + development_dates,
                selected.model_spec,
            )
            selected_policy = selected.policy_spec

        probability_state = fit_probability_state(
            datasets,
            train_dates + development_dates,
            alpha=arguments.probability_alpha,
        )
        final_evaluation = evaluate_final_policies(
            value_state=final_value_state,
            probability_state=probability_state,
            policy_spec=selected_policy,
            datasets=datasets,
            final_dates=final_dates,
            scenario=scenario,
            bootstrap_samples=arguments.bootstrap_samples,
        )

        target_output = {
            "selected_candidate": (
                asdict(selected) if selected is not None else None
            ),
            "development_status": (
                "profitable_policy_selected"
                if selected is not None
                else "no_action_fallback"
            ),
            "development_leaderboard_top20": [
                asdict(item) for item in leaderboard_sorted[:20]
            ],
            "final_test": final_evaluation,
        }
        output["targets"][target_symbol] = target_output
        write_json(arguments.output, output)

        aggregate = final_evaluation["aggregate"]["economic_value_policy"]
        bootstrap = final_evaluation["bootstrap"]["value_minus_no_action"]
        print(
            f"{target_symbol}: final net value="
            f"{aggregate['net_value_per_million_usdt']:+.4f} USDT/$1M; "
            f"CI=[{bootstrap['ci_025']:+.4f}, "
            f"{bootstrap['ci_975']:+.4f}]; "
            f"positive days={bootstrap['positive_day_fraction']:.2%}",
            flush=True,
        )

    write_json(arguments.output, output)


if __name__ == "__main__":
    main()
