"""Sector-aware deterministic screening orchestration."""

from __future__ import annotations

from app.services.screening.classifier import classify_business_model
from app.services.screening.filters import eligibility_failures
from app.services.screening.models import FinancialMetrics, ScreeningResult
from app.services.screening.scoring import calculate_strategy_scores
from app.services.screening.strategies import resolve_strategy


class ScreeningEngine:
    """Classify, validate, score, and explain one normalized company."""

    def __init__(self, min_market_cap: float, min_score: float = 55.0):
        self.min_market_cap = min_market_cap
        self.min_score = min_score

    def screen(self, metrics: FinancialMetrics) -> ScreeningResult:
        business_model = classify_business_model(metrics)
        strategy = resolve_strategy(business_model)
        failures = eligibility_failures(
            metrics,
            business_model,
            strategy,
            self.min_market_cap,
        )
        metric_payload = metrics.model_dump(mode="json", exclude={"data_as_of"})

        if failures:
            expected = strategy.expected_fields if strategy else set()
            available = sum(getattr(metrics, field) is not None for field in expected)
            confidence = round(100 * available / len(expected), 2) if expected else 0.0
            return ScreeningResult(
                symbol=metrics.symbol,
                name=metrics.name,
                sector=metrics.sector,
                industry=metrics.industry,
                business_model=business_model,
                passed=False,
                confidence=confidence,
                failure_reasons=failures,
                metrics=metric_payload,
                data_as_of=metrics.data_as_of,
            )

        assert strategy is not None
        score, confidence, breakdown, strengths, warnings = calculate_strategy_scores(
            metrics, strategy
        )
        category_scores = {
            category: detail.score for category, detail in breakdown.items()
        }
        passed = score is not None and score >= self.min_score
        if not passed:
            failures.append(
                f"Quantitative score {score:.1f} is below configured minimum "
                f"{self.min_score:.1f}"
                if score is not None
                else "No score could be calculated"
            )

        return ScreeningResult(
            symbol=metrics.symbol,
            name=metrics.name,
            sector=metrics.sector,
            industry=metrics.industry,
            business_model=business_model,
            passed=passed,
            score=score,
            confidence=confidence,
            category_scores=category_scores,
            score_breakdown=breakdown,
            strengths=strengths,
            warnings=warnings,
            failure_reasons=failures,
            metrics=metric_payload,
            data_as_of=metrics.data_as_of,
        )
