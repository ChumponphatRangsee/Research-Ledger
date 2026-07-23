"""Reusable bounded scoring primitives and configuration-driven strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.screening.models import (
    BusinessModel,
    CategoryScore,
    FinancialMetrics,
    MetricScore,
)


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def score_higher_is_better(value: float, weak: float, strong: float) -> float:
    if strong <= weak:
        raise ValueError("strong threshold must exceed weak threshold")
    return clamp_score((value - weak) / (strong - weak) * 100.0)


def score_lower_is_better(value: float, strong: float, weak: float) -> float:
    if weak <= strong:
        raise ValueError("weak threshold must exceed strong threshold")
    return clamp_score((weak - value) / (weak - strong) * 100.0)


def score_range(
    value: float,
    lower_bound: float,
    ideal_low: float,
    ideal_high: float,
    upper_bound: float,
) -> float:
    if not lower_bound <= ideal_low <= ideal_high <= upper_bound:
        raise ValueError("range thresholds must be ordered")
    if ideal_low <= value <= ideal_high:
        return 100.0
    if value < ideal_low:
        return score_higher_is_better(value, lower_bound, ideal_low)
    return score_lower_is_better(value, ideal_high, upper_bound)


def weighted_average(values: list[tuple[float | None, float]]) -> float | None:
    available = [(value, weight) for value, weight in values if value is not None and weight > 0]
    if not available:
        return None
    denominator = sum(weight for _, weight in available)
    return clamp_score(sum(value * weight for value, weight in available) / denominator)


@dataclass(frozen=True)
class MetricRule:
    field: str
    label: str
    direction: Literal["higher", "lower", "range"]
    weak: float
    strong: float
    ideal_high: float | None = None
    upper_bound: float | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class StrategyDefinition:
    business_model: BusinessModel
    category_weights: dict[str, float]
    rules: dict[str, tuple[MetricRule, ...]]
    minimum_available_metrics: int = 3
    required_categories: tuple[str, ...] = ()
    required_category_groups: tuple[tuple[str, ...], ...] = ()
    incomplete_data_reason: str | None = None

    @property
    def expected_fields(self) -> set[str]:
        return {rule.field for rules in self.rules.values() for rule in rules}


def _describe_metric(rule: MetricRule, value: float, score: float) -> str:
    if score >= 75:
        qualifier = "strong"
    elif score <= 35:
        qualifier = "weak"
    else:
        qualifier = "moderate"
    return f"{rule.label} is {qualifier} ({value:.2f})"


def score_metric(metrics: FinancialMetrics, rule: MetricRule) -> MetricScore:
    value = getattr(metrics, rule.field)
    if value is None:
        return MetricScore(
            score=None,
            available=False,
            value=None,
            reason=f"{rule.label} unavailable from provider",
        )

    if rule.direction == "higher":
        score = score_higher_is_better(value, rule.weak, rule.strong)
    elif rule.direction == "lower":
        score = score_lower_is_better(value, rule.strong, rule.weak)
    else:
        if rule.ideal_high is None or rule.upper_bound is None:
            raise ValueError(f"Incomplete range rule for {rule.field}")
        score = score_range(value, rule.weak, rule.strong, rule.ideal_high, rule.upper_bound)

    score = round(score, 2)
    return MetricScore(
        score=score,
        available=True,
        value=value,
        reason=_describe_metric(rule, value, score),
    )


def calculate_strategy_scores(
    metrics: FinancialMetrics,
    definition: StrategyDefinition,
    low_confidence_warning_threshold: float = 60.0,
) -> tuple[float | None, float, dict[str, CategoryScore], list[str], list[str]]:
    """Score available data and calculate confidence independently of quality."""
    breakdown: dict[str, CategoryScore] = {}
    scored_metrics: list[tuple[MetricRule, MetricScore]] = []

    for category, category_weight in definition.category_weights.items():
        metric_results: dict[str, MetricScore] = {}
        weighted: list[tuple[float | None, float]] = []
        for rule in definition.rules.get(category, ()):
            result = score_metric(metrics, rule)
            metric_results[rule.field] = result
            weighted.append((result.score, rule.weight))
            scored_metrics.append((rule, result))
        breakdown[category] = CategoryScore(
            score=weighted_average(weighted),
            weight=category_weight,
            metrics=metric_results,
        )

    total = weighted_average(
        [(category.score, category.weight) for category in breakdown.values()]
    )
    expected = definition.expected_fields
    available = sum(getattr(metrics, field) is not None for field in expected)
    confidence = round(100.0 * available / len(expected), 2) if expected else 0.0

    unique_results: dict[str, tuple[MetricRule, MetricScore]] = {}
    for rule, result in scored_metrics:
        previous = unique_results.get(rule.field)
        if previous is None or (result.score or -1) > (previous[1].score or -1):
            unique_results[rule.field] = (rule, result)

    available_results = [item for item in unique_results.values() if item[1].available]
    strengths = [
        result.reason
        for _, result in sorted(
            available_results, key=lambda item: item[1].score or 0, reverse=True
        )
        if (result.score or 0) >= 75
    ][:4]
    warnings = [
        result.reason
        for _, result in sorted(available_results, key=lambda item: item[1].score or 0)
        if result.score is not None and result.score <= 35
    ][:4]
    if confidence < low_confidence_warning_threshold:
        warnings.append(f"Low data completeness ({confidence:.0f}% confidence)")

    return (
        round(total, 2) if total is not None else None,
        confidence,
        breakdown,
        strengths,
        warnings,
    )
