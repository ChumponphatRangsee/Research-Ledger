"""Compatibility normalization API for quantitative screening."""

from typing import Any

from app.services.market_data.normalization import (
    finite_float,
    normalize_company_snapshot,
    ratio_from_percent,
)
from app.services.screening.models import FinancialMetrics


def normalize_financial_metrics(raw: dict[str, Any]) -> FinancialMetrics:
    """Normalize through the provider-neutral market data boundary."""
    return normalize_company_snapshot(raw)


__all__ = [
    "finite_float",
    "normalize_financial_metrics",
    "ratio_from_percent",
]

