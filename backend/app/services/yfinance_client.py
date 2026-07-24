"""Legacy compatibility facade for the canonical yfinance provider."""

from typing import Any

from app.services.market_data.providers.yfinance import YFinanceProvider

_provider = YFinanceProvider()


def fetch_financial_metrics(symbol: str) -> dict[str, Any]:
    """Return the legacy raw mapping through the canonical provider adapter."""
    return _provider.get_legacy_financial_metrics(symbol)
