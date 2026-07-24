"""Application-level access to normalized market data."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.services.market_data.cache import (
    CompanySnapshotCache,
    SupabaseMarketDataSnapshotCache,
)
from app.services.market_data.models import CompanyFinancialSnapshot
from app.services.market_data.provider import MarketDataProvider

DEFAULT_COMPANY_SNAPSHOT_TTL = timedelta(hours=24)
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _provider_cache_name(provider: MarketDataProvider) -> str:
    configured_name = getattr(provider, "provider_name", None)
    if isinstance(configured_name, str) and configured_name.strip():
        return configured_name.strip().lower()

    class_name = type(provider).__name__
    if class_name.lower().endswith("provider"):
        class_name = class_name[:-8]
    return class_name.lower()


class MarketDataService:
    """Retrieve normalized snapshots through a fresh read-through cache."""

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        *,
        cache: CompanySnapshotCache | None = None,
        provider_name: str | None = None,
        ttl: timedelta = DEFAULT_COMPANY_SNAPSHOT_TTL,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if provider is None:
            from app.services.market_data.providers import YFinanceProvider

            provider = YFinanceProvider()
        if ttl <= timedelta(0):
            raise ValueError("Market data cache TTL must be positive")

        self._provider = provider
        self._cache = (
            cache if cache is not None else SupabaseMarketDataSnapshotCache()
        )
        self._provider_name = (
            provider_name.strip().lower()
            if provider_name is not None and provider_name.strip()
            else _provider_cache_name(provider)
        )
        self._ttl = ttl
        self._clock = clock

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        """Return a fresh cached snapshot or fetch and cache a provider result."""
        normalized_symbol = symbol.strip().upper()
        lookup_time = self._clock()
        try:
            cached = self._cache.get_fresh_company_snapshot(
                normalized_symbol,
                self._provider_name,
                now=lookup_time,
            )
        except Exception as exc:
            logger.warning(
                "Market data cache read failed for %s via %s (%s): %s",
                normalized_symbol,
                self._provider_name,
                type(exc).__name__,
                exc,
            )
            cached = None
        if cached is not None:
            return cached

        snapshot = self._provider.get_company_snapshot(normalized_symbol)
        if snapshot.symbol != normalized_symbol:
            snapshot = snapshot.model_copy(update={"symbol": normalized_symbol})
        fetched_at = self._clock()
        try:
            self._cache.upsert_company_snapshot(
                snapshot,
                self._provider_name,
                fetched_at=fetched_at,
                expires_at=fetched_at + self._ttl,
            )
        except Exception as exc:
            logger.warning(
                "Market data cache write failed for %s via %s (%s): %s",
                normalized_symbol,
                self._provider_name,
                type(exc).__name__,
                exc,
            )
        return snapshot
