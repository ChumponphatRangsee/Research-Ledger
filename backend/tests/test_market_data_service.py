import pytest

from app.services.market_data import (
    CompanyFinancialSnapshot,
    MarketDataService,
    ProviderUnavailableError,
)
from app.services.market_data.providers import YFinanceProvider


class RecordingProvider:
    def __init__(self, snapshot: CompanyFinancialSnapshot) -> None:
        self.snapshot = snapshot
        self.symbols: list[str] = []

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        self.symbols.append(symbol)
        return self.snapshot


class FailingProvider:
    def __init__(self, error: ProviderUnavailableError) -> None:
        self.error = error

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        raise self.error


def test_service_delegates_to_injected_provider():
    expected = CompanyFinancialSnapshot(symbol="MSFT", current_price=None)
    provider = RecordingProvider(expected)

    actual = MarketDataService(provider).get_company_snapshot("MSFT")

    assert actual is expected
    assert actual.current_price is None
    assert provider.symbols == ["MSFT"]


def test_service_preserves_structured_provider_failures():
    error = ProviderUnavailableError(
        "provider unavailable",
        provider="fake",
        symbol="FAIL",
    )

    with pytest.raises(ProviderUnavailableError) as caught:
        MarketDataService(FailingProvider(error)).get_company_snapshot("FAIL")

    assert caught.value is error


def test_service_defaults_to_yfinance_without_live_call(monkeypatch):
    expected = CompanyFinancialSnapshot(symbol="AAPL", market_cap=1_000)
    requested_symbols: list[str] = []

    def fake_snapshot(
        _provider: YFinanceProvider,
        symbol: str,
    ) -> CompanyFinancialSnapshot:
        requested_symbols.append(symbol)
        return expected

    monkeypatch.setattr(YFinanceProvider, "get_company_snapshot", fake_snapshot)

    actual = MarketDataService().get_company_snapshot("AAPL")

    assert actual is expected
    assert requested_symbols == ["AAPL"]
