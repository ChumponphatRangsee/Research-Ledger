"""Conservative eligibility checks kept separate from scoring."""

from __future__ import annotations

from app.services.screening.models import BusinessModel, FinancialMetrics
from app.services.screening.scoring import StrategyDefinition


def eligibility_failures(
    metrics: FinancialMetrics,
    business_model: BusinessModel,
    strategy: StrategyDefinition | None,
    min_market_cap: float,
) -> list[str]:
    failures: list[str] = []
    if metrics.market_cap is None:
        failures.append("Market capitalization unavailable")
    elif metrics.market_cap < min_market_cap:
        failures.append(
            f"Market capitalization is below configured minimum ({min_market_cap:,.0f})"
        )
    if metrics.current_price is None or metrics.current_price <= 0:
        failures.append("Current price is missing or invalid")
    if business_model == BusinessModel.UNSUPPORTED or strategy is None:
        failures.append("Unsupported business model")
    elif (
        sum(getattr(metrics, field) is not None for field in strategy.expected_fields)
        < strategy.minimum_available_metrics
    ):
        failures.append("Insufficient financial data")
    return failures

