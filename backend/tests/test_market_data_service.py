from datetime import datetime, timedelta, timezone

import pytest

from app.services.market_data import (
    CompanyFinancialSnapshot,
    MarketDataService,
    ProviderUnavailableError,
)
from app.services.market_data.providers import YFinanceProvider


class RecordingProvider:
    provider_name = "fake"

    def __init__(self, snapshot: CompanyFinancialSnapshot) -> None:
        self.snapshot = snapshot
        self.symbols: list[str] = []

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        self.symbols.append(symbol)
        return self.snapshot


class FailingProvider:
    provider_name = "fake"

    def __init__(self, error: ProviderUnavailableError) -> None:
        self.error = error
        self.symbols: list[str] = []

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        self.symbols.append(symbol)
        raise self.error


class RecordingCache:
    def __init__(
        self,
        snapshot: CompanyFinancialSnapshot | None = None,
        *,
        expires_at: datetime | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.expires_at = expires_at
        self.lookups: list[tuple[str, str, datetime]] = []
        self.upserts: list[
            tuple[CompanyFinancialSnapshot, str, datetime, datetime]
        ] = []

    def get_fresh_company_snapshot(
        self,
        symbol: str,
        provider: str,
        *,
        now: datetime,
    ) -> CompanyFinancialSnapshot | None:
        self.lookups.append((symbol, provider, now))
        if self.expires_at is not None and self.expires_at <= now:
            return None
        return self.snapshot

    def upsert_company_snapshot(
        self,
        snapshot: CompanyFinancialSnapshot,
        provider: str,
        *,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.upserts.append((snapshot, provider, fetched_at, expires_at))


NOW = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)


def test_service_returns_fresh_cached_snapshot_without_calling_provider():
    cached = CompanyFinancialSnapshot(symbol="MSFT", current_price=420)
    provider = RecordingProvider(
        CompanyFinancialSnapshot(symbol="MSFT", current_price=999)
    )
    cache = RecordingCache(cached, expires_at=NOW + timedelta(minutes=1))

    actual = MarketDataService(
        provider,
        cache=cache,
        clock=lambda: NOW,
    ).get_company_snapshot(" msft ")

    assert actual is cached
    assert provider.symbols == []
    assert cache.lookups == [("MSFT", "fake", NOW)]
    assert cache.upserts == []


def test_service_calls_provider_and_upserts_on_cache_miss():
    expected = CompanyFinancialSnapshot(symbol="MSFT", current_price=None)
    provider = RecordingProvider(expected)
    cache = RecordingCache()

    actual = MarketDataService(
        provider,
        cache=cache,
        clock=lambda: NOW,
    ).get_company_snapshot("MSFT")

    assert actual is expected
    assert actual.current_price is None
    assert provider.symbols == ["MSFT"]
    assert cache.upserts == [
        (expected, "fake", NOW, NOW + timedelta(hours=24))
    ]


def test_service_calls_provider_when_cached_snapshot_is_expired():
    stale = CompanyFinancialSnapshot(symbol="AAPL", current_price=100)
    fresh = CompanyFinancialSnapshot(symbol="AAPL", current_price=101)
    provider = RecordingProvider(fresh)
    cache = RecordingCache(stale, expires_at=NOW)

    actual = MarketDataService(
        provider,
        cache=cache,
        clock=lambda: NOW,
    ).get_company_snapshot("aapl")

    assert actual is fresh
    assert provider.symbols == ["AAPL"]
    assert cache.upserts[0][0] is fresh


def test_service_uses_configured_ttl_for_provider_result():
    provider = RecordingProvider(CompanyFinancialSnapshot(symbol="NVDA"))
    cache = RecordingCache()
    ttl = timedelta(hours=6)

    MarketDataService(
        provider,
        cache=cache,
        ttl=ttl,
        clock=lambda: NOW,
    ).get_company_snapshot("NVDA")

    assert cache.upserts[0][2] == NOW
    assert cache.upserts[0][3] == NOW + ttl


def test_service_preserves_none_metrics_and_normalizes_symbol():
    provider = RecordingProvider(
        CompanyFinancialSnapshot(symbol="lower", market_cap=None, roe=None)
    )
    cache = RecordingCache()

    actual = MarketDataService(
        provider,
        cache=cache,
        clock=lambda: NOW,
    ).get_company_snapshot(" lower ")

    assert provider.symbols == ["LOWER"]
    assert actual.symbol == "LOWER"
    assert actual.market_cap is None
    assert actual.roe is None
    cached_snapshot = cache.upserts[0][0]
    assert cached_snapshot.model_dump()["market_cap"] is None
    assert cached_snapshot.model_dump()["roe"] is None


def test_service_preserves_structured_provider_failures_and_does_not_cache():
    error = ProviderUnavailableError(
        "provider unavailable",
        provider="fake",
        symbol="FAIL",
    )
    provider = FailingProvider(error)
    cache = RecordingCache()

    with pytest.raises(ProviderUnavailableError) as caught:
        MarketDataService(
            provider,
            cache=cache,
            clock=lambda: NOW,
        ).get_company_snapshot("fail")

    assert caught.value is error
    assert provider.symbols == ["FAIL"]
    assert cache.upserts == []


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

    actual = MarketDataService(
        cache=RecordingCache(),
        clock=lambda: NOW,
    ).get_company_snapshot("aapl")

    assert actual is expected
    assert requested_symbols == ["AAPL"]


def test_service_rejects_non_positive_cache_ttl():
    provider = RecordingProvider(CompanyFinancialSnapshot(symbol="AAPL"))

    with pytest.raises(ValueError, match="TTL must be positive"):
        MarketDataService(
            provider,
            cache=RecordingCache(),
            ttl=timedelta(0),
        )
