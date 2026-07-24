"""Market data provider boundary."""

from typing import Protocol, runtime_checkable

from app.services.market_data.models import CompanyFinancialSnapshot


@runtime_checkable
class MarketDataProvider(Protocol):
    """Structural interface implemented by market data adapters."""

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        """Return a normalized company/financial snapshot for ``symbol``."""

        ...
