"""Application-level access to normalized market data."""

from app.services.market_data.models import CompanyFinancialSnapshot
from app.services.market_data.provider import MarketDataProvider


class MarketDataService:
    """Retrieve normalized snapshots through an injected market data provider."""

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        if provider is None:
            from app.services.market_data.providers import YFinanceProvider

            provider = YFinanceProvider()
        self._provider = provider

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        """Return the provider's normalized company snapshot."""
        return self._provider.get_company_snapshot(symbol)
