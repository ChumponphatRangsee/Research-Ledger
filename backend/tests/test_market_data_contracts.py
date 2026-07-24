from datetime import datetime, timezone

from app.services.market_data import (
    CompanyFinancialSnapshot,
    InvalidProviderResponseError,
    MarketDataProvider,
    MarketDataProviderError,
    ProviderRateLimitError,
)
from app.services.screening.models import FinancialMetrics


class StubProvider:
    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        return CompanyFinancialSnapshot(symbol=symbol, current_price=123.45)


def test_company_snapshot_preserves_missing_metrics_as_none():
    observed_at = datetime(2026, 7, 24, tzinfo=timezone.utc)

    snapshot = CompanyFinancialSnapshot(
        symbol="MSFT",
        market_cap=3_000_000_000_000,
        data_as_of=observed_at,
    )

    assert snapshot.market_cap == 3_000_000_000_000
    assert snapshot.current_price is None
    assert snapshot.roe is None
    assert snapshot.data_as_of == observed_at
    assert snapshot.model_dump()["current_price"] is None


def test_screening_financial_metrics_uses_canonical_market_data_model():
    assert FinancialMetrics is CompanyFinancialSnapshot


def test_provider_protocol_accepts_structural_implementation():
    provider = StubProvider()

    assert isinstance(provider, MarketDataProvider)
    assert provider.get_company_snapshot("AAPL") == CompanyFinancialSnapshot(
        symbol="AAPL",
        current_price=123.45,
    )


def test_provider_errors_have_stable_types_and_context():
    error = ProviderRateLimitError(
        "Request quota exceeded",
        provider="stub",
        symbol="NVDA",
    )

    assert isinstance(error, MarketDataProviderError)
    assert error.provider == "stub"
    assert error.symbol == "NVDA"
    assert str(error) == "Request quota exceeded"
    assert issubclass(InvalidProviderResponseError, MarketDataProviderError)
